# SportSQL - Natural Language to SQL Query Converter for Premier League Data

A powerful web application that converts natural language questions about Premier League soccer data into SQL queries using Google's Gemini AI model. Features dual database support for cost-effective local development and production deployment.

## ✨ Features

- **Natural Language Processing**: Convert plain English questions to SQL queries
- **Dual Database Support**: PostgreSQL for local development, MySQL for production
- **Real-time Querying**: Instant database queries with live results
- **Automatic Visualization**: Generate charts and graphs from query results
- **Comprehensive Statistics**: Access to complete Premier League data
- **Cost-Effective Development**: Free local database for development
- **Production Ready**: Optimized for GCP Cloud Run deployment

## 🏗️ Architecture

| Environment           | Database          | Cost        | Use Case               |
| --------------------- | ----------------- | ----------- | ---------------------- |
| **Local Development** | PostgreSQL        | Free        | Development, Testing   |
| **Production/GCP**    | MySQL (Cloud SQL) | Pay-per-use | Production, Deployment |

## 📋 Prerequisites

- **Python 3.10+ < 3.12 **
- **Conda** (recommended) or Python venv
- **PostgreSQL** (for local development)
- **Google Gemini API key**
- **Git**

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/SportSQL.git
cd SportSQL
```

### 2. Set Up Conda Environment (Recommended)

#### Option A: Using environment.yml (Easiest)

```bash
# Create environment from file (includes all dependencies)
conda env create -f environment.yml

# Activate environment
conda activate sportsql
```

#### Option B: Manual setup

```bash
# Create conda environment
conda create -n sportsql python=3.11

# Activate environment
conda activate sportsql

# Install dependencies
pip install -r requirements.txt
```

### 3. Install PostgreSQL (Local Development)

#### macOS (using Homebrew)

```bash
brew install postgresql@15
brew services start postgresql@15
echo 'export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

#### Ubuntu/Debian

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### Windows

Download and install from [PostgreSQL official website](https://www.postgresql.org/download/windows/)

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Local PostgreSQL Configuration (for development)
LOCAL_DATABASE_HOST=localhost
LOCAL_DATABASE_PORT=5432
LOCAL_DATABASE_USER=your_username
LOCAL_DATABASE_PASSWORD=
LOCAL_DATABASE_NAME=postgres

# Remote MySQL Configuration (for production)
DATABASE_HOST=your_gcp_host
DATABASE_USER=your_gcp_user
DATABASE_NAME=your_gcp_database
DATABASE_PORT=3306
DATABASE_PASSWORD=your_gcp_password

# Google Gemini API
API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash
```

### 5. Set Up Local Database

```bash
# Run the automated setup script
python setup_local_db.py

# This will:
# - Create all necessary tables
# - Populate with fresh Premier League data
# - Set up the complete database schema
```

## 🎯 Usage

### Local Development (Recommended)

```bash
# Activate conda environment
conda activate sportsql

# Start with local PostgreSQL database
python app.py --server local

# Open browser to http://localhost:5000
```

### Production Testing

```bash
# Test with remote MySQL database
python app.py --server remote
```

### Environment Management with Conda

```bash
# Create environment with specific Python version
conda create -n sportsql python=3.11

# Activate environment
conda activate sportsql

# Install additional packages if needed
conda install pandas numpy matplotlib

# Deactivate when done
conda deactivate

# Remove environment if needed
conda env remove -n sportsql
```

## 📁 Project Structure

```
SportSQL/
├── app.py                  # Main Flask application (updated)
├── db_config.py           # Database configuration manager (new)
├── setup_local_db.py      # Local database setup script (new)
├── mariadb_access.py      # Database access layer (updated)
├── gemini_api.py          # Gemini API integration (updated)
├── update_db.py           # Database update script (updated)
├── requirements.txt       # Python dependencies (updated)
├── Dockerfile             # Docker configuration (updated)
├── cloudbuild.yml         # GCP deployment config (updated)
├── LOCAL_SETUP.md         # Detailed local setup guide
├── .env                   # Environment variables (create this)
├── data/                  # CSV data files
├── static/                # Web assets (CSS, JS, images)
├── templates/             # HTML templates
└── prompts/               # AI prompt templates
```

## 💬 Example Queries

Try these natural language questions:

- **Player Stats**: "Who are the top 5 goal scorers this season?"
- **Team Performance**: "Which team has the most clean sheets?"
- **Specific Queries**: "Show me players with more than 5 assists"
- **Analytics**: "What is the average goals per game for each team?"
- **Comparisons**: "Compare Liverpool and Manchester City's performance"
- **Advanced**: "Show me players who have more expected goals than actual goals"

## 🛠️ Advanced Configuration

### Database Management

```bash
# Refresh local database with latest data
python setup_local_db.py

# Update remote database (production)
python update_db.py --server remote

# Test database connections
python -c "from db_config import print_db_info; print_db_info()"
```

### Deployment Options

#### Local Development

- Uses PostgreSQL (free)
- Fast queries (no network latency)
- Full offline development

#### Production (GCP Cloud Run)

- Uses MySQL Cloud SQL
- Automatic scaling
- Production-grade reliability
- Configured via `cloudbuild.yml`

## 🚨 Troubleshooting

### Common Issues

1. **PostgreSQL Connection Failed**

   ```bash
   # Check if PostgreSQL is running
   brew services list | grep postgresql

   # Start PostgreSQL
   brew services start postgresql@15
   ```

2. **Module Not Found Errors**

   ```bash
   # Ensure conda environment is activated
   conda activate sportsql

   # Reinstall dependencies
   pip install -r requirements.txt
   ```

3. **Database Setup Issues**

   ```bash
   # Re-run database setup
   python setup_local_db.py

   # Check database configuration
   python -c "from db_config import get_db_config; print(get_db_config('local').get_database_info())"
   ```

4. **API Key Issues**
   - Verify your Gemini API key in `.env`
   - Check API key permissions in Google AI Studio

### Environment Variables

Make sure your `.env` file exists and contains all required variables:

```bash
# Check if .env file exists
ls -la .env

# Verify environment variables are loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('API_KEY loaded:', bool(os.getenv('API_KEY')))"
```

## 🚀 Production Deployment

### Google Cloud Platform

1. **Prerequisites**:

   - GCP account with billing enabled
   - Cloud SQL MySQL instance
   - Cloud Run API enabled

2. **Deploy**:

   ```bash
   # Build and deploy using Cloud Build
   gcloud builds submit --config cloudbuild.yml
   ```

3. **Environment Variables**: Already configured in `cloudbuild.yml`

## 🔧 Development Workflow

1. **Daily Development**:

   ```bash
   conda activate sportsql
   python app.py --server local
   ```

2. **Testing with Production Data**:

   ```bash
   python app.py --server remote
   ```

3. **Database Updates**:
   ```bash
   python setup_local_db.py  # Local refresh
   python update_db.py --server remote  # Production update
   ```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Set up conda environment (`conda create -n sportsql-dev python=3.11`)
4. Make your changes and test locally
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Fantasy Premier League API** for providing comprehensive soccer data
- **Google Gemini AI** for advanced natural language processing
- **Flask** framework for robust web application development
- **PostgreSQL** and **MySQL** for reliable database solutions
- **Google Cloud Platform** for scalable deployment infrastructure

## 📚 Additional Resources

- [LOCAL_SETUP.md](LOCAL_SETUP.md) - Detailed local development setup
- [Fantasy Premier League API Documentation](https://fantasy.premierleague.com/api/)
- [Google Gemini AI Documentation](https://ai.google.dev/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Conda Documentation](https://docs.conda.io/)
