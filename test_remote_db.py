#!/usr/bin/env python3
"""
Simple script to test and set up the remote database connection.
"""

import psycopg2
import sys

def test_and_setup_database():
    """Test connection and create schema if needed."""
    
    # First, let's try to connect with common default credentials
    connection_attempts = [
        {"user": "postgres", "password": "postgres"},
        {"user": "postgres", "password": ""},
        {"user": "etluser", "password": "etlpass"},
    ]
    
    for attempt in connection_attempts:
        try:
            print(f"Attempting to connect with user: {attempt['user']}")
            conn = psycopg2.connect(
                host="192.168.0.190",
                port=5432,
                user=attempt['user'],
                password=attempt['password'],
                database="postgres"
            )
            
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()
            print(f"✓ Connected successfully: {version[0]}")
            
            # Check if etldb database exists
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'etldb'")
            db_exists = cursor.fetchone()
            
            if not db_exists:
                print("Creating etldb database...")
                conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
                cursor.execute("CREATE DATABASE etldb")
                print("✓ Database 'etldb' created")
            else:
                print("✓ Database 'etldb' already exists")
            
            cursor.close()
            conn.close()
            
            # Now connect to etldb and create tables
            setup_schema()
            return True
            
        except Exception as e:
            print(f"✗ Connection failed with user {attempt['user']}: {e}")
            continue
    
    print("✗ All connection attempts failed")
    return False

def setup_schema():
    """Create the required tables in etldb."""
    
    try:
        # Try to connect to etldb
        conn = psycopg2.connect(
            host="192.168.0.190",
            port=5432,
            user="postgres",
            password="postgres",
            database="etldb"
        )
        
        cursor = conn.cursor()
        
        # Create the messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                message_id VARCHAR(255) NOT NULL UNIQUE,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source VARCHAR(100),
                status VARCHAR(50) DEFAULT 'processed'
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_message_id ON messages(message_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status)")
        
        conn.commit()
        print("✓ Schema created successfully")
        
        # Test the table
        cursor.execute("SELECT COUNT(*) FROM messages")
        count = cursor.fetchone()[0]
        print(f"✓ Messages table has {count} records")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"✗ Error setting up schema: {e}")
        return False

if __name__ == "__main__":
    print("Setting up remote database connection...")
    print("Host: 192.168.0.190")
    print("=" * 50)
    
    if test_and_setup_database():
        print("=" * 50)
        print("✓ Remote database setup completed successfully!")
    else:
        print("=" * 50)
        print("✗ Remote database setup failed!")
        sys.exit(1)
