# Natural Language to SQL Query Converter for Premier League Data

A web application that converts natural language questions about Premier League soccer data into SQL queries using Google's Gemini AI model.

## Features

- Natural language to SQL query conversion
- Real-time database querying
- Automatic data visualization
- Comprehensive Premier League statistics
- Clean and intuitive user interface

## Prerequisites

- Python 3.8 or higher
- MariaDB server
- Google Gemini API key
- Fantasy Premier League API access

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/natural-language-soccer-query.git
cd natural-language-soccer-query
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up the database:
   - Install MariaDB if not already installed
   - Create a new database named 'fpl'
   - Update the database credentials in `mariadb_access.py`

5. Configure the Gemini API key:
   - Get an API key from Google AI Studio
   - Update the `gemini_api_key` variable in `gemini_api.py`

6. Initialize the database with Premier League data:
```bash
python update_db.py
```

## Usage

### Main Application (Natural Language to SQL)

1. Start the main Flask application:
```bash
python app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

3. Enter your question about Premier League data in the input box
4. Toggle visualization if desired
5. Click "Submit Query" to see the results

### Visualization Gallery (Optional)

1. Start the visualization gallery application:
```bash
cd viz-static-site
python app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5005
```

3. Select from pre-defined visualizations to explore Premier League statistics

## Website Index Files

This repository contains **two separate Flask applications**:

1. **Main Application** (runs on port 5000):
   - Entry point: `app.py`
   - **Index file**: `templates/index.html`
   - Purpose: Natural language to SQL query conversion and database interaction

2. **Visualization Gallery** (runs on port 5005):
   - Entry point: `viz-static-site/app.py`
   - **Index file**: `viz-static-site/templates/index.html`
   - Purpose: Pre-defined visualizations of Premier League data

## Project Structure

```
SportSQL/
├── app.py                  # Main Flask application (port 5000)
├── gemini_api.py           # Gemini API interface
├── mariadb_access.py       # Database access
├── update_db.py            # Database update script
├── static/
│   ├── css/
│   │   └── style.css       # Main app styling
│   └── js/
│       └── main.js         # Main app frontend functionality
├── templates/
│   ├── index.html          # Main application index (PRIMARY)
│   ├── about.html          # About page
│   ├── dataset.html        # Dataset information
│   └── paper.html          # Research paper
└── viz-static-site/        # Visualization Gallery application
    ├── app.py              # Visualization Flask app (port 5005)
    ├── static/
    │   └── plots/          # Generated plot images
    ├── templates/
    │   └── index.html      # Visualization gallery index
    └── *.csv               # Data files for visualizations
```

## Example Queries

- "Who are the top 5 goal scorers this season?"
- "Which team has the most clean sheets?"
- "Show me players with more than 5 assists"
- "What is the average goals per game for each team?"

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Fantasy Premier League API for providing the data
- Google Gemini AI for natural language processing
- Flask framework for web application development 