#!/usr/bin/env python3
"""
Unified database setup script for SportSQL (local or remote).
Creates core tables (players, teams, fixtures) and can populate them from CSV and/or the FPL API.

Usage examples (run from repository root or from the SportSQL folder):
  - python -m SportSQL.setup_local_db --server local --source api
  - python setup_local_db.py --server remote --source both
"""

import os
import sys
import argparse
import pandas as pd
import requests
import numpy as np
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Float, Boolean, DateTime
from dotenv import load_dotenv
from src.database.schemas import get_create_table_sql, PLAYER_HISTORY_SCHEMA, PLAYER_PAST_SCHEMA, PLAYER_FUTURE_SCHEMA
from unidecode import unidecode
from bs4 import BeautifulSoup

# Add current directory to path to import src.database.config as db_config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.database.config import get_db_config, get_engine

load_dotenv()

def create_tables(engine):
    """Create all necessary tables in PostgreSQL."""
    print("Creating database tables...")
    
    # Create tables using raw SQL (PostgreSQL syntax)
    tables_sql = [
        """
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER PRIMARY KEY,
            team_name VARCHAR(100),
            short_name VARCHAR(10),
            position INTEGER,
            played INTEGER,
            win INTEGER,
            draw INTEGER,
            loss INTEGER,
            points INTEGER,
            strength INTEGER
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS players (
            player_id INTEGER PRIMARY KEY,
            first_name VARCHAR(100),
            second_name VARCHAR(100),
            web_name VARCHAR(100),
            player_position VARCHAR(20),
            team_id INTEGER,
            team_name VARCHAR(100),
            form FLOAT,
            points_per_game FLOAT,
            starts INTEGER,
            minutes INTEGER,
            goals_scored INTEGER,
            assists INTEGER,
            yellow_cards INTEGER,
            red_cards INTEGER,
            penalties_missed INTEGER,
            own_goals INTEGER,
            goals_conceded INTEGER,
            saves INTEGER,
            clean_sheets INTEGER,
            penalties_saved INTEGER,
            goals_per_90 FLOAT,
            assists_per_90 FLOAT,
            goals_conceded_per_90 FLOAT,
            saves_per_90 FLOAT,
            clean_sheets_per_90 FLOAT,
            expected_goals FLOAT,
            expected_assists FLOAT,
            expected_goal_involvements FLOAT,
            expected_goals_conceded FLOAT,
            expected_goals_per_90 FLOAT,
            expected_assists_per_90 FLOAT,
            expected_goal_involvements_per_90 FLOAT,
            expected_goals_conceded_per_90 FLOAT,
            ict_index FLOAT,
            influence FLOAT,
            creativity FLOAT,
            threat FLOAT,
            form_rank INTEGER,
            form_rank_type INTEGER,
            ict_index_rank INTEGER,
            ict_index_rank_type INTEGER,
            influence_rank INTEGER,
            influence_rank_type INTEGER,
            creativity_rank INTEGER,
            creativity_rank_type INTEGER,
            threat_rank INTEGER,
            threat_rank_type INTEGER,
            points_per_game_rank INTEGER,
            points_per_game_rank_type INTEGER,
            total_points INTEGER
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS fixtures (
            game_id INTEGER PRIMARY KEY,
            gw INTEGER,
            finished BOOLEAN,
            team_a INTEGER,
            team_h INTEGER,
            team_h_name VARCHAR(100),
            team_h_score INTEGER,
            team_a_name VARCHAR(100),
            team_a_score INTEGER,
            kickoff_time TIMESTAMP,
            team_h_difficulty INTEGER,
            team_a_difficulty INTEGER
        )
        """,
        get_create_table_sql("player_history", PLAYER_HISTORY_SCHEMA),
        get_create_table_sql("player_past", PLAYER_PAST_SCHEMA),
        get_create_table_sql("player_future", PLAYER_FUTURE_SCHEMA)
    ]
    
    with engine.connect() as conn:
        for sql in tables_sql:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception as e:
                print(f"Error creating table: {e}")
                continue
    
    print("✅ Tables created successfully!")

