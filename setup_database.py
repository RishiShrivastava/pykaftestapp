#!/usr/bin/env python3
"""
Database Schema Setup Script for Enhanced ETL Pipeline
Creates tables, indexes, and initial data for log processing system.
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', '192.168.0.190'),
    'port': os.getenv('POSTGRES_PORT', '5432'),
    'database': os.getenv('POSTGRES_DB', 'etldb'),
    'user': os.getenv('POSTGRES_USER', 'etluser'),
    'password': os.getenv('POSTGRES_PASSWORD', 'etlpass'),
    'sslmode': os.getenv('POSTGRES_SSL_MODE', 'prefer')
}

# SQL Schema Definitions
SCHEMA_SQL = """
-- Drop existing tables (in reverse dependency order)
DROP TABLE IF EXISTS log_statistics CASCADE;
DROP TABLE IF EXISTS parsed_logs CASCADE;
DROP TABLE IF EXISTS raw_logs CASCADE;
DROP TABLE IF EXISTS log_sources CASCADE;

-- 1. Log Sources Table
CREATE TABLE log_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    type VARCHAR(50) NOT NULL CHECK (type IN ('apache', 'nginx', 'application', 'custom')),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Raw Logs Table (Temporary storage)
CREATE TABLE raw_logs (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES log_sources(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255),
    raw_content TEXT,
    file_size BIGINT,
    file_hash VARCHAR(64) UNIQUE,
    upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    error_message TEXT
);

-- 3. Parsed Logs Table (Main analytics table)
CREATE TABLE parsed_logs (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES log_sources(id) ON DELETE CASCADE,
    raw_log_id INTEGER REFERENCES raw_logs(id) ON DELETE CASCADE,
    
    -- Timestamp fields
    timestamp TIMESTAMP,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Network fields
    ip_address INET,
    hostname VARCHAR(255),
    
    -- HTTP fields
    method VARCHAR(10),
    url TEXT,
    http_version VARCHAR(10),
    status_code INTEGER,
    response_size BIGINT,
    response_time FLOAT,
    
    -- Request details
    user_agent TEXT,
    referer TEXT,
    
    -- Error fields
    error_level VARCHAR(20),
    error_message TEXT,
    error_code VARCHAR(50),
    
    -- Session fields
    session_id VARCHAR(100),
    user_id VARCHAR(100),
    
    -- Enriched data (JSONB for flexible storage)
    geographic_info JSONB,
    user_agent_info JSONB,
    url_info JSONB,
    
    -- Classification
    error_category VARCHAR(50),
    
    -- Original data
    raw_line TEXT
);

-- 4. Log Statistics Table (Aggregated data)
CREATE TABLE log_statistics (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES log_sources(id) ON DELETE CASCADE,
    date_bucket DATE NOT NULL,
    hour_bucket INTEGER CHECK (hour_bucket >= 0 AND hour_bucket <= 23),
    
    -- Aggregate metrics
    total_requests BIGINT DEFAULT 0,
    unique_ips BIGINT DEFAULT 0,
    total_bytes BIGINT DEFAULT 0,
    
    -- Error metrics
    error_count BIGINT DEFAULT 0,
    client_error_count BIGINT DEFAULT 0,
    server_error_count BIGINT DEFAULT 0,
    
    -- Performance metrics
    avg_response_time FLOAT,
    min_response_time FLOAT,
    max_response_time FLOAT,
    
    -- Top lists (JSONB for flexibility)
    top_status_codes JSONB,
    top_user_agents JSONB,
    top_ips JSONB,
    top_urls JSONB,
    top_countries JSONB,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint
    UNIQUE(source_id, date_bucket, hour_bucket)
);
"""

# Index creation SQL
INDEXES_SQL = """
-- Indexes for log_sources
CREATE INDEX idx_log_sources_type ON log_sources(type);
CREATE INDEX idx_log_sources_name ON log_sources(name);

-- Indexes for raw_logs
CREATE INDEX idx_raw_logs_source_id ON raw_logs(source_id);
CREATE INDEX idx_raw_logs_processed ON raw_logs(processed);
CREATE INDEX idx_raw_logs_upload_timestamp ON raw_logs(upload_timestamp);
CREATE INDEX idx_raw_logs_file_hash ON raw_logs(file_hash);

