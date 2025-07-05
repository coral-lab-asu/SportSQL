from sqlalchemy import create_engine
import pandas as pd
import requests
import numpy as np
from unidecode import unidecode
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
load_dotenv()

engine = create_engine(
    "mariadb+mariadbconnector://{user}:{password}@{host}:{port}/{database}".format(
        user=os.getenv("DATABASE_USER"),
        password=os.getenv("DATABASE_PASSWORD"),  
        host=os.getenv("DATABASE_HOST"),
        port=os.getenv("DATABASE_PORT"),
        database=os.getenv("DATABASE_NAME")
    )
)

#df = pd.read_sql_table('players', engine)


url = "https://fantasy.premierleague.com/api/bootstrap-static/"
response = requests.get(url)


if response.status_code == 200:
    # Convert the JSON data to a Python dictionary
    data = response.json()

    df_teams = pd.DataFrame(data['teams']) # Extract team data (teams) into a DataFrame
    df_players = pd.DataFrame(data['elements']) # Extract player data (elements) into a DataFrame

    print('Successfully extracted all tables')
else:
    print("Failed to retrieve data from API. Status code:", response.status_code)

# rename columns
df_teams = df_teams.rename(columns={'id': 'team_id', 'name': 'team_name'})
df_players = df_players.rename(columns={'team': 'team_id', 'id': 'player_id', 'element_type': 'player_position'})

# create columns
df_players['goals_per_90'] = (df_players['goals_scored'] / df_players['minutes'].replace(0, np.nan)) * 90
df_players['assists_per_90'] = (df_players['assists'] / df_players['minutes'].replace(0, np.nan)) * 90

# insert 'team_name' column based on 'team_id'
df_players['team_name'] = df_players['team_id'].map(df_teams.set_index('team_id')['team_name'])

# filter out columns
df_teams = df_teams[['team_id', 'team_name', 'short_name', 'position', 'played', 'win', 'draw', 'loss', 'points', 'strength']]
df_players = df_players[['player_id', 'first_name', 'second_name', 'web_name', 'player_position', 'team_id', 'team_name', 'form', 'points_per_game', 'starts', 'minutes', 'goals_scored', 'assists', 'yellow_cards', 'red_cards', 'penalties_missed', 'own_goals', 'goals_conceded', 'saves', 'clean_sheets', 'penalties_saved', 'goals_per_90', 'assists_per_90', 'goals_conceded_per_90', 'saves_per_90', 'clean_sheets_per_90', 'expected_goals', 'expected_assists', 'expected_goal_involvements', 'expected_goals_conceded', 'expected_goals_per_90', 'expected_assists_per_90', 'expected_goal_involvements_per_90', 'expected_goals_conceded_per_90', 'ict_index', 'influence', 'creativity', 'threat', 'form_rank', 'form_rank_type', 'ict_index_rank', 'ict_index_rank_type', 'influence_rank', 'influence_rank_type', 'creativity_rank', 'creativity_rank_type', 'threat_rank', 'threat_rank_type', 'points_per_game_rank', 'points_per_game_rank_type', 'total_points']]

# clean column datatypes
columns_to_floats = ['form', 'points_per_game', 'goals_per_90', 'assists_per_90', 'goals_conceded_per_90', 'saves_per_90', 'clean_sheets_per_90', 'expected_goals', 'expected_assists', 'expected_goal_involvements', 'expected_goals_conceded', 'expected_goals_per_90', 'expected_assists_per_90', 'expected_goal_involvements_per_90', 'expected_goals_conceded_per_90', 'ict_index', 'influence', 'creativity', 'threat']
df_players[columns_to_floats] = df_players[columns_to_floats].astype(float)
columns_to_ints = ['player_id', 'team_id', 'starts', 'minutes', 'goals_scored', 'assists', 'yellow_cards', 'red_cards', 'penalties_missed', 'own_goals', 'goals_conceded', 'saves', 'clean_sheets', 'penalties_saved', 'form_rank', 'form_rank_type', 'ict_index_rank', 'ict_index_rank_type', 'influence_rank', 'influence_rank_type', 'creativity_rank', 'creativity_rank_type', 'threat_rank', 'threat_rank_type', 'points_per_game_rank', 'points_per_game_rank_type', 'total_points']
df_players[columns_to_ints] = df_players[columns_to_ints].astype(int)
columns_to_strings = ['first_name', 'second_name', 'web_name', 'team_name']
df_players[columns_to_strings] = df_players[columns_to_strings].astype(str)

position_mapping = {
    1: 'Goalkeeper',
    2: 'Defender',
    3: 'Midfielder',
    4: 'Forward'
}

# Update the position column using the mapping
df_players['player_position'] = df_players['player_position'].map(position_mapping)

df_players['first_name'] = df_players['first_name'].map(unidecode)
df_players['second_name'] = df_players['second_name'].map(unidecode)
df_players['web_name'] = df_players['web_name'].map(unidecode)

#df.to_sql('players', engine, if_exists='replace', index=False)
df_players.to_sql('players', engine, if_exists='replace', index=False)



# Get Table Standings ------------------------------------------------------------------------
link = "https://onefootball.com/en/competition/premier-league-9/table"
source = requests.get(link).text
page = BeautifulSoup(source, "lxml")

# Find all rows in the standings table
rows = page.find_all("li", class_="Standing_standings__row__5sdZG")

# Initialize lists to store the data
positions = []
teams = []
played_list = []
wins_list = []
draws_list = []
losses_list = []
points_list = []

