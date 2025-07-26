"""
Enhanced Extract Service for Log Processing
Handles file uploads and log extraction with multiple format support.
"""

from typing import List, Optional, Dict, Any
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from confluent_kafka import Producer
from pydantic import BaseModel, Field
import json
import os
import re
import hashlib
from datetime import datetime
from pathlib import Path
import aiofiles
from enum import Enum
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
os.makedirs('/app/logs', exist_ok=True)
file_handler = RotatingFileHandler('/app/logs/extract.log', maxBytes=10485760, backupCount=5)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[file_handler, logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class LogType(str, Enum):
    """Supported log file types."""
    APACHE = "apache"
    NGINX = "nginx"
    APPLICATION = "application"
    CUSTOM = "custom"


class LogEntry(BaseModel):
    """Structured log entry model."""
    timestamp: Optional[datetime] = None
    ip_address: Optional[str] = None
    method: Optional[str] = None
    url: Optional[str] = None
    status_code: Optional[int] = None
    response_size: Optional[int] = None
    user_agent: Optional[str] = None
    referer: Optional[str] = None
    error_message: Optional[str] = None
    error_level: Optional[str] = None
    raw_line: str = Field(..., description="Original log line")


class LogParser:
    """Log parsing utility class."""
    
    # Apache Common Log Format
    APACHE_COMMON_PATTERN = re.compile(
        r'(?P<ip>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] '
        r'"(?P<method>\S+) (?P<url>\S+) (?P<version>[^"]+)" '
        r'(?P<status>\d+) (?P<size>\S+)'
    )
    
    # Apache Combined Log Format
    APACHE_COMBINED_PATTERN = re.compile(
        r'(?P<ip>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] '
        r'"(?P<method>\S+) (?P<url>\S+) (?P<version>[^"]+)" '
        r'(?P<status>\d+) (?P<size>\S+) '
        r'"(?P<referer>[^"]*)" "(?P<user_agent>[^"]*)"'
    )
    
    # Nginx Log Format
    NGINX_PATTERN = re.compile(
        r'(?P<ip>\S+) - \S+ \[(?P<timestamp>[^\]]+)\] '
        r'"(?P<method>\S+) (?P<url>\S+) (?P<version>[^"]+)" '
        r'(?P<status>\d+) (?P<size>\S+) '
        r'"(?P<referer>[^"]*)" "(?P<user_agent>[^"]*)"'
    )
    
    @classmethod
    def parse_apache_log(cls, line: str) -> Optional[LogEntry]:
        """Parse Apache log format."""
        match = cls.APACHE_COMBINED_PATTERN.match(line)
        if not match:
            match = cls.APACHE_COMMON_PATTERN.match(line)
        
        if match:
            data = match.groupdict()
            return LogEntry(
                ip_address=data.get('ip'),
                timestamp=cls._parse_timestamp(data.get('timestamp')),
                method=data.get('method'),
                url=data.get('url'),
                status_code=int(data.get('status', 0)),
                response_size=cls._parse_size(data.get('size')),
                user_agent=data.get('user_agent'),
                referer=data.get('referer'),
                raw_line=line
            )
        return None
    
    @classmethod
    def parse_nginx_log(cls, line: str) -> Optional[LogEntry]:
        """Parse Nginx log format."""
        match = cls.NGINX_PATTERN.match(line)
        if match:
            data = match.groupdict()
            return LogEntry(
                ip_address=data.get('ip'),
                timestamp=cls._parse_timestamp(data.get('timestamp')),
                method=data.get('method'),
                url=data.get('url'),
                status_code=int(data.get('status', 0)),
                response_size=cls._parse_size(data.get('size')),
                user_agent=data.get('user_agent'),
                referer=data.get('referer'),
                raw_line=line
            )
        return None
    
    @staticmethod
    def _parse_timestamp(timestamp_str: str) -> Optional[datetime]:
        """Parse timestamp from log."""
        if not timestamp_str:
            return None
        try:
            # Apache/Nginx format: 10/Oct/2000:13:55:36 -0700
            return datetime.strptime(
                timestamp_str.split()[0], 
                "%d/%b/%Y:%H:%M:%S"
            )
        except ValueError:
            return None
    
    @staticmethod
    def _parse_size(size_str: str) -> Optional[int]:
        """Parse response size."""
        if size_str == '-' or not size_str:
            return None
        try:
            return int(size_str)
        except ValueError:
            return None


class EnhancedExtractService:
    """Enhanced Extract Service with file upload and parsing."""
    
    def __init__(self):
        self.upload_dir = Path("/app/data/uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        self.kafka_producer = Producer({
            'bootstrap.servers': os.getenv('KAFKA_BROKER', 'kafka:29092'),
            'client.id': 'enhanced-extract-service'
        })
        
        self.parser = LogParser()
    
    async def upload_log_file(
        self, 
        file: UploadFile, 
        log_type: LogType,
        source_name: str
    ) -> Dict[str, Any]:
        """Upload and process log file."""
        
        # Validate file
        if not file.filename.endswith(('.log', '.txt', '.access')):
            raise HTTPException(
                status_code=400, 
                detail="Invalid file type. Only .log, .txt, .access files allowed"
            )
        
        # Check file size (max 100MB)
        content = await file.read()
        if len(content) > 100 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum size is 100MB"
            )
        
        # Generate unique filename
        file_hash = hashlib.md5(
            f"{file.filename}{datetime.now().isoformat()}".encode()
        ).hexdigest()
        unique_filename = f"{file_hash}_{file.filename}"
        file_path = self.upload_dir / unique_filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        logger.info(f"File uploaded: {unique_filename}, size: {len(content)} bytes")
        
        # Process file
        processing_result = await self._process_log_file(
            file_path, log_type, source_name, unique_filename
        )
        
        return {
            "status": "success",
            "filename": unique_filename,
            "original_filename": file.filename,
            "file_size": len(content),
            "file_hash": file_hash,
            "processing_result": processing_result
        }
    
    async def _process_log_file(
        self, 
        file_path: Path, 
        log_type: LogType, 
        source_name: str,
        filename: str
    ) -> Dict[str, Any]:
        """Process uploaded log file."""
        
        processed_count = 0
        error_count = 0
        
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                line_num = 0
                async for line in f:
                    line_num += 1
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        # Parse based on log type
                        if log_type == LogType.APACHE:
                            parsed_entry = self.parser.parse_apache_log(line)
                        elif log_type == LogType.NGINX:
                            parsed_entry = self.parser.parse_nginx_log(line)
                        else:
                            # For custom/application logs, create basic entry
                            parsed_entry = LogEntry(raw_line=line)
                        
                        if parsed_entry:
                            # Send to Kafka for further processing
                            await self._send_to_kafka(
                                parsed_entry, source_name, filename, line_num
                            )
                            processed_count += 1
                        else:
                            error_count += 1
                            
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error processing line {line_num}: {e}")
        
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing file: {e}")
        
        logger.info(f"File processing completed: {processed_count} processed, {error_count} errors")
        
        return {
            "processed_lines": processed_count,
            "error_lines": error_count,
            "total_lines": processed_count + error_count
        }
    
    async def _send_to_kafka(
        self, 
        log_entry: LogEntry, 
        source_name: str, 
        filename: str, 
        line_num: int
    ):
        """Send parsed log entry to Kafka."""
        
        message = {
            "message_id": f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{line_num}",
            "source_name": source_name,
            "filename": filename,
            "line_number": line_num,
            "timestamp": datetime.now().isoformat(),
            "log_data": log_entry.dict()
        }
        
        try:
            self.kafka_producer.produce(
                'parsed-logs',
                key=source_name,
                value=json.dumps(message, default=str),
                callback=self._delivery_report
            )
            self.kafka_producer.flush()
        except Exception as e:
            logger.error(f"Error sending message to Kafka: {e}")
    
    def _delivery_report(self, err, msg):
        """Kafka delivery callback."""
        if err is not None:
            logger.error(f'Message delivery failed: {err}')
        else:
            logger.debug(f'Message delivered to {msg.topic()}')


