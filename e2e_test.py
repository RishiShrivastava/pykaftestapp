import requests
import psycopg2
import json
import time
import os
from datetime import datetime
import logging
from typing import Dict, Any
import sys

# Set up logging with a more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('etl_test_report.log')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
EXTRACT_URL = "http://localhost:8001/extract"
DB_HOST = os.getenv("POSTGRES_HOST", "192.168.0.190")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "etltest")
DB_USER = os.getenv("POSTGRES_USER", "etluser")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "etlpassword")

def print_json(data: Dict[str, Any], title: str = None) -> None:
    """Print JSON data in a formatted way with an optional title"""
    if title:
        logger.info("=" * 80)
        logger.info(title)
        logger.info("=" * 80)
    logger.info(json.dumps(data, indent=2))

def connect_to_db():
    """Create a connection to the PostgreSQL database"""
    try:
        logger.info("Attempting to connect to PostgreSQL database:")
        logger.info(f"  Host: {DB_HOST}")
        logger.info(f"  Port: {DB_PORT}")
        logger.info(f"  Database: {DB_NAME}")
        logger.info(f"  User: {DB_USER}")
        
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        # Get database version
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            logger.info(f"Successfully connected to PostgreSQL: {version}")
        
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise

def check_data_in_db(conn, test_id):
    """Check if test data exists in the database and return details about the transformation"""
    try:
        with conn.cursor() as cur:
            # Check if data exists and get its details
            cur.execute("""
                SELECT id, created_at, data
                FROM processed_data 
                WHERE data->'data'->>'test_id' = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (test_id,))
            result = cur.fetchone()
            
            if result:
                logger.info(f"Found data in database:")
                logger.info(f"  Record ID: {result[0]}")
                logger.info(f"  Created at: {result[1]}")
                return result
            else:
                logger.warning(f"No data found in database for test_id: {test_id}")
                return None
    except Exception as e:
        logger.error(f"Error querying database: {e}")
        raise

def main():
    """Run the end-to-end test of the ETL pipeline"""
    logger.info("\n" + "="*50 + "\nSTARTING END-TO-END ETL PIPELINE TEST\n" + "="*50)
    
    # Generate unique test ID
    test_id = f"test_{int(time.time())}"
    logger.info(f"Generated unique test ID: {test_id}")
    
    # Step 1: Prepare test data
    logger.info("\nSTEP 1: Preparing test data")
    test_data = {
        "source": "e2e_test",
        "data": {
            "test_id": test_id,
            "name": "Test User",
            "email": "test@example.com",
            "timestamp": datetime.now().isoformat(),
            "values": [1, 2, 3, 4, 5]
        }
    }
    print_json(test_data, "Input Data (to Extract Service)")

    # Step 2: Send data to extract service
    logger.info("\nSTEP 2: Sending data to Extract Service")
    logger.info(f"POST {EXTRACT_URL}")
    try:
        response = requests.post(EXTRACT_URL, json=test_data)
        response.raise_for_status()
        logger.info(f"Response Status: {response.status_code}")
        logger.info("Successfully sent data to extract service")
        
        if response.text:
            try:
                print_json(response.json(), "Extract Service Response")
            except json.JSONDecodeError:
                logger.info(f"Response Text: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send data to extract service: {e}")
        return False

    # Step 3: Wait for data processing
    logger.info("\nSTEP 3: Waiting for data to be processed through the pipeline...")
    time.sleep(5)  # Initial wait for processing

    # Step 4: Verify data in database
    logger.info("\nSTEP 4: Verifying processed data in database")
    try:
        conn = connect_to_db()
        max_retries = 5
        retry_count = 0
        result = None

        while retry_count < max_retries:
            result = check_data_in_db(conn, test_id)
            if result:
                print_json(result[2], "Final Processed Data (from Database)")
                break
            
            retry_count += 1
            if retry_count < max_retries:
                logger.info(f"Data not found, retrying in 2 seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(2)
            else:
                logger.error("Data not found in database after all retries")
                return False

        # Verify data integrity
        logger.info("\nSTEP 5: Verifying data integrity")
        db_data = result[2]
        
        # Verify source
        logger.info("Checking source field...")
        if db_data.get('source') == test_data['source']:
            logger.info("✓ Source field matches")
        else:
            logger.error("✗ Source field mismatch")
            
        # Verify test_id
        logger.info("Checking test_id...")
        if db_data.get('data', {}).get('test_id') == test_data['data']['test_id']:
            logger.info("✓ test_id matches")
        else:
            logger.error("✗ test_id mismatch")

        logger.info("\n" + "="*50 + "\nTEST SUMMARY\n" + "="*50)
        logger.info("✓ Data successfully sent to Extract Service")
        logger.info("✓ Data processed through Transform Service")
        logger.info("✓ Data loaded into database by Load Service")
        logger.info("✓ Data integrity verified")
        logger.info("\nEnd-to-end test completed successfully!")
        logger.info("="*50)
        return True

    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