-- Indexes for parsed_logs (performance critical)
CREATE INDEX idx_parsed_logs_timestamp ON parsed_logs(timestamp);
CREATE INDEX idx_parsed_logs_ip_address ON parsed_logs(ip_address);
CREATE INDEX idx_parsed_logs_status_code ON parsed_logs(status_code);
CREATE INDEX idx_parsed_logs_error_level ON parsed_logs(error_level);
CREATE INDEX idx_parsed_logs_method ON parsed_logs(method);
CREATE INDEX idx_parsed_logs_source_id ON parsed_logs(source_id);

-- JSONB indexes for enriched data
CREATE INDEX idx_parsed_logs_geographic_info ON parsed_logs USING GIN(geographic_info);
CREATE INDEX idx_parsed_logs_user_agent_info ON parsed_logs USING GIN(user_agent_info);

-- Composite indexes for common queries
CREATE INDEX idx_parsed_logs_timestamp_status ON parsed_logs(timestamp, status_code);
CREATE INDEX idx_parsed_logs_ip_timestamp ON parsed_logs(ip_address, timestamp);

-- Indexes for log_statistics
CREATE INDEX idx_log_statistics_source_date ON log_statistics(source_id, date_bucket);
CREATE INDEX idx_log_statistics_date_hour ON log_statistics(date_bucket, hour_bucket);
"""

# Initial data
INITIAL_DATA_SQL = """
-- Insert default log sources
INSERT INTO log_sources (name, type, description) VALUES
    ('apache-access', 'apache', 'Apache access logs'),
    ('apache-error', 'apache', 'Apache error logs'),
    ('nginx-access', 'nginx', 'Nginx access logs'),
    ('nginx-error', 'nginx', 'Nginx error logs'),
    ('application', 'application', 'Application logs'),
    ('custom', 'custom', 'Custom log format');
"""


def connect_to_database():
    """Create database connection."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Successfully connected to PostgreSQL database")
        return conn
    except psycopg2.Error as e:
        logger.error(f"Error connecting to PostgreSQL database: {e}")
        return None


def execute_sql(conn, sql, description):
    """Execute SQL with error handling."""
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
        conn.commit()
        logger.info(f"Successfully executed: {description}")
        return True
    except psycopg2.Error as e:
        logger.error(f"Error executing {description}: {e}")
        conn.rollback()
        return False


def verify_schema(conn):
    """Verify that all tables were created successfully."""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Check tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name;
            """)
            tables = [row['table_name'] for row in cursor.fetchall()]
            
            expected_tables = ['log_sources', 'raw_logs', 'parsed_logs', 'log_statistics']
            missing_tables = set(expected_tables) - set(tables)
            
            if missing_tables:
                logger.error(f"Missing tables: {missing_tables}")
                return False
            
            logger.info(f"All tables created successfully: {tables}")
            
            # Check indexes
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public' 
                AND indexname LIKE 'idx_%'
                ORDER BY indexname;
            """)
            indexes = [row['indexname'] for row in cursor.fetchall()]
            logger.info(f"Created {len(indexes)} indexes")
            
            # Check initial data
            cursor.execute("SELECT COUNT(*) as count FROM log_sources;")
            source_count = cursor.fetchone()['count']
            logger.info(f"Inserted {source_count} initial log sources")
            
            return True
            
    except psycopg2.Error as e:
        logger.error(f"Error verifying schema: {e}")
        return False


def main():
    """Main setup function."""
    logger.info("Starting database schema setup...")
    
    # Connect to database
    conn = connect_to_database()
    if not conn:
        sys.exit(1)
    
    try:
        # Create schema
        if not execute_sql(conn, SCHEMA_SQL, "schema creation"):
            sys.exit(1)
        
        # Create indexes
        if not execute_sql(conn, INDEXES_SQL, "index creation"):
            sys.exit(1)
        
        # Insert initial data
        if not execute_sql(conn, INITIAL_DATA_SQL, "initial data insertion"):
            sys.exit(1)
        
        # Verify setup
        if not verify_schema(conn):
            sys.exit(1)
        
        logger.info("Database schema setup completed successfully!")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
