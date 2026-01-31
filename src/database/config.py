"""
Database configuration module for SportSQL application.
Handles switching between local PostgreSQL and remote MySQL databases.
"""

import os
from urllib.parse import quote_plus
import argparse
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

class DatabaseConfig:
    """Database configuration manager for local/remote database switching."""
    
    def __init__(self, server_type=None):
        """
        Initialize database configuration.
        
        Args:
            server_type (str): 'local' for PostgreSQL, 'remote' for MySQL, None for auto-detect
        """
        self.server_type = server_type or self._detect_server_type()
        self._validate_config()
    
    def _detect_server_type(self):
        """Auto-detect server type from command line arguments or environment."""
        # Check if we're in a production/containerized environment
        if os.getenv('FORCE_REMOTE_DB') == 'true':
            return 'remote'
        
        # Check for GCP Cloud Run environment
        if os.getenv('K_SERVICE') or os.getenv('GAE_APPLICATION'):
            return 'remote'
        
        # Parse command line arguments for local development
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--server', choices=['local', 'remote'], default='remote')
        args, _ = parser.parse_known_args()
        return args.server
    
    def _validate_config(self):
        """Validate that required environment variables are present."""
        if self.server_type == 'local':
            required_vars = [
                'LOCAL_DATABASE_HOST', 'LOCAL_DATABASE_USER', 
                'LOCAL_DATABASE_NAME', 'LOCAL_DATABASE_PASSWORD'
            ]
        else:
            required_vars = [
                'DATABASE_HOST', 'DATABASE_USER', 
                'DATABASE_NAME', 'DATABASE_PASSWORD'
            ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            print(f"Warning: Missing environment variables for {self.server_type} database: {missing_vars}")
    
    def get_connection_string(self):
        """Get SQLAlchemy connection string based on server type."""
        if self.server_type == 'local':
            return self._get_postgresql_connection()
        else:
            dialect = os.getenv('REMOTE_DB_DIALECT', 'mysql').lower()
            if dialect in ('postgres', 'postgresql', 'pg'):
                return self._get_remote_postgresql_connection()
            return self._get_mysql_connection()
    
    def _get_postgresql_connection(self):
        """Get PostgreSQL connection string for local development."""
        host = os.getenv('LOCAL_DATABASE_HOST', 'localhost')
        port = os.getenv('LOCAL_DATABASE_PORT', '5432')
        user = quote_plus(os.getenv('LOCAL_DATABASE_USER', 'postgres') or '')
        password = quote_plus(os.getenv('LOCAL_DATABASE_PASSWORD', '') or '')
        database = quote_plus(os.getenv('LOCAL_DATABASE_NAME', 'sportsql_local') or '')
        
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    
    def _get_mysql_connection(self):
        """Get MySQL connection string for remote GCP database."""
        host = os.getenv('DATABASE_HOST')
        port = os.getenv('DATABASE_PORT', '3306')
        user = os.getenv('DATABASE_USER')
        password = os.getenv('DATABASE_PASSWORD')
        database = os.getenv('DATABASE_NAME')
        
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"

    def _get_remote_postgresql_connection(self):
        """Get PostgreSQL connection string for remote (e.g., Cloud SQL)."""
        host = os.getenv('DATABASE_HOST')
        port = os.getenv('DATABASE_PORT', '5432')
        user = quote_plus(os.getenv('DATABASE_USER') or '')
        password = quote_plus(os.getenv('DATABASE_PASSWORD') or '')
        database = quote_plus(os.getenv('DATABASE_NAME') or '')
        sslmode = os.getenv('DATABASE_SSLMODE')  # e.g., 'require'
        sslroot = os.getenv('DATABASE_SSLROOTCERT')  # optional path to CA cert

        base = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
        params = []
        if sslmode:
            params.append(f"sslmode={sslmode}")
        if sslroot:
            params.append(f"sslrootcert={sslroot}")
        if params:
            return base + "?" + "&".join(params)
        return base
    
    def create_engine(self):
        """Create SQLAlchemy engine with appropriate configuration."""
        connection_string = self.get_connection_string()
        
        # Common engine configuration
        engine_config = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 1,
            'max_overflow': 2,
        }
        
        # Add database-specific configuration
        if self.server_type == 'local':
            engine_config['connect_args'] = {"connect_timeout": 10}
        else:
            engine_config['connect_args'] = {"connect_timeout": 10}
        
        return create_engine(connection_string, **engine_config)
    
    def get_database_info(self):
        """Get human-readable database information."""
        if self.server_type == 'local':
            return {
                'type': 'PostgreSQL (Local)',
                'host': os.getenv('LOCAL_DATABASE_HOST', 'localhost'),
                'port': os.getenv('LOCAL_DATABASE_PORT', '5432'),
                'database': os.getenv('LOCAL_DATABASE_NAME', 'sportsql_local')
            }
        else:
            dialect = os.getenv('REMOTE_DB_DIALECT', 'mysql').lower()
            if dialect in ('postgres', 'postgresql', 'pg'):
                return {
                    'type': 'PostgreSQL (Remote)',
                    'host': os.getenv('DATABASE_HOST', 'Unknown'),
                    'port': os.getenv('DATABASE_PORT', '5432'),
                    'database': os.getenv('DATABASE_NAME', 'Unknown')
                }
            return {
                'type': 'MySQL (Remote GCP)',
                'host': os.getenv('DATABASE_HOST', 'Unknown'),
                'port': os.getenv('DATABASE_PORT', '3306'),
                'database': os.getenv('DATABASE_NAME', 'Unknown')
            }
    
    def is_local(self):
        """Check if using local database."""
        return self.server_type == 'local'
    
    def is_remote(self):
        """Check if using remote database."""
        return self.server_type == 'remote'


# Global database configuration instance
_db_config = None

def get_db_config(server_type=None):
    """Get or create global database configuration instance."""
    global _db_config
    if _db_config is None or server_type is not None:
        _db_config = DatabaseConfig(server_type)
    return _db_config

def get_engine():
    """Get SQLAlchemy engine using current configuration."""
    return get_db_config().create_engine()

def print_db_info():
    """Print current database configuration information."""
    config = get_db_config()
    info = config.get_database_info()
    print(f"Database Configuration:")
    print(f"  Type: {info['type']}")
    print(f"  Host: {info['host']}")
    print(f"  Port: {info['port']}")
    print(f"  Database: {info['database']}")
    print(f"  Server Type: {config.server_type}")
