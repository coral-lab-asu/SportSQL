#!/usr/bin/env python3
"""
📊 Schema Summary for LLM Context

This module provides a concise schema summary for the LLM to understand
the database structure. Now uses master schemas as the source of truth.

Note: History tables (player_history, player_past, player_future) do NOT
contain first_name/second_name columns. Use JOINs with players table for names.
"""

from schemas import get_column_names, ALL_SCHEMAS

def generate_schema_summary():
    """Generate schema summary from master schemas."""
    
    # Static schemas (not generated from master schemas)
    static_schemas = {
        'players': [
            'player_id', 'first_name', 'second_name', 'web_name', 'player_position',
            'team_id', 'team_name', 'minutes', 'starts', 'goals_scored', 'assists',
            'goals_conceded', 'saves', 'clean_sheets',
            'goals_per_90', 'assists_per_90', 'goals_conceded_per_90', 'saves_per_90', 'clean_sheets_per_90',
            'expected_goals', 'expected_assists', 'expected_goal_involvements', 'expected_goals_conceded',
            'expected_goals_per_90', 'expected_assists_per_90', 'expected_goal_involvements_per_90', 'expected_goals_conceded_per_90',
            'ict_index', 'influence', 'creativity', 'threat',
            'total_points', 'points_per_game', 'form'
        ],
        'teams': [
            'team_id', 'team_name', 'short_name',
            'position', 'played', 'win', 'draw', 'loss', 'points', 'strength'
        ],
        'fixtures': [
            'game_id', 'gw', 'finished',
            'team_h', 'team_h_name', 'team_h_score',
            'team_a', 'team_a_name', 'team_a_score',
            'kickoff_time', 'team_h_difficulty', 'team_a_difficulty'
        ]
    }
    
    # Generate dynamic schemas from master schemas
    dynamic_schemas = {}
    for table_name, schema in ALL_SCHEMAS.items():
        columns = get_column_names(schema)
        dynamic_schemas[table_name] = columns
    
    # Build summary
    summary_parts = []
    
    # Add static schemas
    for table_name, columns in static_schemas.items():
        summary_parts.append(f"{table_name}: [\n  {', '.join(columns)}\n]")
    
    # Add dynamic schemas with notes
    for table_name, columns in dynamic_schemas.items():
        note = ""
        if table_name in ['player_history', 'player_past', 'player_future']:
            note = f"  // NO first_name/second_name - JOIN with players table for names\n  // {get_table_description(table_name)}"
        
        summary_parts.append(f"{table_name}: [\n  {', '.join(columns)}\n{note}\n]")
    
    return "\n\n".join(summary_parts)

def get_table_description(table_name):
    """Get description for table."""
    descriptions = {
        'player_history': 'one row per season per player (historical seasons)',
        'player_past': 'one row per match this season for a player (completed matches)',
        'player_future': 'one row per upcoming match for a player (future fixtures)'
    }
    return descriptions.get(table_name, '')

# Generate the schema summary
SCHEMA_SUMMARY = generate_schema_summary()
