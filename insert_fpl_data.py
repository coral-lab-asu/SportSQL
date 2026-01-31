#!/usr/bin/env python3
"""
Script to insert FPL CSV data into local PostgreSQL database.
Reads all CSV files from fpl_database/fpl/ folder and inserts them into the local database.
"""

import os
import pandas as pd
import sys
from pathlib import Path
from db_config import get_db_config
from sqlalchemy import text, inspect

def main():
    """Main function to insert FPL CSV data into PostgreSQL."""
    
    # Force local database configuration
    print("🔧 Configuring local PostgreSQL database...")
    db_config = get_db_config(server_type='local')
    
    # Print database info
    info = db_config.get_database_info()
    print(f"📊 Database: {info['type']}")
    print(f"🏠 Host: {info['host']}:{info['port']}")
    print(f"💾 Database: {info['database']}")
    print()
    
    try:
        # Create database engine
        engine = db_config.create_engine()
        
        # Test connection
        print("🔗 Testing database connection...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Connected successfully!")
            print(f"🐘 PostgreSQL version: {version.split(',')[0]}")
        print()
        
        # Define CSV files and their corresponding table names
        csv_files = {
            'fixtures': 'fpl_database/fpl/fixtures.csv',
            'players': 'fpl_database/fpl/players.csv', 
            'teams': 'fpl_database/fpl/teams.csv'
        }
        
        # Process each CSV file
        for table_name, csv_path in csv_files.items():
            full_path = Path(csv_path)
            
            if not full_path.exists():
                print(f"❌ File not found: {csv_path}")
                continue
                
            print(f"📄 Processing {csv_path}...")
            
            # Read CSV file
            try:
                df = pd.read_csv(full_path)
                print(f"📊 Loaded {len(df)} rows, {len(df.columns)} columns")
                
                # Display first few column names
                print(f"📋 Columns: {', '.join(df.columns[:5])}{'...' if len(df.columns) > 5 else ''}")
                
                # Insert data into database
                print(f"💾 Inserting data into table '{table_name}'...")
                
                # Drop table if exists and create new one
                with engine.connect() as conn:
                    # Drop existing table
                    conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                    conn.commit()
                    
                # Insert data - pandas will create the table automatically
                df.to_sql(
                    table_name, 
                    engine, 
                    if_exists='replace', 
                    index=False,
                    method='multi',
                    chunksize=1000
                )
                
                # Verify insertion
                with engine.connect() as conn:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    count = result.fetchone()[0]
                    print(f"✅ Successfully inserted {count} rows into '{table_name}' table")
                
                print()
                
            except Exception as e:
                print(f"❌ Error processing {csv_path}: {str(e)}")
                continue
        
        # Display final summary
        print("📋 Final Database Summary:")
        print("=" * 50)
        
        with engine.connect() as conn:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            for table in sorted(tables):
                if table in csv_files.keys():
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.fetchone()[0]
                    print(f"📊 {table}: {count} rows")
        
        print()
        print("🎉 All CSV files have been successfully inserted into the local PostgreSQL database!")
        
    except Exception as e:
        print(f"❌ Database connection error: {str(e)}")
        print("\n💡 Make sure:")
        print("   1. PostgreSQL is running locally")
        print("   2. Database credentials are set in .env file:")
        print("      - LOCAL_DATABASE_HOST")
        print("      - LOCAL_DATABASE_USER") 
        print("      - LOCAL_DATABASE_PASSWORD")
        print("      - LOCAL_DATABASE_NAME")
        print("   3. Database exists and user has proper permissions")
        sys.exit(1)

if __name__ == "__main__":
    main()
