#!/usr/bin/env python3
"""
🏗️ Master Schema Definitions for SportSQL

This module provides a single source of truth for all table schemas,
ensuring consistency across the entire application.

Key Features:
- ✅ Based on actual FPL API data structures
- ✅ Eliminates schema drift between modules
- ✅ Automatic data cleaning and validation
- ✅ Programmatic table creation

Usage:
    from SportSQL.schemas import PLAYER_HISTORY_SCHEMA, get_create_table_sql
    
    # Create table
    sql = get_create_table_sql("player_history", PLAYER_HISTORY_SCHEMA)
    
    # Clean DataFrame
    clean_df = clean_dataframe_for_schema(df, PLAYER_HISTORY_SCHEMA, "player_history")
"""

# Based on actual FPL API data structure for history_past
PLAYER_HISTORY_SCHEMA = {
    'columns': [
        ('id', 'SERIAL PRIMARY KEY'),
        ('player_id', 'INTEGER NOT NULL'),
        ('first_name', 'VARCHAR(100)'),
        ('second_name', 'VARCHAR(100)'),
        ('season_name', 'VARCHAR(20)'),
        ('element_code', 'INTEGER'),
        ('start_cost', 'INTEGER'),
        ('end_cost', 'INTEGER'),
        ('total_points', 'INTEGER'),
        ('minutes', 'INTEGER'),
        ('goals_scored', 'INTEGER'),
        ('assists', 'INTEGER'),
        ('clean_sheets', 'INTEGER'),
        ('goals_conceded', 'INTEGER'),
        ('own_goals', 'INTEGER'),
        ('penalties_saved', 'INTEGER'),
        ('penalties_missed', 'INTEGER'),
        ('yellow_cards', 'INTEGER'),
        ('red_cards', 'INTEGER'),
        ('saves', 'INTEGER'),
        ('bonus', 'INTEGER'),
        ('bps', 'INTEGER'),
        ('influence', 'FLOAT'),
        ('creativity', 'FLOAT'),
        ('threat', 'FLOAT'),
        ('ict_index', 'FLOAT'),
        ('clearances_blocks_interceptions', 'INTEGER'),
        ('recoveries', 'INTEGER'),
        ('tackles', 'INTEGER'),
        ('defensive_contribution', 'INTEGER'),
        ('starts', 'INTEGER'),
        ('expected_goals', 'FLOAT'),
        ('expected_assists', 'FLOAT'),
        ('expected_goal_involvements', 'FLOAT'),
        ('expected_goals_conceded', 'FLOAT'),
        # first_name, second_name populated during refresh
    ]
}

# Based on actual FPL API data structure for history (current season gameweeks)
PLAYER_PAST_SCHEMA = {
    'columns': [
        ('id', 'SERIAL PRIMARY KEY'),
        ('player_id', 'INTEGER NOT NULL'),  # renamed from 'element' in API
        ('first_name', 'VARCHAR(100)'),
        ('second_name', 'VARCHAR(100)'),
        ('fixture', 'INTEGER'),
        ('opponent_team', 'INTEGER'),
        ('total_points', 'INTEGER'),
        ('was_home', 'BOOLEAN'),
        ('kickoff_time', 'TIMESTAMP'),
        ('team_h_score', 'INTEGER'),
        ('team_a_score', 'INTEGER'),
        ('round', 'INTEGER'),  # gameweek number
        ('modified', 'BOOLEAN'),
        ('minutes', 'INTEGER'),
        ('goals_scored', 'INTEGER'),
        ('assists', 'INTEGER'),
        ('clean_sheets', 'INTEGER'),
        ('goals_conceded', 'INTEGER'),
        ('own_goals', 'INTEGER'),
        ('penalties_saved', 'INTEGER'),
        ('penalties_missed', 'INTEGER'),
        ('yellow_cards', 'INTEGER'),
        ('red_cards', 'INTEGER'),
        ('saves', 'INTEGER'),
        ('bonus', 'INTEGER'),
        ('bps', 'INTEGER'),
        ('influence', 'FLOAT'),
        ('creativity', 'FLOAT'),
        ('threat', 'FLOAT'),
        ('ict_index', 'FLOAT'),
        ('clearances_blocks_interceptions', 'INTEGER'),
        ('recoveries', 'INTEGER'),
        ('tackles', 'INTEGER'),
        ('defensive_contribution', 'INTEGER'),
        ('starts', 'INTEGER'),
        ('expected_goals', 'FLOAT'),
        ('expected_assists', 'FLOAT'),
        ('expected_goal_involvements', 'FLOAT'),
        ('expected_goals_conceded', 'FLOAT'),
        ('value', 'INTEGER'),
        ('transfers_balance', 'INTEGER'),
        ('selected', 'INTEGER'),
        ('transfers_in', 'INTEGER'),
        ('transfers_out', 'INTEGER'),
        # first_name, second_name populated during refresh
    ]
}

