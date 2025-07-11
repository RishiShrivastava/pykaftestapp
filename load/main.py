from fastapi import FastAPI
from confluent_kafka import Consumer, KafkaException
import json
import threading
import logging
from logging.handlers import RotatingFileHandler
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import Json
from psycopg2.pool import ThreadedConnectionPool
from datetime import datetime
import ssl

# Load environment variables
load_dotenv()

# Set up logging to file
os.makedirs('/app/logs', exist_ok=True)
file_handler = RotatingFileHandler('/app/logs/load.log', maxBytes=10485760, backupCount=5)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[file_handler, logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Database configuration with SSL
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'etldb'),
    'user': os.getenv('DB_USER', 'etluser'),
    'password': os.getenv('DB_PASSWORD', 'etlpass'),
    'host': os.getenv('DB_HOST', 'db'),
    'port': os.getenv('DB_PORT', '5432'),
    'sslmode': os.getenv('POSTGRES_SSL_MODE', 'require'),
    'sslcert': os.getenv('POSTGRES_SSL_CA'),
}

# Initialize connection pool
pool_size = int(os.getenv('DB_POOL_SIZE', 20))
pool_overflow = int(os.getenv('DB_POOL_OVERFLOW', 10))
db_pool = None

# Kafka configuration
kafka_config = {
    'bootstrap.servers': os.getenv('KAFKA_BROKER', 'kafka:29092'),
    'group.id': 'load-group',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False
}

consumer = Consumer(kafka_config)

def get_db_connection():
    if not db_pool:
        raise Exception("Database pool not initialized")
    return db_pool.getconn()

def return_db_connection(conn):
    if db_pool:
        db_pool.putconn(conn)

