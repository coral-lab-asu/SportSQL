#!/usr/bin/env python3
"""
Quick script to extract player and team IDs from the local database.
Creates mappings for debugging evaluation results.
"""

import os
import sys
import json

# Force local database usage
if 'FORCE_REMOTE_DB' in os.environ:
    del os.environ['FORCE_REMOTE_DB']

if '--server' not in sys.argv:
    sys.argv.extend(['--server', 'local'])

from mariadb_access import run_sql

def extract_mappings():
    """Extract player and team ID mappings from database."""
    print("🔍 Extracting player and team ID mappings...")
    
    # Extract players
    print("📋 Fetching players...")
    headers, rows = run_sql("SELECT player_id, first_name, second_name, web_name, team_name FROM players ORDER BY player_id")
    
    player_map = {}
    for row in rows:
        player_id, first_name, second_name, web_name, team_name = row
        full_name = f"{first_name} {second_name}".strip()
        
        player_map[player_id] = {
            'first_name': first_name,
            'second_name': second_name, 
            'web_name': web_name,
            'full_name': full_name,
            'team_name': team_name
        }
    
    print(f"✅ Found {len(player_map)} players")
    
    # Extract teams
    print("🏟️  Fetching teams...")
    headers, rows = run_sql("SELECT team_id, team_name, short_name FROM teams ORDER BY team_id")
    
    team_map = {}
    for row in rows:
        team_id, team_name, short_name = row
        team_map[team_id] = {
            'team_name': team_name,
            'short_name': short_name
        }
    
    print(f"✅ Found {len(team_map)} teams")
    
    # Save to JSON files
    with open('player_id_map.json', 'w') as f:
        json.dump(player_map, f, indent=2)
    
    with open('team_id_map.json', 'w') as f:
        json.dump(team_map, f, indent=2)
    
    print(f"💾 Saved mappings to player_id_map.json and team_id_map.json")
    
    # Print some examples
    print("\n📝 Sample player mappings:")
    for i, (player_id, info) in enumerate(list(player_map.items())[:5]):
        print(f"  {player_id}: {info['full_name']} ({info['team_name']})")
    
    print("\n🏟️  Sample team mappings:")
    for team_id, info in list(team_map.items())[:5]:
        print(f"  {team_id}: {info['team_name']} ({info['short_name']})")
    
    # Search for specific players mentioned in test
    print("\n🔍 Looking for test case players:")
    for player_id, info in player_map.items():
        if 'Palmer' in info['second_name']:
            print(f"  Cole Palmer: ID {player_id} - {info['full_name']} ({info['team_name']})")
        if 'Dijk' in info['second_name']:
            print(f"  Van Dijk: ID {player_id} - {info['full_name']} ({info['team_name']})")

if __name__ == "__main__":
    extract_mappings()
