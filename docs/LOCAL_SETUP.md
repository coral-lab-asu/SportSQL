# SportSQL Local Development Setup

This guide will help you set up SportSQL for local development using PostgreSQL instead of the expensive GCP MySQL database.

## Prerequisites

1. **Python 3.8+**
2. **PostgreSQL** (local installation)
3. **Git**

## Quick Setup

### 1. Install PostgreSQL

#### macOS (using Homebrew)

```bash
brew install postgresql
brew services start postgresql
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

### 2. Create Local Database

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE sportsql_local;
CREATE USER sportsql_user WITH PASSWORD 'your_local_password';
GRANT ALL PRIVILEGES ON DATABASE sportsql_local TO sportsql_user;
\q
```

### 3. Set Up Environment Variables

Create a `.env` file in the SportSQL directory:

```bash
# Local PostgreSQL Configuration
LOCAL_DATABASE_HOST=localhost
LOCAL_DATABASE_PORT=5432
LOCAL_DATABASE_USER=sportsql_user
LOCAL_DATABASE_PASSWORD=your_local_password
LOCAL_DATABASE_NAME=sportsql_local

# Remote MySQL Configuration (keep existing for production)
DATABASE_HOST=35.184.21.229
DATABASE_USER=naman
DATABASE_NAME=sport-sql
DATABASE_PORT=3306
DATABASE_PASSWORD=your_gcp_password

# Gemini API
API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Set Up Local Database

Run the setup script to create tables and populate data:

```bash
python setup_local_db.py
```

This script will:

- Create all necessary tables in PostgreSQL
- Populate them with fresh data from the Fantasy Premier League API
- Set up the database schema compatible with your application

## Usage

### Local Development (PostgreSQL)

```bash
python app.py --server local
```

### Production/Testing (GCP MySQL)

```bash
python app.py --server remote
```

### Database Management

#### Populate/Update Local Data

```bash
python setup_local_db.py
```

#### Update Remote Data (as before)

```bash
python update_db.py --server remote
```

## Configuration Details

The application now supports two database configurations:

### Local Configuration

- **Database**: PostgreSQL
- **Host**: localhost
- **Port**: 5432
- **Cost**: Free
- **Performance**: Fast (no network latency)
- **Use Case**: Development, testing

### Remote Configuration

- **Database**: MySQL (GCP)
- **Host**: 35.184.21.229
- **Port**: 3306
- **Cost**: Pay per use
- **Performance**: Network dependent
- **Use Case**: Production, deployment

## Troubleshooting

### PostgreSQL Connection Issues

1. **Check if PostgreSQL is running:**

```bash
# macOS
brew services list | grep postgresql

# Linux
sudo systemctl status postgresql
```

2. **Verify database exists:**

```bash
psql -h localhost -U sportsql_user -d sportsql_local -c "SELECT version();"
```

3. **Check environment variables:**

```bash
python -c "from db_config import get_db_config; print(get_db_config('local').get_database_info())"
```

### Common Issues

1. **"psycopg2 not found"**: Install with `pip install psycopg2-binary`
2. **"database does not exist"**: Run the database creation commands above
3. **"permission denied"**: Check PostgreSQL user permissions
4. **"connection refused"**: Ensure PostgreSQL service is running

### Switching Between Databases

The application automatically detects the `--server` flag:

```bash
# Use local PostgreSQL
python app.py --server local --port 5000

# Use remote MySQL
python app.py --server remote --port 5000

# Default is remote for backward compatibility
python app.py
```

## Development Workflow

1. **Start local development:**

   ```bash
   python app.py --server local
   ```

2. **Test with fresh data:**

   ```bash
   python setup_local_db.py  # Refresh local data
   python app.py --server local
   ```

3. **Test production setup:**

   ```bash
   python app.py --server remote
   ```

4. **Deploy to production:**
   - Use existing deployment process
   - Application defaults to remote database
   - No changes needed for production deployment

## Benefits of This Setup

✅ **Cost Savings**: No GCP charges during development  
✅ **Speed**: Local database = faster queries  
✅ **Offline Development**: Work without internet  
✅ **Easy Testing**: Quick database resets  
✅ **Production Parity**: Same application code  
✅ **Flexible**: Switch between local/remote anytime

## File Structure

```
SportSQL/
├── app.py                 # Main Flask application (updated)
├── db_config.py          # Database configuration manager (new)
├── setup_local_db.py     # Local database setup script (new)
├── mariadb_access.py     # Database access layer (updated)
├── gemini_api.py         # Gemini API integration (updated)
├── update_db.py          # Database update script (updated)
├── requirements.txt      # Dependencies (updated)
├── LOCAL_SETUP.md        # This setup guide (new)
└── .env                  # Environment variables (create)
```

## Next Steps

1. Follow the setup steps above
2. Test local development with `python app.py --server local`
3. Verify all features work with local PostgreSQL
4. Continue development with cost-free local database
5. Use `--server remote` only when you need production data

For questions or issues, check the troubleshooting section above.