def init_db():
    global db_pool
    max_retries = 5
    retry_delay = 10  # seconds
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to connect to database (attempt {attempt + 1}/{max_retries})")
            logger.info(f"Database host: {DB_CONFIG['host']}")
            
            # Initialize the connection pool
            db_pool = ThreadedConnectionPool(
                minconn=pool_size,
                maxconn=pool_size + pool_overflow,
                **DB_CONFIG
            )
            
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Test connection
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            logger.info(f"Connected to database: {version}")
            
            # Create table for storing processed data with message tracking
            cur.execute("""
                CREATE TABLE IF NOT EXISTS processed_data (
                    id SERIAL PRIMARY KEY,
                    message_id VARCHAR(100) UNIQUE,
                    original_source VARCHAR(100),
                    original_timestamp TIMESTAMP,
                    transform_timestamp TIMESTAMP,
                    load_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create table for message tracking
            cur.execute("""
                CREATE TABLE IF NOT EXISTS message_tracking (
                    message_id VARCHAR(100) PRIMARY KEY,
                    source VARCHAR(100),
                    extract_timestamp TIMESTAMP,
                    transform_timestamp TIMESTAMP,
                    load_timestamp TIMESTAMP,
                    status VARCHAR(50),
                    metadata JSONB,
                    retry_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create table for messages (simpler table for basic ETL)
            cur.execute("""
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
            
            # Create indexes for better query performance
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_processed_data_message_id ON processed_data(message_id);
                CREATE INDEX IF NOT EXISTS idx_processed_data_timestamps ON processed_data(original_timestamp, transform_timestamp, load_timestamp);
                CREATE INDEX IF NOT EXISTS idx_message_tracking_status ON message_tracking(status);
                CREATE INDEX IF NOT EXISTS idx_message_tracking_timestamps ON message_tracking(extract_timestamp, transform_timestamp, load_timestamp);
                CREATE INDEX IF NOT EXISTS idx_messages_message_id ON messages(message_id);
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
                CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
            """)
            
            conn.commit()
            cur.close()
            return_db_connection(conn)
            
            logger.info("Database initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                import time
                time.sleep(retry_delay)
            else:
                logger.error("Max retries reached. Database connection failed.")
                return False
    
    return False

def store_data(data):
    if not db_pool:
        logger.warning(f"Database not available. Logging message: {data.get('message_id', 'unknown')}")
        return False
        
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Simple message storage for basic ETL
            cur.execute("""
                INSERT INTO messages 
                (message_id, content, source, status)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (message_id) DO UPDATE
                SET content = EXCLUDED.content,
                    processed_at = CURRENT_TIMESTAMP
            """, (
                data.get("message_id", "unknown"),
                json.dumps(data.get("transformed_data", data)),
                data.get("original_source", "unknown"),
                'processed'
            ))
            
            # Store the processed data
            cur.execute("""
                INSERT INTO processed_data 
                (message_id, original_source, original_timestamp, transform_timestamp, data)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (message_id) DO UPDATE
                SET data = EXCLUDED.data,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                data.get("message_id", "unknown"),
                data.get("original_source", "unknown"),
                data.get("original_timestamp"),
                data.get("transform_timestamp"),
                Json(data.get("transformed_data", data))
            ))
            
            # Update message tracking
            cur.execute("""
                INSERT INTO message_tracking 
                (message_id, source, extract_timestamp, transform_timestamp, load_timestamp, status, metadata)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
                ON CONFLICT (message_id) DO UPDATE
                SET status = EXCLUDED.status,
                    load_timestamp = CURRENT_TIMESTAMP,
                    retry_count = message_tracking.retry_count + 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                data.get("message_id", "unknown"),
                data.get("original_source", "unknown"),
                data.get("original_timestamp"),
                data.get("transform_timestamp"),
                'LOADED',
                Json({
                    "load_service_version": "1.0",
                    "processed_at": datetime.now().isoformat()
                })
            ))
            
            conn.commit()
            logger.info(f"Stored data in PostgreSQL: {data['message_id']}")
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            return_db_connection(conn)
            
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise e

def process_message(msg):
    try:
        # Parse the transformed data
        data = json.loads(msg.value())
        logger.info(f"Processing message: {data['message_id']}")
        
        # Store in PostgreSQL
        store_data(data)
        
        # Commit the message
        consumer.commit(msg)
        logger.info(f"Processed and committed message: {data['message_id']}")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def kafka_consumer_thread():
    try:
        consumer.subscribe(['transformed-data'])
        logger.info("Subscribed to transformed-data topic")
        
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                continue
            
            process_message(msg)
            
    except KafkaException as e:
        logger.error(f"Kafka error: {e}")
    finally:
        consumer.close()

# Initialize database and start Kafka consumer
@app.on_event("startup")
async def startup_event():
    db_connected = init_db()
    if not db_connected:
        logger.warning("Database connection failed. Service will start in degraded mode.")
        logger.warning("Messages will be logged but not stored until database is available.")
    
    # Start Kafka consumer in background
    background_thread = threading.Thread(target=kafka_consumer_thread, daemon=True)
    background_thread.start()

@app.get("/")
def read_root():
    return {
        "service": "Load Service",
        "status": "running",
        "kafka_broker": os.getenv('KAFKA_BROKER', 'kafka:29092'),
        "consuming_from": "transformed-data",
        "database": "PostgreSQL"
    }

@app.get("/health")
def health_check():
    try:
        # Check database connection
        db_connected = False
        if db_pool:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                return_db_connection(conn)
                db_connected = True
            except Exception as e:
                logger.error(f"Database health check failed: {e}")
        
        # Check Kafka connection
        kafka_connected = False
        try:
            topics = consumer.list_topics(timeout=5)
            kafka_connected = topics is not None
        except Exception as e:
            logger.error(f"Kafka health check failed: {e}")
        
        status = "healthy" if db_connected and kafka_connected else "degraded"
        
        return {
            "status": status,
            "kafka_connected": kafka_connected,
            "database_connected": db_connected,
            "database_host": DB_CONFIG['host'],
            "database_port": DB_CONFIG['port']
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
