from flask import Flask, render_template, request, jsonify
import json
import sys
import os
import argparse
from gemini_api import generate_sql, generate_visualization
from mariadb_access import return_query, get_player_id_from_question, update_player_data
from insights_planner import plan_questions_nl
from insights_sql_compiler import compile_questions_to_sql
from player_refresh import refresh_players_with_like_and_llm, cleanup_on_demand_tables
from player_refresh import extract_player_ids_from_refresh_map
from llm_wrapper import get_global_llm
import pandas as pd
from subprocess import run
from matplotlib.colors import ListedColormap
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from db_config import get_db_config, print_db_info

app = Flask(__name__)

@app.route('/')
def index():
    """Render the main page with query input form."""
    return render_template('index.html')

@app.route('/about')
def about():
    """Render the about page."""
    return render_template('about.html')

@app.route('/dataset')
def dataset():
    """Render the dataset information page."""
    return render_template('dataset.html')

@app.route('/paper')
def paper():
    """Render the research paper page."""
    return render_template('paper.html')

@app.route('/gallery')
def gallery():
    """Render the visualization gallery page."""
    options = [
        {'value': 'liverpool_players_expected_assists_vs_goals', 'label': 'Liverpool Players: Expected Assists Per 90 vs Goals per 90'},
        {'value': 'team_avg_difficulty', 'label': 'Average Fixture Difficulty for Team 1'},
        {'value': 'top_5_goals', 'label': 'Top 5 players with the most goals'},
        {'value': 'top_5_assists', 'label': 'Top 5 players with the most assists'},
        {'value': 'top_5_influence', 'label': 'Top 5 players with the most influence'},
        {'value': 'team_standings', 'label': 'Premier League Team Standings By Team Strength'},
        {'value': 'goals_vs_expected_goals', 'label': 'Goals Vs Expected Goals - Erling Haaland'},
        {'value': 'assists_vs_expected_assists', 'label': 'Assists Vs Expected Assists - Cole Palmer'},
    ]
    return render_template('gallery.html', options=options)

