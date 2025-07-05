from flask import Flask, render_template, request, jsonify
import json
import sys
import os
from gemini_api import generate_sql, generate_visualization
from mariadb_access import return_query, get_player_id_from_question, update_player_data
import pandas as pd
from subprocess import run

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

@app.route('/query', methods=['POST'])
def process_query():
    """Process natural language query and return results."""
    try:
        # Get query and visualization flag from request
        data = request.get_json()
        query = data.get('query', '')
        generate_viz = data.get('visualization', False)
        
        if not query:
            return jsonify({'error': 'No query provided'}), 400
            
        # Step 1: Check if query contains a player name and update tables if needed
        player_id = get_player_id_from_question(query)
        if player_id > 0:
            # Update player data tables before proceeding
            update_success = update_player_data(player_id)
            if not update_success:
                return jsonify({'error': 'Failed to update player data'}), 500
            
        # Step 2: Convert natural language to SQL
        sql_query = generate_sql(query)
        if not sql_query:
            return jsonify({'error': 'Failed to generate SQL query'}), 500
            
        # Step 3: Execute SQL query against database
        db_result = return_query(sql_query)
        if not db_result:
            return jsonify({'error': 'Database query failed'}), 500
            
        # Parse the database result
        result_data = json.loads(db_result)
        
        # Step 4: Generate visualization if requested
        viz_code = None
        if generate_viz and result_data.get('rows'):
            viz_code = generate_visualization(query, result_data)
            
        return jsonify({
            'sql': sql_query,
            'data': result_data,
            'visualization': viz_code
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

if __name__ == '__main__':
    app.run(debug=True)