#!/usr/bin/env python3
"""
Script to set up the remote database schema.
This script will create the database, user, and tables on the remote PostgreSQL instance.
"""

import psycopg2
import sys
import os
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def create_database_and_user():
    """Create the database and user on the remote PostgreSQL instance."""
    
    # Connection parameters for the remote database
    host = "192.168.0.190"
    port = 5432
    admin_user = "postgres"  # Default admin user
    admin_password = input("Enter PostgreSQL admin password: ")
    
    try:
        # Connect as admin to create database and user
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=admin_user,
            password=admin_password,
            database="postgres"  # Connect to default database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Create user if not exists
        cursor.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'etluser') THEN
                    CREATE USER etluser WITH PASSWORD 'etlpass';
                END IF;
            END $$;
        """)
        
        # Create database if not exists
        cursor.execute("""
            SELECT 1 FROM pg_database WHERE datname = 'etldb'
        """)
        
        if not cursor.fetchone():
            cursor.execute("CREATE DATABASE etldb OWNER etluser")
            print("Database 'etldb' created successfully")
        else:
            print("Database 'etldb' already exists")
        
        # Grant privileges
        cursor.execute("GRANT ALL PRIVILEGES ON DATABASE etldb TO etluser")
        
        cursor.close()
        conn.close()
        
        print("Database and user setup completed successfully")
        return True
        
    except Exception as e:
        print(f"Error setting up database and user: {e}")
        return False

def create_schema():
    """Create the required schema in the etldb database."""
    
    try:
        # Connect to the etldb database as etluser
        conn = psycopg2.connect(
            host="192.168.0.190",
            port=5432,
            user="etluser",
            password="etlpass",
            database="etldb"
        )
        
        cursor = conn.cursor()
        
        # Create the messages table with the same schema as in load/main.py
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
        
        # Create indexes for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_message_id ON messages(message_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status)
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("Schema created successfully")
        return True
        
    except Exception as e:
        print(f"Error creating schema: {e}")
        return False

def test_connection():
    """Test the connection to the remote database."""
    
    try:
        conn = psycopg2.connect(
            host="192.168.0.190",
            port=5432,
            user="etluser",
            password="etlpass",
            database="etldb"
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()
        print(f"Connected to PostgreSQL: {version[0]}")
        
        # Test table exists
        cursor.execute("SELECT COUNT(*) FROM messages")
        count = cursor.fetchone()[0]
        print(f"Messages table exists with {count} records")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Error testing connection: {e}")
        return False

if __name__ == "__main__":
    print("Setting up remote PostgreSQL database...")
    print("Host: 192.168.0.190")
    print("Database: etldb")
    print("User: etluser")
    print()
    
    # Step 1: Create database and user
    if create_database_and_user():
        print("✓ Database and user setup completed")
    else:
        print("✗ Failed to set up database and user")
        sys.exit(1)
    
    # Step 2: Create schema
    if create_schema():
        print("✓ Schema created successfully")
    else:
        print("✗ Failed to create schema")
        sys.exit(1)
    
    # Step 3: Test connection
    if test_connection():
        print("✓ Connection test successful")
        print("\nRemote database setup completed successfully!")
    else:
        print("✗ Connection test failed")
        sys.exit(1)