def create_gallery_visualization(option):
    # Load the data
    data_path = 'SportSQL/data/'
    players = pd.read_csv(os.path.join(data_path, 'players.csv'))
    teams = pd.read_csv(os.path.join(data_path, 'teams.csv'))
    player_history = pd.read_csv(os.path.join(data_path, 'player_history.csv'))
    player_past = pd.read_csv(os.path.join(data_path, 'player_past.csv'))
    player_future = pd.read_csv(os.path.join(data_path, 'player_future.csv'))
    fixtures = pd.read_csv(os.path.join(data_path, 'fixtures.csv'))

    plot_path = f'static/plots/{option}.png'
    os.makedirs('static/plots', exist_ok=True)

    if option == 'liverpool_players_expected_assists_vs_goals':
        filtered_players = players[players['expected_assists_per_90'] > players['goals_per_90']]
        filtered_players = filtered_players[filtered_players['team_name'] == 'Liverpool']
        filtered_players = filtered_players.sort_values(by='expected_assists_per_90', ascending=False)
        filtered_top5 = filtered_players[['web_name', 'expected_assists_per_90', 'goals_per_90']].head(5)
        plt.figure(figsize=(10, 6))
        filtered_top5.set_index('web_name').plot(kind='bar', stacked=True)
        plt.title('Top 5 Players: Expected Assists vs. Goals per 90 Minutes')
        plt.ylabel('Values')
        plt.xlabel('Player')
        plt.legend(['Expected Assists per 90', 'Goals per 90'])
        plt.tight_layout()
        plt.savefig(plot_path)
        plt.close()

    elif option == 'team_avg_difficulty':
        avg_difficulty = fixtures[(fixtures['team_h'] == 1) | (fixtures['team_a'] == 1) & ~fixtures['finished']].team_a_difficulty.mean()
        plt.figure(figsize=(6, 6))
        plt.bar(['Team 1'], [avg_difficulty], color='blue')
        plt.title('Average Fixture Difficulty for Team 1')
        plt.ylabel('Average Difficulty')
        plt.savefig(plot_path)
        plt.close()

    elif option == 'top_5_goals':
        filtered_players = players.sort_values(by='goals_scored', ascending=False)
        filtered_top5 = filtered_players[['web_name', 'goals_scored']].head(5)
        plt.figure(figsize=(10, 6))
        filtered_top5.set_index('web_name').plot(kind='bar', stacked=True)
        plt.title('Top 5 Players: Goals')
        plt.ylabel('Goals')
        plt.xlabel('Player')
        plt.legend(['Goals'])
        plt.tight_layout()
        plt.savefig(plot_path)
        plt.close()

    elif option == 'top_5_assists':
        filtered_players = players.sort_values(by='assists', ascending=False)
        filtered_top5 = filtered_players[['web_name', 'assists']].head(5)
        plt.figure(figsize=(10, 6))
        filtered_top5.set_index('web_name').plot(kind='bar', stacked=True)
        plt.title('Top 5 Players: Assists')
        plt.ylabel('Assists')
        plt.xlabel('Player')
        plt.legend(['Assists'])
        plt.tight_layout()
        plt.savefig(plot_path)
        plt.close()

    elif option == 'top_5_influence':
        filtered_players = players.sort_values(by='influence', ascending=False)
        filtered_top5 = filtered_players[['web_name', 'influence']].head(5)
        plt.figure(figsize=(10, 6))
        filtered_top5.set_index('web_name').plot(kind='bar', stacked=True)
        plt.title('Top 5 Players: Influence')
        plt.ylabel('Influence')
        plt.xlabel('Player')
        plt.legend(['Influence'])
        plt.tight_layout()
        plt.savefig(plot_path)
        plt.close()

    elif option == 'team_standings':
        plt.figure(figsize=(10, 6))
        min_strength = teams['strength'].min()
        max_strength = teams['strength'].max()
        normalized_strength = (teams['strength'] - min_strength) / (max_strength - min_strength)
        cmap = plt.get_cmap('YlGnBu')
        half_cmap = ListedColormap(cmap(np.linspace(0.3, 1, 256)))
        plt.scatter(teams['position'], teams['points'], c=normalized_strength, cmap=half_cmap, s=50, alpha=0.8)
        plt.title('Premier League Team Standings')
        plt.ylabel('Points')
        plt.xlabel('Position')
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.legend(['strength'])
        plt.tight_layout()
        plt.savefig(plot_path)
        plt.close()

    elif option == 'goals_vs_expected_goals':
        plt.figure(figsize=(10, 6))
        colors = ['orange' if player == 'Haaland' else 'blue' for player in players['second_name']]
        plt.scatter(players['expected_goals'], players['goals_scored'], c=colors, s=50, alpha=0.8)
        plt.title('Goals Scored vs Expected Goals', fontsize=14)
        plt.ylabel('Goals Scored', fontsize=12)
        plt.xlabel('Expected Goals', fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.5)
        haaland = players[players['second_name'] == 'Haaland']
        if not haaland.empty:
            plt.annotate('Erling Haaland', 
                        (haaland['expected_goals'].values[0], haaland['goals_scored'].values[0]), 
                        textcoords="offset points", 
                        xytext=(10, -10), 
                        ha='center', 
                        color='orange', 
                        fontsize=10)
        plt.tight_layout()
        plt.savefig(plot_path)
        plt.close()

    elif option == 'assists_vs_expected_assists':
        plt.figure(figsize=(10, 6))
        colors = ['orange' if player == 'Palmer' else 'blue' for player in players['second_name']]
        plt.scatter(players['expected_assists'], players['assists'], c=colors, s=50, alpha=0.8)
        plt.title('Assists vs Expected Assists', fontsize=14)
        plt.ylabel('Assists', fontsize=12)
        plt.xlabel('Expected Assists', fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.5)
        haaland = players[players['second_name'] == 'Palmer']
        if not haaland.empty:
            plt.annotate('Cole Palmer', 
                        (haaland['expected_assists'].values[0], haaland['assists'].values[0]), 
                        textcoords="offset points", 
                        xytext=(10, -10), 
                        ha='center', 
                        color='orange', 
                        fontsize=10)
        plt.tight_layout()
        plt.savefig(plot_path)
        plt.close()

    return plot_path

