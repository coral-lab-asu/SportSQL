from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import os

# Initialize Flask app
app = Flask(__name__)

# Load the data
players = pd.read_csv('players.csv')
teams = pd.read_csv('teams.csv')
player_history = pd.read_csv('player_history.csv')
player_past = pd.read_csv('player_past.csv')
player_future = pd.read_csv('player_future.csv')
fixtures = pd.read_csv('fixtures.csv')

# Ensure static/plots folder exists
os.makedirs('static/plots', exist_ok=True)

# Function to generate plots
def create_visualization(option):
    plot_path = f'static/plots/{option}.png'

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
        #plt.xticks(fontsize=10)
        #plt.yticks(fontsize=10)
        plt.legend(['strength'])
        plt.tight_layout()
        plt.savefig(plot_path)
        plt.close()

    elif option == 'goals_vs_expected_goals':
        plt.figure(figsize=(10, 6))
        
        # Define colors for all players (default blue) and highlight Erling Haaland in orange
        colors = ['orange' if player == 'Haaland' else 'blue' for player in players['second_name']]
        plt.scatter(players['expected_goals'], players['goals_scored'], c=colors, s=50, alpha=0.8)
        plt.title('Goals Scored vs Expected Goals', fontsize=14)
        plt.ylabel('Goals Scored', fontsize=12)
        plt.xlabel('Expected Goals', fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.5)
        
        # Add annotation for Erling Haaland
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
        
        # Define colors for all players (default blue) and highlight Erling Haaland in orange
        colors = ['orange' if player == 'Palmer' else 'blue' for player in players['second_name']]
        plt.scatter(players['expected_assists'], players['assists'], c=colors, s=50, alpha=0.8)
        plt.title('Assists vs Expected Assists', fontsize=14)
        plt.ylabel('Assists', fontsize=12)
        plt.xlabel('Expected Assists', fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.5)
        
        # Add annotation for Erling Haaland
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

@app.route('/')
def index():
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
    return render_template('index.html', options=options)

@app.route('/visualize', methods=['POST'])
def visualize():
    try:
        data = request.get_json()
        selected_option = data.get('visualization')
        if not selected_option:
            return jsonify({'error': 'No visualization option provided'}), 400
        plot_path = create_visualization(selected_option)
        return jsonify({'plot_path': '/' + plot_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    #app.run(debug=True)
    app.run(host='127.0.0.1', port=5005, debug=True)
