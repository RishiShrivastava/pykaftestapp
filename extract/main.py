from fastapi import FastAPI, HTTPException
from confluent_kafka import Producer
from pydantic import BaseModel
import json
import os
from dotenv import load_dotenv
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Load environment variables
load_dotenv()

app = FastAPI()

# Set up logging to file
os.makedirs('/app/logs', exist_ok=True)
file_handler = RotatingFileHandler('/app/logs/extract.log', maxBytes=10485760, backupCount=5)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[file_handler, logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Kafka configuration
kafka_config = {
    'bootstrap.servers': os.getenv('KAFKA_BROKER', 'kafka:29092'),
    'client.id': 'extract-service'
}

producer = Producer(kafka_config)

class DataInput(BaseModel):
    source: str
    data: dict

def delivery_report(err, msg):
    if err is not None:
        logger.error(f'Message delivery failed: {err}')
    else:
        logger.info(f'Message delivered to {msg.topic()} [partition: {msg.partition()}] at offset {msg.offset()}')

@app.post("/extract")
async def extract_data(input_data: DataInput):
    try:
        message = {
            "message_id": f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "source": input_data.source,
            "timestamp": datetime.now().isoformat(),
            "data": input_data.data
        }
        
        # Produce message to Kafka
        producer.produce(
            'raw-data',
            key=input_data.source,
            value=json.dumps(message),
            callback=delivery_report
        )
        producer.flush()
        
        logger.info(f"Message sent to topic 'raw-data': {message}")
        return {
            "status": "success",
            "message": "Data extracted and sent to processing",
            "message_id": message["message_id"]
        }
    except Exception as e:
        logger.error(f"Error in extract_data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {
        "service": "Extract Service",
        "status": "running",
        "kafka_broker": os.getenv('KAFKA_BROKER', 'kafka:29092')
    }