@app.route('/query', methods=['POST'])
def process_query():
    """Process natural language query and return results."""
    try:
        # Get query and visualization flag from request
        data = request.get_json()
        query = data.get('query', '')
        generate_viz = data.get('visualization', False)
        mode = (data.get('mode') or 'direct').lower()
        print(f"Received query: '{query}', Generate viz: {generate_viz}")

        if not query:
            return jsonify({'error': 'No query provided'}), 400
            
        # Direct mode: legacy single-shot NL->SQL->execute
        if mode == 'direct':
            # Step 1: Check if query contains a player name and update tables if needed
            player_id = get_player_id_from_question(query)
            if player_id > 0:
                print(f"Player ID {player_id} found, updating data...")
                update_success = update_player_data(player_id)
                if not update_success:
                    print("Failed to update player data.")
                    return jsonify({'error': 'Failed to update player data'}), 500
            #Step 2: Convert natural language to SQL
            print("Generating SQL...")
            sql_query = generate_sql(query)
            if not sql_query:
                print("Failed to generate SQL.")
                return jsonify({'error': 'Failed to generate SQL query'}), 500
            print(f"Generated SQL: {sql_query}")
            # Step 3: Execute SQL query against database
            print("Executing database query...")
            db_result = return_query(sql_query)
            if not db_result:
                print("Database query failed.")
                return jsonify({'error': 'Database query failed'}), 500
            print(f"DB Result (raw string, first 200 chars): {db_result[:200]}")
            # Parse the database result
            result_data = json.loads(db_result)
            print(f"Parsed DB data type: {type(result_data)}")
            # Step 4: Generate visualization if requested
            viz_code = None
            if generate_viz and result_data.get('rows'):
                print("Generating visualization...")
                viz_code = generate_visualization(query, result_data)
                print(f"Visualization code generated: {viz_code}")
            response_payload = {
                'mode': 'direct',
                'sql': sql_query,
                'data': result_data,
                'visualization': viz_code
            }
            print(f"Final response payload: {response_payload}")
            return jsonify(response_payload)

        # Deep mode: plan -> populate -> compile -> execute
        # Determine server type from argv (default remote)
        server_type = 'remote'
        try:
            argsline = ' '.join(sys.argv)
            if '--server local' in argsline:
                server_type = 'local'
        except Exception:
            pass

        # 1) Extract entities with a lightweight LLM call (players/teams full names)
        print("[DEEP] Extracting entities with LLM...")
        extracted_entities = {"players": [], "teams": []}
        try:
            llm = get_global_llm()
            extract_prompt = (
                "You are an information extraction assistant.\n"
                "Task: From the USER QUESTION below, extract full names of Premier League players and teams.\n"
                "Return STRICT JSON with keys 'players' and 'teams' only.\n"
                "- players: array of full player names (e.g., ['Erling Haaland', 'Mohamed Salah'])\n"
                "- teams: array of full team names (e.g., ['Manchester City', 'Liverpool'])\n"
                "Do not include any extra fields or text.\n\n"
                f"USER QUESTION: {query}"
            )
            raw = llm.generate_content(extract_prompt, timeout=20)
            # Try direct json parse; if fails, find first {...}
            try:
                parsed = json.loads(raw)
            except Exception:
                s = raw.strip()
                start = s.find('{')
                end = s.rfind('}')
                parsed = json.loads(s[start:end+1]) if start != -1 and end != -1 else {}
            if isinstance(parsed, dict):
                pl = parsed.get('players') or []
                tm = parsed.get('teams') or []
                if isinstance(pl, list):
                    extracted_entities['players'] = [str(x).strip() for x in pl if str(x).strip()]
                if isinstance(tm, list):
                    extracted_entities['teams'] = [str(x).strip() for x in tm if str(x).strip()]
        except Exception as e:
            print(f"[DEEP] Entity extraction failed: {e}")

        print(f"[DEEP] Extracted entities: {json.dumps(extracted_entities, ensure_ascii=False)}")

        # 2) Plan NL sub-questions (seed planner with extracted entities)
        print("[DEEP] Planning deep analysis...")
        plan = plan_questions_nl(query, entities=extracted_entities, server_type=server_type)
        entities = plan.get('entities') or {}
        questions = plan.get('questions') or []
        print(f"[DEEP] Planner entities: {json.dumps(entities, ensure_ascii=False)}")
        print(f"[DEEP] Planner produced {len(questions)} subqueries:")
        for sq in questions:
            try:
                print(f"  - {sq.get('id')} :: {sq.get('question')}")
            except Exception:
                pass

        # 3) Populate on-demand tables for all relevant entities (batch)
        print("Populating on-demand tables for entities...")
        refresh_map = refresh_players_with_like_and_llm(entities, include_debug=False)
        # Extract player_ids (if resolved) and pass to compiler
        resolved_ids = extract_player_ids_from_refresh_map(refresh_map)
        if resolved_ids:
            ents_for_compile = dict(entities)
            ents_for_compile['player_ids'] = resolved_ids
        else:
            ents_for_compile = entities

        # 4) Compile sub-questions to SQL
        compiled = compile_questions_to_sql(questions, ents_for_compile, server_type=server_type)
        print(f"[DEEP] Compiled {len(compiled or [])} subqueries:")
        for qc in compiled or []:
            sql_text_dbg = (qc.get('sql') or '').strip()
            head = sql_text_dbg[:220] + ("..." if len(sql_text_dbg) > 220 else "")
            print(f"  >> {qc.get('id')} valid={qc.get('valid')} notes={qc.get('notes')}\n     SQL: {head if head else '[EMPTY]'}")

        # 5) Execute each SQL
        subq_results = []
        for qc in compiled or []:
            sql_text = qc.get('sql') or ''
            exec_out = {'success': False, 'error': 'empty sql', 'data': None, 'row_count': 0}
            if sql_text and qc.get('valid'):
                raw = return_query(sql_text)
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict) and 'error' not in parsed:
                        exec_out = {
                            'success': True,
                            'error': None,
                            'data': {
                                'headers': parsed.get('headers', []),
                                'rows': parsed.get('rows', [])
                            },
                            'row_count': len(parsed.get('rows') or [])
                        }
                    else:
                        exec_out = {'success': False, 'error': parsed.get('error'), 'data': None, 'row_count': 0}
                except Exception as ex:
                    exec_out = {'success': False, 'error': str(ex), 'data': None, 'row_count': 0}

            subq_results.append({
                'id': qc.get('id'),
                'question': qc.get('question'),
                'table_hint': None,
                'sql': sql_text,
                'valid': qc.get('valid', False),
                'notes': qc.get('notes', []),
                'execution': exec_out
            })

        response_payload = {
            'mode': 'deep',
            'question': query,
            'entities': entities,
            'subqueries': subq_results
        }
        return jsonify(response_payload)
        player_id = get_player_id_from_question(query)
        if player_id > 0:
            print(f"Player ID {player_id} found, updating data...")
            update_success = update_player_data(player_id)
            if not update_success:
                print("Failed to update player data.")
                return jsonify({'error': 'Failed to update player data'}), 500
            
        #Step 2: Convert natural language to SQL
        print("Generating SQL...")
        sql_query = generate_sql(query)
        if not sql_query:
            print("Failed to generate SQL.")
            return jsonify({'error': 'Failed to generate SQL query'}), 500
        print(f"Generated SQL: {sql_query}")
            
        # Step 3: Execute SQL query against database
        print("Executing database query...")
        db_result = return_query(sql_query)
        if not db_result:
            print("Database query failed.")
            return jsonify({'error': 'Database query failed'}), 500
        print(f"DB Result (raw string, first 200 chars): {db_result[:200]}")
            
        # Parse the database result
        result_data = json.loads(db_result)
        print(f"Parsed DB data type: {type(result_data)}")
        
        # Step 4: Generate visualization if requested
        viz_code = None
        if generate_viz and result_data.get('rows'):
            print("Generating visualization...")
            viz_code = generate_visualization(query, result_data)
            print(f"Visualization code generated: {viz_code}")
            
        response_payload = {
            'sql': sql_query,
            'data': result_data,
            'visualization': viz_code
        }
        print(f"Final response payload: {response_payload}")
        return jsonify(response_payload)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        # Ensure cleanup for deep mode as well
        try:
            cleanup_on_demand_tables()
        except Exception:
            pass

