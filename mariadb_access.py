import mariadb
import json
from decimal import Decimal
import sys
import requests
import pandas as pd
from sqlalchemy import create_engine
import google.generativeai as genai
from dotenv import load_dotenv
import os
load_dotenv()


# Database connection configuration
config = {
    'host': os.getenv("DATABASE_HOST"),
    'user': os.getenv("DATABASE_USER"),
    'password': os.getenv("DATABASE_PASSWORD"),  # Replace with your actual password
    'database': os.getenv("DATABASE_NAME")         # Replace with your actual database name
}

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def execute_query(cursor, query):
    """Executes an SQL query and returns the extracted result."""
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        return result
    except mariadb.Error as e:
        print(f"SQL Execution Error: {e}")
        return None

def return_query(sql_query):
    try:
        conn = mariadb.connect(
            user=config['user'],
            password=config['password'],
            host=config['host'],
            port=3307,
            database=config['database']
        )
        #print("Connected to MariaDB Platform!")
        cur = conn.cursor()

        gt_result = execute_query(cur, sql_query)

        #print(gt_result)

        #rows = cur.fetchall()
        rows = gt_result
        columns = [desc[0] for desc in cur.description]

        # Format the results as JSON
        result = {
            "headers": columns,
            "rows": rows
        }

        # Close connection
        cur.close()
        conn.close()

        # Use the custom encoder for JSON serialization
        return json.dumps(result, cls=DecimalEncoder)

    except mariadb.Error as e:
        print(f"Error connecting to MariaDB Platform: {e}")
        return json.dumps({"error": str(e)})

def get_player_id_from_question(natural_language_question):
    """
    Extracts player ID from a natural language question by:
    1. Getting all player names from the database
    2. Using Gemini API to match the question with the correct player
    3. Returns the player_id or 0 if no match found
    """
    try:
        # Step 1: Get all player names from database
        conn = mariadb.connect(
            user=config['user'],
            password=config['password'],  
            host=config['host'],
            port=3307,
            database=config['database']
        )
        cur = conn.cursor()
        
        # Query to get all player names and IDs
        player_query = """
        SELECT web_name, first_name, second_name, player_id 
        FROM players
        """
        players_data = execute_query(cur, player_query)
        columns = [desc[0] for desc in cur.description]
        
        # Format the data for Gemini API
        players_table = {
            "headers": columns,
            "rows": players_data
        }
        
        # Step 2: Create prompt for Gemini API
        prompt = f"""
        Scan the following table and question and return only the corresponding player_id, no other text. 
        If you cannot find a match then return 0.
        
        Question: {natural_language_question}
        
        Players Table:
        {json.dumps(players_table, cls=DecimalEncoder)}

        Remember to only return the player_id, no other text.
        """
        
        # Step 3: Get player_id from Gemini API
        genai.configure(api_key=os.getenv("API_KEY"))
        model = genai.GenerativeModel("gemini-2.0-flash")
    
        response = model.generate_content(prompt)
        
        # Extract numeric value from response
        try:
            # Try to find a number in the response
            import re
            numbers = re.findall(r'\d+', response.text)
            if numbers:
                player_id = int(numbers[0])  # Take the first number found
            else:
                player_id = 0
        except (ValueError, IndexError):
            player_id = 0
        
        # Close connection
        cur.close()
        conn.close()
        
        return player_id
        
    except Exception as e:
        print(f"Error in get_player_id_from_question: {e}")
        return 0

def update_player_data(player_id):
    """
    Updates player data in the database by:
    1. Fetching data from FPL API
    2. Processing and cleaning the data
    3. Updating the database tables
    """
    if player_id == 0:
        return None
    try:
        # Step 1: Fetch data from FPL API
        response = requests.get(f'https://fantasy.premierleague.com/api/element-summary/{player_id}/')
        
        if response.status_code != 200:
            print(f"Failed to retrieve data from API. Status code: {response.status_code}")
            return False
            
        data = response.json()
        
        # Step 2: Create DataFrames
        df_player_history = pd.DataFrame(data['history_past'])
        df_player_past = pd.DataFrame(data['history'])
        df_player_future = pd.DataFrame(data['fixtures'])
        
        # Get teams data for mapping
        teams_response = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/')
        if teams_response.status_code == 200:
            teams_data = teams_response.json()
            df_teams = pd.DataFrame(teams_data['teams'])
        else:
            print("Failed to retrieve teams data")
            return False
        
        df_teams = df_teams.rename(columns={'id': 'team_id', 'name': 'team_name'})
        df_teams = df_teams[['team_id', 'team_name', 'short_name', 'position', 'played', 'win', 'draw', 'loss', 'points', 'strength']]
        # Step 3: Process player history data
        df_player_history = df_player_history[['season_name', 'total_points',
           'minutes', 'goals_scored', 'assists', 'clean_sheets', 'goals_conceded',
           'own_goals', 'penalties_saved', 'penalties_missed', 'yellow_cards',
           'red_cards', 'saves', 'starts', 'influence', 'creativity', 'threat', 
           'ict_index', 'expected_goals', 'expected_assists',
           'expected_goal_involvements', 'expected_goals_conceded']]
        
        # Convert numeric columns to float
        columns_to_floats = ['influence', 'creativity', 'threat', 'ict_index', 
                           'expected_goals', 'expected_assists', 
                           'expected_goal_involvements', 'expected_goals_conceded']
        df_player_history[columns_to_floats] = df_player_history[columns_to_floats].astype(float)
        
        # Step 4: Process player past data
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
        
        df_player_past[columns_to_floats] = df_player_past[columns_to_floats].astype(float)
        
        # Step 5: Process player future data
        # df_player_future['team_h_name'] = df_player_future['team_h'].map(
        #     df_teams.set_index('team_id')['team_name']
        # )
        # df_player_future['team_a_name'] = df_player_future['team_a'].map(
        #     df_teams.set_index('team_id')['team_name']
        # )
        
        # df_player_future = df_player_future[['event', 'event_name', 'team_h', 'team_a', 
        #                                    'team_h_name', 'team_a_name', 'is_home', 
        #                                    'difficulty', 'kickoff_time']]
        
        # Step 6: Update database
        engine = create_engine('mysql+pymysql://{user}:{password}@{host}:{port}/{database}'.format(
            user=os.getenv("DATABASE_USER"),
            password=os.getenv("DATABASE_PASSWORD"),
            host=os.getenv("DATABASE_HOST"),
            port=os.getenv("DATABASE_PORT"),
            database=os.getenv("DATABASE_NAME")
        )   )
        
        df_player_history.to_sql('player_history', engine, if_exists='replace', index=False)
        df_player_past.to_sql('player_past', engine, if_exists='replace', index=False)
        #df_player_future.to_sql('player_future', engine, if_exists='replace', index=False)
        
        return True
        
    except Exception as e:
        print(f"Error in update_player_data: {e}")
        return False

if __name__ == "__main__":
    # Read the SQL query from the command-line arguments
    sql_query = sys.argv[1]
    print(return_query(sql_query))