def populate_from_csv(engine):
    """Populate tables from existing CSV files if they exist."""
    print("Populating tables from CSV files...")
    
    # Only preload core season-wide tables from CSV. Per-player tables (player_history,
    # player_past, player_future) are populated on-demand via update_player_data().
    csv_files = {
        'teams': 'data/teams.csv',
        'players': 'data/players.csv',
        'fixtures': 'data/fixtures.csv'
    }
    
    for table_name, csv_path in csv_files.items():
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                df.to_sql(table_name, engine, if_exists='replace', index=False, method='multi', chunksize=1000)
                print(f"✅ Populated {table_name} from {csv_path} ({len(df)} rows)")
            except Exception as e:
                print(f"❌ Error populating {table_name}: {e}")
        else:
            print(f"⚠️  CSV file not found: {csv_path}")

def populate_from_api(engine):
    """Populate tables from FPL API (same as update_db.py but for PostgreSQL)."""
    print("Fetching fresh data from FPL API...")
    
    try:
        # Fetch main data
        url = "https://fantasy.premierleague.com/api/bootstrap-static/"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            df_teams = pd.DataFrame(data['teams'])
            df_players = pd.DataFrame(data['elements'])
            print('✅ Successfully extracted data from FPL API')
        else:
            print(f"❌ Failed to retrieve data from API. Status code: {response.status_code}")
            return False
        
        # Process teams data
        df_teams = df_teams.rename(columns={'id': 'team_id', 'name': 'team_name'})
        df_teams = df_teams[['team_id', 'team_name', 'short_name', 'position', 'played', 'win', 'draw', 'loss', 'points', 'strength']]
        
        # Process players data
        df_players = df_players.rename(columns={'team': 'team_id', 'id': 'player_id', 'element_type': 'player_position'})
        
        # Create calculated columns
        df_players['goals_per_90'] = (df_players['goals_scored'] / df_players['minutes'].replace(0, np.nan)) * 90
        df_players['assists_per_90'] = (df_players['assists'] / df_players['minutes'].replace(0, np.nan)) * 90
        
        # Add team names
        df_players['team_name'] = df_players['team_id'].map(df_teams.set_index('team_id')['team_name'])
        
        # Filter columns
        player_columns = ['player_id', 'first_name', 'second_name', 'web_name', 'player_position', 'team_id', 'team_name', 'form', 'points_per_game', 'starts', 'minutes', 'goals_scored', 'assists', 'yellow_cards', 'red_cards', 'penalties_missed', 'own_goals', 'goals_conceded', 'saves', 'clean_sheets', 'penalties_saved', 'goals_per_90', 'assists_per_90', 'goals_conceded_per_90', 'saves_per_90', 'clean_sheets_per_90', 'expected_goals', 'expected_assists', 'expected_goal_involvements', 'expected_goals_conceded', 'expected_goals_per_90', 'expected_assists_per_90', 'expected_goal_involvements_per_90', 'expected_goals_conceded_per_90', 'ict_index', 'influence', 'creativity', 'threat', 'form_rank', 'form_rank_type', 'ict_index_rank', 'ict_index_rank_type', 'influence_rank', 'influence_rank_type', 'creativity_rank', 'creativity_rank_type', 'threat_rank', 'threat_rank_type', 'points_per_game_rank', 'points_per_game_rank_type', 'total_points']
        
        df_players = df_players[player_columns]
        
        # Clean data types
        columns_to_floats = ['form', 'points_per_game', 'goals_per_90', 'assists_per_90', 'goals_conceded_per_90', 'saves_per_90', 'clean_sheets_per_90', 'expected_goals', 'expected_assists', 'expected_goal_involvements', 'expected_goals_conceded', 'expected_goals_per_90', 'expected_assists_per_90', 'expected_goal_involvements_per_90', 'expected_goals_conceded_per_90', 'ict_index', 'influence', 'creativity', 'threat']
        df_players[columns_to_floats] = df_players[columns_to_floats].astype(float)
        
        columns_to_ints = ['player_id', 'team_id', 'starts', 'minutes', 'goals_scored', 'assists', 'yellow_cards', 'red_cards', 'penalties_missed', 'own_goals', 'goals_conceded', 'saves', 'clean_sheets', 'penalties_saved', 'form_rank', 'form_rank_type', 'ict_index_rank', 'ict_index_rank_type', 'influence_rank', 'influence_rank_type', 'creativity_rank', 'creativity_rank_type', 'threat_rank', 'threat_rank_type', 'points_per_game_rank', 'points_per_game_rank_type', 'total_points']
        df_players[columns_to_ints] = df_players[columns_to_ints].astype(int)
        
        columns_to_strings = ['first_name', 'second_name', 'web_name', 'team_name']
        df_players[columns_to_strings] = df_players[columns_to_strings].astype(str)
        
        # Map player positions
        position_mapping = {1: 'Goalkeeper', 2: 'Defender', 3: 'Midfielder', 4: 'Forward'}
        df_players['player_position'] = df_players['player_position'].map(position_mapping)
        
        # Clean names
        df_players['first_name'] = df_players['first_name'].map(unidecode)
        df_players['second_name'] = df_players['second_name'].map(unidecode)
        df_players['web_name'] = df_players['web_name'].map(unidecode)
        
        # Write to database
        df_players.to_sql('players', engine, if_exists='replace', index=False, method='multi', chunksize=1000)
        print(f"✅ Populated players table ({len(df_players)} rows)")
        
        # Process teams data from API (same as mariadb_access.py)
        df_teams = df_teams.rename(columns={'id': 'team_id', 'name': 'team_name'})
        df_teams = df_teams[['team_id', 'team_name', 'short_name', 'position', 'played',
                             'win', 'draw', 'loss', 'points', 'strength']]
        df_teams.to_sql('teams', engine, if_exists='replace', index=False, method='multi', chunksize=1000)
        print(f"✅ Populated teams table ({len(df_teams)} rows)")
        
        # Fetch fixtures
        fixtures_url = "https://fantasy.premierleague.com/api/fixtures/"
        fixtures_response = requests.get(fixtures_url)
        if fixtures_response.status_code == 200:
            fixtures_data = fixtures_response.json()
            df_fixtures = pd.DataFrame(fixtures_data)
            
            df_fixtures = df_fixtures.rename(columns={'event': 'gw', 'id': 'game_id'})
            df_fixtures['team_a_name'] = df_fixtures['team_a'].map(df_teams.set_index('team_id')['team_name'])
            df_fixtures['team_h_name'] = df_fixtures['team_h'].map(df_teams.set_index('team_id')['team_name'])
            
            fixture_columns = ['game_id', 'gw', 'finished', 'team_a', 'team_h', 'team_h_name', 'team_h_score', 'team_a_name', 'team_a_score', 'kickoff_time', 'team_h_difficulty', 'team_a_difficulty']
            df_fixtures = df_fixtures[fixture_columns]
            
            df_fixtures.to_sql('fixtures', engine, if_exists='replace', index=False, method='multi', chunksize=1000)
            print(f"✅ Populated fixtures table ({len(df_fixtures)} rows)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error populating from API: {e}")
        return False