@app.route('/visualize', methods=['POST'])
def visualize():
    try:
        data = request.json
        query = data.get('query')
        result_data = data.get('resultData')
        
        if not query or not result_data:
            return jsonify({'error': 'Missing query or result data'}), 400
            
        # Generate visualization and save to static/visualization.png
        success = generate_visualization(query, result_data)
        
        if not success:
            return jsonify({'error': 'Failed to generate visualization'}), 500
            
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error in visualization route: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/gallery/visualize', methods=['POST'])
def gallery_visualize():
    try:
        data = request.get_json()
        selected_option = data.get('visualization')
        if not selected_option:
            return jsonify({'error': 'No visualization option provided'}), 400
        plot_path = create_gallery_visualization(selected_option)
        return jsonify({'plot_path': '/' + plot_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/update-db', methods=['POST'])
def update_db():
    """Run update_db.py and return status."""
    try:
        result = run(['python', 'update_db.py'], capture_output=True, text=True)
        if result.returncode == 0:
            return jsonify({'success': True, 'message': 'Database updated successfully.'})
        else:
            return jsonify({'success': False, 'message': result.stderr}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='SportSQL Application')
    parser.add_argument('--server', 
                       choices=['local', 'remote'], 
                       default='remote',
                       help='Database server type: local (PostgreSQL) or remote (MySQL)')
    parser.add_argument('--debug', 
                       action='store_true', 
                       default=True,
                       help='Run Flask in debug mode')
    parser.add_argument('--port', 
                       type=int, 
                       default=5000,
                       help='Port to run the Flask application')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_arguments()
    
    # Initialize database configuration
    db_config = get_db_config(args.server)
    
    # Print database information
    print("=" * 50)
    print("SportSQL Application Starting")
    print("=" * 50)
    print_db_info()
    print("=" * 50)
    
    # Run Flask application
    app.run(debug=args.debug, port=args.port)