# Based on actual FPL API data structure for fixtures (future matches)
PLAYER_FUTURE_SCHEMA = {
    'columns': [
        ('id', 'SERIAL PRIMARY KEY'),  # Auto-generated ID since API doesn't provide fixture id for player-specific data
        ('player_id', 'INTEGER NOT NULL'),  # Added by us for linking
        ('first_name', 'VARCHAR(100)'),
        ('second_name', 'VARCHAR(100)'),
        ('code', 'INTEGER'),
        ('team_h', 'INTEGER'),
        ('team_h_score', 'INTEGER'),
        ('team_a', 'INTEGER'),
        ('team_a_score', 'INTEGER'),
        ('event', 'INTEGER'),  # gameweek
        ('finished', 'BOOLEAN'),
        ('minutes', 'INTEGER'),
        ('provisional_start_time', 'BOOLEAN'),
        ('kickoff_time', 'TIMESTAMP'),
        ('event_name', 'VARCHAR(50)'),
        ('is_home', 'BOOLEAN'),
        ('difficulty', 'INTEGER'),
        # player_id, first_name, second_name moved to top
    ]
}

def get_create_table_sql(table_name: str, schema: dict, if_not_exists: bool = True) -> str:
    """Generate CREATE TABLE SQL from schema definition."""
    columns = []
    for col_name, col_type in schema['columns']:
        columns.append(f"    {col_name} {col_type}")
    
    columns_sql = ",\n".join(columns)
    exists_clause = "IF NOT EXISTS " if if_not_exists else ""
    
    return f"""CREATE TABLE {exists_clause}{table_name} (
{columns_sql}
)"""

def get_column_names(schema: dict) -> list:
    """Get list of column names from schema."""
    return [col_name for col_name, _ in schema['columns']]

def get_column_names_excluding_id(schema: dict) -> list:
    """Get list of column names from schema, excluding auto-generated ID columns."""
    return [col_name for col_name, col_type in schema['columns'] 
            if not ('SERIAL' in col_type or col_name == 'id')]

def validate_dataframe_columns(df, schema: dict, table_name: str) -> None:
    """Validate that DataFrame columns match schema expectations."""
    expected_columns = set(get_column_names_excluding_id(schema))
    actual_columns = set(df.columns)
    
    missing = expected_columns - actual_columns
    extra = actual_columns - expected_columns
    
    if missing:
        print(f"[WARN] {table_name}: Missing columns: {missing}")
    if extra:
        print(f"[WARN] {table_name}: Extra columns (will be ignored): {extra}")

def clean_dataframe_for_schema(df, schema: dict, table_name: str):
    """Clean DataFrame to match schema exactly."""
    expected_columns = get_column_names_excluding_id(schema)
    
    # Reindex to match schema columns exactly, filling missing with None
    cleaned_df = df.reindex(columns=expected_columns, fill_value=None)
    
    # Validate the result
    validate_dataframe_columns(cleaned_df, schema, table_name)
    
    return cleaned_df

# Export all schemas for easy import
ALL_SCHEMAS = {
    'player_history': PLAYER_HISTORY_SCHEMA,
    'player_past': PLAYER_PAST_SCHEMA,
    'player_future': PLAYER_FUTURE_SCHEMA,
}