# Extract data for each row
for row in rows:
    position_elem = row.find("div", class_="Standing_standings__cell__5Kd0W")
    team_elem = row.find("p", class_="Standing_standings__teamName__psv61")
    stats = row.find_all("div", class_="Standing_standings__cell__5Kd0W")

    if position_elem and team_elem and len(stats) >= 7:
        position = position_elem.text.strip()
        team = team_elem.text.strip()
        played = stats[2].text.strip()
        wins = stats[3].text.strip()
        draws = stats[4].text.strip()
        losses = stats[5].text.strip()
        points = stats[7].text.strip()

        positions.append(position)
        teams.append(team)
        played_list.append(played)
        wins_list.append(wins)
        draws_list.append(draws)
        losses_list.append(losses)
        points_list.append(points)

# Create a pandas DataFrame
data = {
    "team_name": teams,
    "position": positions,
    "played": played_list,
    "win": wins_list,
    "draw": draws_list,
    "loss": losses_list,
    "points": points_list
}

df = pd.DataFrame(data)

replacements = {
    "AFC Bournemouth": "Bournemouth",
    "Brighton & Hove Albion": "Brighton",
    "Ipswich Town": "Ipswich",
    "Leicester City": "Leicester",
    "Liverpool FC": "Liverpool",
    "Manchester City": "Man City",
    "Manchester United": "Man Utd",
    "Newcastle United": "Newcastle",
    "Nottingham Forest": "Nott'm Forest",
    "Tottenham Hotspur": "Spurs",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves"
}

# Apply the replacements
df['team_name'] = df['team_name'].replace(replacements)

#add team_id column
df['team_id'] = df['team_name'].map(df_teams.set_index('team_name')['team_id'])
#add team short_name column
df['team_short_name'] = df['team_name'].map(df_teams.set_index('team_name')['short_name'])
#add strength column
df['strength'] = df['team_name'].map(df_teams.set_index('team_name')['strength'])

#UNCOMMENT THIS LINE WHEN NEW SEASON STARTS
#df.to_sql('teams', engine, if_exists='replace', index=False)

data = {
    'team_id': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
    'team_name': [
        'Arsenal', 'Aston Villa', 'Bournemouth', 'Brentford', 'Brighton',
        'Chelsea', 'Crystal Palace', 'Everton', 'Fulham', 'Ipswich',
        'Leicester', 'Liverpool', 'Man City', 'Man Utd', 'Newcastle',
        'Nott\'m Forest', 'Southampton', 'Spurs', 'West Ham', 'Wolves'
    ],
    'short_name': [
        'ARS', 'AVL', 'BOU', 'BRE', 'BHA', 'CHE', 'CRY', 'EVE', 'FUL', 'IPS',
        'LEI', 'LIV', 'MCI', 'MUN', 'NEW', 'NFO', 'SOU', 'TOT', 'WHU', 'WOL'
    ],
    'position': [2, 6, 9, 10, 8, 4, 12, 13, 11, 19, 18, 1, 3, 15, 5, 7, 20, 17, 14, 16],
    'played': [38, 38, 38, 38, 38, 38, 38, 38, 38, 38, 38, 38, 38, 38, 38, 38, 38, 38, 38, 38],
    'win': [20, 19, 15, 16, 16, 20, 13, 11, 15, 4, 6, 25, 21, 11, 20, 19, 2, 11, 11, 12],
    'draw': [14, 9, 11, 8, 13, 9, 14, 15, 9, 10, 7, 9, 8, 9, 6, 8, 6, 5, 10, 6],
    'loss': [4, 10, 12, 14, 9, 9, 11, 12, 14, 24, 25, 4, 9, 18, 12, 11, 30, 22, 17, 20],
    'points': [74, 66, 56, 56, 61, 69, 53, 48, 54, 22, 25, 84, 71, 42, 66, 65, 12, 38, 43, 42],
    'strength': [5, 3, 3, 3, 3, 3, 3, 3, 3, 2, 2, 5, 4, 3, 4, 4, 2, 3, 3, 3]
}

# Create the Pandas DataFrame
df_epl = pd.DataFrame(data)
df_epl.to_sql('teams', engine, if_exists='replace', index=False)

# Get Fixtures ------------------------------------------------------------------------
# API request
url = "https://fantasy.premierleague.com/api/fixtures/"
response = requests.get(url)

# Check if the request was successful
if response.status_code == 200:
    # Convert the JSON data to a Python dictionary
    data = response.json()

    df_fixtures = pd.DataFrame(data) # Extract player data (elements) into a DataFrame

    print('Successfully extracted all tables')
else:
    print("Failed to retrieve data from API. Status code:", response.status_code)

# CLEANING
#----------------------------
df_fixtures = df_fixtures.rename(columns={'event': 'gw', 'id': 'game_id'})
df_fixtures['team_a_name'] = df_fixtures['team_a'].map(df_teams.set_index('team_id')['team_name'])
df_fixtures['team_h_name'] = df_fixtures['team_h'].map(df_teams.set_index('team_id')['team_name'])

# filter out columns
df_fixtures = df_fixtures[['game_id', 'gw', 'finished', 'team_a', 'team_h', 'team_h_name', 'team_h_score', 'team_a_name', 'team_a_score', 'kickoff_time', 'team_h_difficulty', 'team_a_difficulty']]
#----------------------------

# Insert into DB
df_fixtures.to_sql('fixtures', engine, if_exists='replace', index=False)

