# database_access.py - Updated to support both PostgreSQL and MySQL
import json
from decimal import Decimal
from datetime import datetime, date
import sys
import re
import requests
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Result
from dotenv import load_dotenv
import os
from db_config import get_db_config, get_engine
from llm_wrapper import get_global_llm
from schemas import (
    PLAYER_HISTORY_SCHEMA,
    PLAYER_PAST_SCHEMA,
    PLAYER_FUTURE_SCHEMA,
    clean_dataframe_for_schema,
)

load_dotenv()

# ---------- CONFIG ----------
# Database configuration now handled by db_config module
db_config = get_db_config()

# ---------- ENGINE ----------
# Use the centralized engine from db_config
engine = get_engine()

# ---------- HELPERS ----------
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
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
        headers, rows = run_sql("SELECT first_name, second_name, player_id FROM players")
        players_table = {"headers": headers, "rows": rows}

        prompt = f"""
Scan the following table and the question. Return ONLY the matching player_id (integer). 
If no match, return 0. No extra text.

Question: {natural_language_question}

Players Table (JSON):
{json.dumps(players_table, cls=DecimalEncoder)}
"""
        llm = get_global_llm()
        response_text = llm.generate_content(
            prompt,
            timeout=30
        )

        numbers = re.findall(r"\d+", response_text or "")
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
        r = requests.get(f"https://fantasy.premierleague.com/api/element-summary/{player_id}/", timeout=15)
        if r.status_code != 200:
            print(f"FPL API error (player): {r.status_code}")
            return False
        pdata = r.json()

        df_player_history = pd.DataFrame(pdata["history_past"])
        df_player_past = pd.DataFrame(pdata["history"])
        df_player_future = pd.DataFrame(pdata["fixtures"])

        # --- Teams and Players lookup ---
        bootstrap_resp = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/", timeout=15)
        if bootstrap_resp.status_code != 200:
            print("FPL bootstrap API error")
            return False
        bootstrap_data = bootstrap_resp.json()
        
        # Get teams data
        df_teams = pd.DataFrame(bootstrap_data["teams"])
        df_teams = df_teams.rename(columns={"id": "team_id", "name": "team_name"})
        df_teams = df_teams[['team_id', 'team_name', 'short_name', 'position', 'played',
                             'win', 'draw', 'loss', 'points', 'strength']]
        
        # Get player names
        player_info = next((p for p in bootstrap_data["elements"] if p["id"] == player_id), None)
        if not player_info:
            print(f"Player {player_id} not found in bootstrap data")
            return False
        first_name = player_info.get("first_name", "")
        second_name = player_info.get("second_name", "")

        # --- Clean & prepare history data using master schema ---
        if not df_player_history.empty:
            # Add player info to the dataframe
            df_player_history["player_id"] = player_id
            df_player_history["first_name"] = first_name
            df_player_history["second_name"] = second_name
            
            # Clean DataFrame to match master schema exactly
            df_player_history_clean = clean_dataframe_for_schema(
                df_player_history, PLAYER_HISTORY_SCHEMA, "player_history"
            )
            
            # Cast float columns
            float_cols = ['influence', 'creativity', 'threat', 'ict_index', 
                          'expected_goals', 'expected_assists', 
                          'expected_goal_involvements', 'expected_goals_conceded']
            
            for col in float_cols:
                if col in df_player_history_clean.columns:
                    df_player_history_clean[col] = pd.to_numeric(df_player_history_clean[col], errors='coerce')

            # --- Write historical data ---
            run_sql_write(df_player_history_clean, "player_history", mode="append")

        # --- Process and write past GW data only if it exists ---
        if not df_player_past.empty:
            # Rename API columns to match our schema and add player info
            df_player_past = df_player_past.rename(columns={'element': 'player_id'})
            df_player_past["first_name"] = first_name
            df_player_past["second_name"] = second_name
            
            # Clean DataFrame to match master schema exactly
            df_player_past_clean = clean_dataframe_for_schema(
                df_player_past, PLAYER_PAST_SCHEMA, "player_past"
            )
            
            # Cast float columns
            float_cols = ['influence', 'creativity', 'threat', 'ict_index', 
                          'expected_goals', 'expected_assists', 
                          'expected_goal_involvements', 'expected_goals_conceded']
            
            for col in float_cols:
                if col in df_player_past_clean.columns:
                    df_player_past_clean[col] = pd.to_numeric(df_player_past_clean[col], errors='coerce')

            run_sql_write(df_player_past_clean, "player_past", mode="append")

        # Always write player_future if available (not gated by past data)
        if not df_player_future.empty:
            # Add player info to the dataframe
            df_player_future["player_id"] = player_id
            df_player_future["first_name"] = first_name
            df_player_future["second_name"] = second_name
            
            # Clean DataFrame to match master schema exactly
            df_player_future_clean = clean_dataframe_for_schema(
                df_player_future, PLAYER_FUTURE_SCHEMA, "player_future"
            )
            
            run_sql_write(df_player_future_clean, "player_future", mode="append")

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