# FastAPI Application
app = FastAPI(
    title="Enhanced ETL Extract Service",
    description="Log file processing and extraction service",
    version="2.0.0"
)

extract_service = EnhancedExtractService()


@app.get("/", response_class=HTMLResponse)
async def upload_form():
    """Upload form HTML page."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Enhanced ETL - Log File Upload</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                padding: 40px;
                max-width: 600px;
                width: 90%;
            }
            
            .header {
                text-align: center;
                margin-bottom: 30px;
            }
            
            .header h1 {
                color: #333;
                font-size: 2.5em;
                margin-bottom: 10px;
            }
            
            .header p {
                color: #666;
                font-size: 1.1em;
            }
            
            .form-group {
                margin-bottom: 25px;
            }
            
            label {
                display: block;
                margin-bottom: 8px;
                font-weight: 600;
                color: #333;
                font-size: 1.1em;
            }
            
            input[type="file"], select, input[type="text"] {
                width: 100%;
                padding: 15px;
                border: 2px solid #e1e5e9;
                border-radius: 10px;
                font-size: 16px;
                transition: border-color 0.3s ease;
            }
            
            input[type="file"]:focus, select:focus, input[type="text"]:focus {
                outline: none;
                border-color: #667eea;
            }
            
            select {
                background-color: white;
            }
            
            .file-info {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 15px;
                margin-top: 10px;
                font-size: 14px;
                color: #666;
            }
            
            .submit-btn {
                width: 100%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 18px;
                border: none;
                border-radius: 10px;
                font-size: 18px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s ease;
            }
            
            .submit-btn:hover {
                transform: translateY(-2px);
            }
            
            .submit-btn:disabled {
                background: #ccc;
                cursor: not-allowed;
                transform: none;
            }
            
            .features {
                margin-top: 30px;
                padding-top: 30px;
                border-top: 1px solid #e1e5e9;
            }
            
            .features h3 {
                color: #333;
                margin-bottom: 15px;
            }
            
            .features ul {
                list-style: none;
                color: #666;
            }
            
            .features li {
                padding: 5px 0;
                position: relative;
                padding-left: 20px;
            }
            
            .features li:before {
                content: "✓";
                position: absolute;
                left: 0;
                color: #28a745;
                font-weight: bold;
            }
            
            .loading {
                display: none;
                text-align: center;
                margin-top: 20px;
            }
            
            .spinner {
                border: 4px solid #f3f3f3;
                border-top: 4px solid #667eea;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 0 auto;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔍 Log Analyzer</h1>
                <p>Upload and analyze your log files with advanced ETL processing</p>
            </div>
            
            <form id="uploadForm" action="/upload" method="post" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="file">📄 Select Log File:</label>
                    <input type="file" id="file" name="file" accept=".log,.txt,.access" required>
                    <div class="file-info">
                        Supported formats: .log, .txt, .access | Maximum size: 100MB
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="log_type">🔧 Log Type:</label>
                    <select id="log_type" name="log_type" required>
                        <option value="">Select log type...</option>
                        <option value="apache">Apache Access/Error Logs</option>
                        <option value="nginx">Nginx Access/Error Logs</option>
                        <option value="application">Application Logs</option>
                        <option value="custom">Custom Format</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="source_name">🏷️ Source Name:</label>
                    <input type="text" id="source_name" name="source_name" 
                           placeholder="e.g., web-server-01, api-gateway, load-balancer" required>
                </div>
                
                <button type="submit" class="submit-btn" id="submitBtn">
                    📤 Upload and Process
                </button>
                
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p>Processing your log file...</p>
                </div>
            </form>
            
            <div class="features">
                <h3>🚀 Features</h3>
                <ul>
                    <li>Multi-format log parsing (Apache, Nginx, Custom)</li>
                    <li>Real-time data processing with Kafka</li>
                    <li>Geographic IP enrichment</li>
                    <li>User agent and device detection</li>
                    <li>Advanced analytics and reporting</li>
                    <li>Secure processing with WAF protection</li>
                </ul>
            </div>
        </div>
        
        <script>
            document.getElementById('uploadForm').addEventListener('submit', function() {
                document.getElementById('submitBtn').disabled = true;
                document.getElementById('loading').style.display = 'block';
            });
            
            document.getElementById('file').addEventListener('change', function(e) {
                const file = e.target.files[0];
                if (file) {
                    const size = (file.size / 1024 / 1024).toFixed(2);
                    console.log(`Selected file: ${file.name} (${size} MB)`);
                }
            });
        </script>
    </body>
    </html>
    """


@app.post("/upload")
async def upload_log_file(
    file: UploadFile = File(...),
    log_type: LogType = Form(...),
    source_name: str = Form(...)
):
    """Upload and process log file."""
    try:
        result = await extract_service.upload_log_file(file, log_type, source_name)
        return JSONResponse(content=result)
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"status": "error", "detail": e.detail}
        )
    except Exception as e:
        logger.error(f"Unexpected error in upload: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": "Internal server error"}
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "service": "Enhanced Extract Service",
        "status": "running",
        "version": "2.0.0",
        "features": [
            "File Upload",
            "Apache Log Parsing", 
            "Nginx Log Parsing",
            "Custom Format Support",
            "Kafka Integration",
            "Real-time Processing"
        ],
        "kafka_broker": os.getenv('KAFKA_BROKER', 'kafka:29092')
    }


@app.get("/stats")
async def get_stats():
    """Get service statistics."""
    upload_dir = Path("/app/data/uploads")
    files = list(upload_dir.glob("*")) if upload_dir.exists() else []
    
    return {
        "uploaded_files": len(files),
        "upload_directory": str(upload_dir),
        "supported_formats": [".log", ".txt", ".access"],
        "max_file_size": "100MB"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