def main():
    """Main setup function (works for both local and remote)."""
    parser = argparse.ArgumentParser(description="SportSQL DB setup")
    parser.add_argument("--server", choices=["local", "remote"], default="local",
                        help="Database target: local (PostgreSQL) or remote (PostgreSQL on Cloud)")
    parser.add_argument("--source", choices=["csv", "api", "both"], default="api",
                        help="Data source to populate core tables")
    args = parser.parse_args()

    print("=" * 60)
    print("SportSQL Database Setup")
    print("=" * 60)

    # Initialize database configuration based on flag
    db_conf = get_db_config(args.server)
    engine = get_engine()

    info = db_conf.get_database_info()
    print(f"Setting up database: {info['type']}")
    print(f"Host: {info['host']}")
    print(f"Database: {info['database']}")
    print("=" * 60)

    try:
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Connected: {version}")

        # Create tables
        create_tables(engine)

        # Populate according to requested source
        if args.source in ["csv", "both"]:
            populate_from_csv(engine)

        if args.source in ["api", "both"]:
            populate_from_api(engine)

        print("\n" + "=" * 60)
        print("✅ Database setup completed!")
        print("You can now run the app: python app.py --server", args.server)
        print("=" * 60)

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        print("\nPlease ensure:")
        print("1. Target database is reachable (env vars & network)")
        print("2. Database exists and credentials are correct")
        print("3. .env contains the correct settings for the chosen --server")
        sys.exit(1)

if __name__ == "__main__":
    main()
