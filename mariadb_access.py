# update_db_runtime.py
import json
from decimal import Decimal
import sys
import re
import requests
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Result
import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()

# ---------- CONFIG ----------
DB_HOST = os.getenv("DATABASE_HOST")
DB_USER = os.getenv("DATABASE_USER")
DB_PASS = os.getenv("DATABASE_PASSWORD")
DB_NAME = os.getenv("DATABASE_NAME")
DB_PORT = int(os.getenv("DATABASE_PORT", 3306))

GEMINI_API_KEY = os.getenv("API_KEY")          # rename if needed
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ---------- ENGINE ----------
def get_engine() -> Engine:
    # Public IP path; if you swap to Cloud SQL Proxy, change host/port to 127.0.0.1:3307
    return create_engine(
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=1,
        max_overflow=2,
        connect_args={"connect_timeout": 10}
    )

engine = get_engine()

# ---------- HELPERS ----------
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def run_sql(sql: str) -> tuple[list[str], list[tuple]]:
    """Run a read-only SQL and return (headers, rows)."""
    with engine.connect() as conn:
        result: Result = conn.execute(text(sql))
        # Convert each row to a tuple for JSON serialization
        rows = [tuple(row) for row in result.fetchall()]
        headers = result.keys()
    return list(headers), rows

def run_sql_write(df: pd.DataFrame, table: str, mode: str = "replace"):
    """Write a DataFrame to MySQL."""
    df.to_sql(table, engine, if_exists=mode, index=False, method="multi", chunksize=1000)

# ---------- PUBLIC FUNCTIONS ----------
def execute_query(sql_query: str) -> str:
    """Executes SQL and returns JSON {headers, rows}."""
    try:
        headers, rows = run_sql(sql_query)
        return json.dumps({"headers": headers, "rows": rows}, cls=DecimalEncoder)
    except Exception as e:
        print(f"SQL Execution Error: {e}")
        return json.dumps({"error": str(e)})

def return_query(sql_query: str) -> str:
    """Backward-compatible wrapper."""
    return execute_query(sql_query)

def get_player_id_from_question(natural_language_question: str) -> int:
    """
    1. Pull player names/ids from DB
    2. Ask Gemini which row matches the question
    3. Return player_id (int) or 0
    """
    try:
        headers, rows = run_sql("SELECT web_name, first_name, second_name, player_id FROM players")
        players_table = {"headers": headers, "rows": rows}

        prompt = f"""
Scan the following table and the question. Return ONLY the matching player_id (integer). 
If no match, return 0. No extra text.

Question: {natural_language_question}

Players Table (JSON):
{json.dumps(players_table, cls=DecimalEncoder)}
"""
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)

        numbers = re.findall(r"\d+", response.text or "")
        return int(numbers[0]) if numbers else 0

    except Exception as e:
        print(f"Error in get_player_id_from_question: {e}")
        return 0

def update_player_data(player_id: int) -> bool:
    """
    Pull fresh data for a player from FPL and update tables.
    Returns True on success, False otherwise.
    """
    if player_id == 0:
        return False
    try:
        # --- Fetch player-specific data ---
        r = requests.get(f"https://fantasy.premierleague.com/api/element-summary/{player_id}/")
        if r.status_code != 200:
            print(f"FPL API error (player): {r.status_code}")
            return False
        pdata = r.json()

        df_player_history = pd.DataFrame(pdata["history_past"])
        df_player_past = pd.DataFrame(pdata["history"])
        df_player_future = pd.DataFrame(pdata["fixtures"])  # currently unused

        # --- Teams lookup ---
        teams_resp = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
        if teams_resp.status_code != 200:
            print("FPL teams API error")
            return False
        df_teams = pd.DataFrame(teams_resp.json()["teams"])
        df_teams = df_teams.rename(columns={"id": "team_id", "name": "team_name"})
        df_teams = df_teams[['team_id', 'team_name', 'short_name', 'position', 'played',
                             'win', 'draw', 'loss', 'points', 'strength']]

        # --- Clean & cast history data ---
        df_player_history = df_player_history[['season_name', 'total_points',
           'minutes', 'goals_scored', 'assists', 'clean_sheets', 'goals_conceded',
           'own_goals', 'penalties_saved', 'penalties_missed', 'yellow_cards',
           'red_cards', 'saves', 'starts', 'influence', 'creativity', 'threat', 
           'ict_index', 'expected_goals', 'expected_assists',
           'expected_goal_involvements', 'expected_goals_conceded']]

        float_cols = ['influence', 'creativity', 'threat', 'ict_index', 
                      'expected_goals', 'expected_assists', 
                      'expected_goal_involvements', 'expected_goals_conceded']
        df_player_history[float_cols] = df_player_history[float_cols].astype(float)

        # --- Past GW data ---
        df_player_past = df_player_past.rename(columns={'round': 'event', 'element': 'player_id'})
        df_player_past['opponent_team_name'] = df_player_past['opponent_team'].map(
            df_teams.set_index('team_id')['team_name']
        )
        df_player_past = df_player_past[['player_id', 'event', 'was_home', 'opponent_team',
                                        'opponent_team_name', 'team_h_score', 'team_a_score',
                                        'minutes', 'goals_scored', 'assists', 'clean_sheets',
                                        'goals_conceded', 'own_goals', 'penalties_saved',
                                        'penalties_missed', 'yellow_cards', 'red_cards', 'saves',
                                        'starts', 'influence', 'creativity', 'threat', 'ict_index',
                                        'expected_goals', 'expected_assists',
                                        'expected_goal_involvements', 'expected_goals_conceded',
                                        'kickoff_time']]
        df_player_past[float_cols] = df_player_past[float_cols].astype(float)

        # --- Write back ---
        run_sql_write(df_player_history, "player_history", mode="replace")
        run_sql_write(df_player_past, "player_past", mode="replace")
        # run_sql_write(df_player_future, "player_future", mode="replace")  # if needed later

        return True
    except Exception as e:
        print(f"Error in update_player_data: {e}")
        return False

# ---------- CLI ----------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update_db_runtime.py \"SELECT * FROM players LIMIT 5\"")
        sys.exit(1)

    sql_query = " ".join(sys.argv[1:])
    print(return_query(sql_query))
