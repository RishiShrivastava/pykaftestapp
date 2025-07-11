from fastapi import FastAPI
from confluent_kafka import Consumer, Producer, KafkaException
import json
import threading
import logging
from logging.handlers import RotatingFileHandler
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Set up logging to file
os.makedirs('/app/logs', exist_ok=True)
file_handler = RotatingFileHandler('/app/logs/transform.log', maxBytes=10485760, backupCount=5)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[file_handler, logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Kafka configuration
kafka_config = {
    'bootstrap.servers': os.getenv('KAFKA_BROKER', 'kafka:29092'),
    'group.id': 'transform-group',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False
}

producer_config = {
    'bootstrap.servers': os.getenv('KAFKA_BROKER', 'kafka:29092'),
    'client.id': 'transform-service'
}

consumer = Consumer(kafka_config)
producer = Producer(producer_config)

def delivery_report(err, msg):
    if err is not None:
        logger.error(f'Message delivery failed: {err}')
    else:
        logger.info(f'Transformed message delivered to {msg.topic()} [partition: {msg.partition()}] at offset {msg.offset()}')

def process_message(msg):
    try:
        # Parse the raw data
        raw_data = json.loads(msg.value())
        logger.info(f"Processing message: {raw_data['message_id']}")
        
        # Transform the data
        transformed_data = {
            "message_id": raw_data["message_id"],
            "original_source": raw_data["source"],
            "transform_timestamp": datetime.now().isoformat(),
            "original_timestamp": raw_data["timestamp"],
            "transformed_data": {
                "processed": True,
                "data": raw_data["data"],
                "metadata": {
                    "transformed_by": "transform-service",
                    "transform_version": "1.0"
                }
            }
        }
        
        # Produce transformed data to new topic
        producer.produce(
            'transformed-data',
            key=raw_data["source"],
            value=json.dumps(transformed_data),
            callback=delivery_report
        )
        producer.flush()
        
        # Commit the message
        consumer.commit(msg)
        logger.info(f"Transformed and committed message: {raw_data['message_id']}")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def kafka_consumer_thread():
    try:
        consumer.subscribe(['raw-data'])
        logger.info("Subscribed to raw-data topic")
        
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

# Start Kafka consumer in background
background_thread = threading.Thread(target=kafka_consumer_thread, daemon=True)
background_thread.start()

@app.get("/")
def read_root():
    return {
        "service": "Transform Service",
        "status": "running",
        "kafka_broker": os.getenv('KAFKA_BROKER', 'kafka:29092'),
        "consuming_from": "raw-data",
        "producing_to": "transformed-data"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "kafka_connected": consumer.list_topics() is not None
    }
