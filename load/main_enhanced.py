"""
Enhanced Load Service with Database Optimization and Analytics
Handles bulk loading, data aggregation, and real-time analytics.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import asyncio
import asyncpg
import logging
from logging.handlers import RotatingFileHandler
from confluent_kafka import Consumer
from collections import defaultdict, deque
import os
from dotenv import load_dotenv
import hashlib
from contextlib import asynccontextmanager

# Load environment variables
load_dotenv()

# Set up logging
os.makedirs('/app/logs', exist_ok=True)
file_handler = RotatingFileHandler('/app/logs/load.log', maxBytes=10485760, backupCount=5)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[file_handler, logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


@dataclass
class BatchMetrics:
    """Metrics for batch processing."""
    batch_size: int = 0
    processing_time: float = 0.0
    success_count: int = 0
    error_count: int = 0
    start_time: datetime = None
    end_time: datetime = None


@dataclass
class DatabaseStats:
    """Database performance statistics."""
    total_records: int = 0
    records_per_second: float = 0.0
    avg_processing_time: float = 0.0
    connection_pool_size: int = 0
    active_connections: int = 0


class ConnectionManager:
    """PostgreSQL connection pool manager."""
    
    def __init__(self):
        self.pool = None
        self.connection_string = self._build_connection_string()
    
    def _build_connection_string(self) -> str:
        """Build PostgreSQL connection string."""
        return (
            f"postgresql://{os.getenv('DB_USER', 'etluser')}:"
            f"{os.getenv('DB_PASSWORD', 'etlpassword')}@"
            f"{os.getenv('DB_HOST', '192.168.0.190')}:"
            f"{os.getenv('DB_PORT', '5432')}/"
            f"{os.getenv('DB_NAME', 'etldb')}"
        )
    
    async def initialize_pool(self):
        """Initialize connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=5,
                max_size=20,
                command_timeout=60,
                server_settings={
                    'application_name': 'enhanced_load_service',
                    'jit': 'off'  # Disable JIT for better performance on small queries
                }
            )
            logger.info("Database connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool."""
        if not self.pool:
            await self.initialize_pool()
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def close_pool(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")


class BulkInserter:
    """Optimized bulk insertion utility."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.batch_size = int(os.getenv('BATCH_SIZE', '1000'))
        self.batch_timeout = int(os.getenv('BATCH_TIMEOUT', '30'))  # seconds
    
    async def bulk_insert_raw_logs(self, log_entries: List[Dict[str, Any]]) -> BatchMetrics:
        """Bulk insert raw log entries."""
        start_time = datetime.now()
        metrics = BatchMetrics(
            batch_size=len(log_entries),
            start_time=start_time
        )
        
        try:
            async with self.connection_manager.get_connection() as conn:
                # Prepare data for bulk insert
                records = []
                for entry in log_entries:
                    original_data = entry.get('original_data', {})
                    log_data = original_data.get('log_data', {})
                    
                    record = (
                        original_data.get('source_name'),
                        original_data.get('filename'),
                        log_data.get('raw_line', ''),
                        log_data.get('timestamp'),
                        log_data.get('ip_address'),
                        log_data.get('method'),
                        log_data.get('url'),
                        log_data.get('status_code'),
                        log_data.get('response_size'),
                        log_data.get('user_agent'),
                        log_data.get('referer'),
                        json.dumps(log_data),
                        datetime.now()
                    )
                    records.append(record)
                
                # Bulk insert using COPY
                await conn.copy_records_to_table(
                    'raw_logs',
                    records=records,
                    columns=[
                        'source_name', 'filename', 'raw_line', 'log_timestamp',
                        'ip_address', 'http_method', 'url', 'status_code',
                        'response_size', 'user_agent', 'referer',
                        'parsed_data', 'created_at'
                    ]
                )
                
                metrics.success_count = len(records)
                
        except Exception as e:
            logger.error(f"Error in bulk insert raw logs: {e}")
            metrics.error_count = len(log_entries)
        
        metrics.end_time = datetime.now()
        metrics.processing_time = (metrics.end_time - metrics.start_time).total_seconds()
        
        return metrics
    
    async def bulk_insert_parsed_logs(self, enriched_entries: List[Dict[str, Any]]) -> BatchMetrics:
        """Bulk insert parsed and enriched log entries."""
        start_time = datetime.now()
        metrics = BatchMetrics(
            batch_size=len(enriched_entries),
            start_time=start_time
        )
        
        try:
            async with self.connection_manager.get_connection() as conn:
                # Prepare enriched data for bulk insert
                records = []
                for entry in enriched_entries:
                    enriched_data = entry.get('enriched_data', {})
                    original_data = enriched_data.get('original_data', {})
                    log_data = original_data.get('log_data', {})
                    
                    # Extract geo location data
                    geo_location = enriched_data.get('geo_location', {})
                    device_info = enriched_data.get('device_info', {})
                    url_analysis = enriched_data.get('url_analysis', {})
                    security_analysis = enriched_data.get('security_analysis', {})
                    
                    record = (
                        original_data.get('source_name'),
                        original_data.get('filename'),
                        log_data.get('timestamp'),
                        log_data.get('ip_address'),
                        log_data.get('method'),
                        log_data.get('url'),
                        log_data.get('status_code'),
                        log_data.get('response_size'),
                        log_data.get('user_agent'),
                        log_data.get('referer'),
                        
                        # Geographic enrichment
                        geo_location.get('country'),
                        geo_location.get('country_code'),
                        geo_location.get('region'),
                        geo_location.get('city'),
                        geo_location.get('latitude'),
                        geo_location.get('longitude'),
                        geo_location.get('isp'),
                        
                        # Device information
                        device_info.get('browser_family'),
                        device_info.get('browser_version'),
                        device_info.get('os_family'),
                        device_info.get('os_version'),
                        device_info.get('device_family'),
                        device_info.get('is_mobile', False),
                        device_info.get('is_bot', False),
                        
                        # URL analysis
                        url_analysis.get('domain'),
                        url_analysis.get('path'),
                        url_analysis.get('file_extension'),
                        url_analysis.get('is_static_resource', False),
                        url_analysis.get('is_api_endpoint', False),
                        url_analysis.get('is_admin_path', False),
                        
                        # Security analysis
                        security_analysis.get('threat_level', 'low'),
                        security_analysis.get('has_sql_injection', False),
                        security_analysis.get('has_xss_attempt', False),
                        security_analysis.get('has_path_traversal', False),
                        security_analysis.get('reputation_score', 0.0),
                        
                        # Metadata
                        enriched_data.get('data_quality_score', 0.0),
                        json.dumps(enriched_data),
                        datetime.now()
                    )
                    records.append(record)
                
                # Bulk insert using COPY
                await conn.copy_records_to_table(
                    'parsed_logs',
                    records=records,
                    columns=[
                        'source_name', 'filename', 'log_timestamp', 'ip_address',
                        'http_method', 'url', 'status_code', 'response_size',
                        'user_agent', 'referer', 'country', 'country_code',
                        'region', 'city', 'latitude', 'longitude', 'isp',
                        'browser_family', 'browser_version', 'os_family',
                        'os_version', 'device_family', 'is_mobile', 'is_bot',
                        'domain', 'path', 'file_extension', 'is_static_resource',
                        'is_api_endpoint', 'is_admin_path', 'threat_level',
                        'has_sql_injection', 'has_xss_attempt', 'has_path_traversal',
                        'reputation_score', 'data_quality_score', 'enriched_data',
                        'created_at'
                    ]
                )
                
                metrics.success_count = len(records)
                
        except Exception as e:
            logger.error(f"Error in bulk insert parsed logs: {e}")
            metrics.error_count = len(enriched_entries)
        
        metrics.end_time = datetime.now()
        metrics.processing_time = (metrics.end_time - metrics.start_time).total_seconds()
        
        return metrics


class AnalyticsEngine:
    """Real-time analytics and aggregation engine."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.analytics_interval = int(os.getenv('ANALYTICS_INTERVAL', '300'))  # 5 minutes
    
    async def update_statistics(self, log_entries: List[Dict[str, Any]]):
        """Update real-time statistics."""
        try:
            # Group entries by source and time window
            stats_by_source = defaultdict(lambda: {
                'total_requests': 0,
                'unique_ips': set(),
                'status_codes': defaultdict(int),
                'threat_levels': defaultdict(int),
                'countries': defaultdict(int),
                'browsers': defaultdict(int),
                'avg_response_size': 0,
                'total_response_size': 0
            })
            
            current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
            
            for entry in log_entries:
                enriched_data = entry.get('enriched_data', {})
                original_data = enriched_data.get('original_data', {})
                log_data = original_data.get('log_data', {})
                
                source_name = original_data.get('source_name', 'unknown')
                stats = stats_by_source[source_name]
                
                # Basic metrics
                stats['total_requests'] += 1
                if log_data.get('ip_address'):
                    stats['unique_ips'].add(log_data.get('ip_address'))
                
                # Status codes
                status_code = log_data.get('status_code')
                if status_code:
                    stats['status_codes'][status_code] += 1
                
                # Response size
                response_size = log_data.get('response_size', 0) or 0
                stats['total_response_size'] += response_size
                
                # Enriched data analytics
                geo_location = enriched_data.get('geo_location', {})
                device_info = enriched_data.get('device_info', {})
                security_analysis = enriched_data.get('security_analysis', {})
                
                if geo_location.get('country'):
                    stats['countries'][geo_location['country']] += 1
                
                if device_info.get('browser_family'):
                    stats['browsers'][device_info['browser_family']] += 1
                
                if security_analysis.get('threat_level'):
                    stats['threat_levels'][security_analysis['threat_level']] += 1
            
            # Update database with aggregated statistics
            await self._save_statistics(stats_by_source, current_hour)
            
        except Exception as e:
            logger.error(f"Error updating statistics: {e}")
    
    async def _save_statistics(self, stats_by_source: Dict, time_window: datetime):
        """Save aggregated statistics to database."""
        try:
            async with self.connection_manager.get_connection() as conn:
                for source_name, stats in stats_by_source.items():
                    # Calculate averages
                    avg_response_size = (
                        stats['total_response_size'] / stats['total_requests']
                        if stats['total_requests'] > 0 else 0
                    )
                    
                    # Upsert statistics
                    await conn.execute("""
                        INSERT INTO log_statistics (
                            source_name, time_window, total_requests, unique_ips,
                            avg_response_size, status_codes, threat_levels,
                            countries, browsers, created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $10)
                        ON CONFLICT (source_name, time_window)
                        DO UPDATE SET
                            total_requests = log_statistics.total_requests + $3,
                            unique_ips = log_statistics.unique_ips + $4,
                            avg_response_size = ($5 + log_statistics.avg_response_size) / 2,
                            status_codes = log_statistics.status_codes || $6,
                            threat_levels = log_statistics.threat_levels || $7,
                            countries = log_statistics.countries || $8,
                            browsers = log_statistics.browsers || $9,
                            updated_at = $10
                    """, 
                        source_name,
                        time_window,
                        stats['total_requests'],
                        len(stats['unique_ips']),
                        avg_response_size,
                        json.dumps(dict(stats['status_codes'])),
                        json.dumps(dict(stats['threat_levels'])),
                        json.dumps(dict(stats['countries'])),
                        json.dumps(dict(stats['browsers'])),
                        datetime.now()
                    )
                    
        except Exception as e:
            logger.error(f"Error saving statistics: {e}")


class EnhancedLoadService:
    """Enhanced load service with optimization and analytics."""
    
    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.bulk_inserter = BulkInserter(self.connection_manager)
        self.analytics_engine = AnalyticsEngine(self.connection_manager)
        
        # Message buffers
        self.raw_log_buffer = deque()
        self.enriched_log_buffer = deque()
        
        # Batch processing settings
        self.batch_size = int(os.getenv('BATCH_SIZE', '1000'))
        self.batch_timeout = int(os.getenv('BATCH_TIMEOUT', '30'))
        
        # Kafka configuration
        kafka_config = {
            'bootstrap.servers': os.getenv('KAFKA_BROKER', 'kafka:29092'),
            'group.id': 'enhanced-load-service',
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False
        }
        
        self.consumer = Consumer(kafka_config)
        self.consumer.subscribe(['enriched-logs'])
        
        # Performance metrics
        self.performance_metrics = {
            'total_processed': 0,
            'total_errors': 0,
            'avg_batch_time': 0.0,
            'records_per_second': 0.0
        }
    
    async def start_processing(self):
        """Start processing messages with batch optimization."""
        logger.info("Starting enhanced load service...")
        
        await self.connection_manager.initialize_pool()
        
        # Start batch processing task
        batch_task = asyncio.create_task(self._process_batches())
        
        try:
            while True:
                msg = self.consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    logger.error(f"Consumer error: {msg.error()}")
                    continue
                
                try:
                    # Parse message
                    log_data = json.loads(msg.value().decode('utf-8'))
                    
                    # Add to appropriate buffer
                    if log_data.get('processing_stage') == 'transform_complete':
                        self.enriched_log_buffer.append(log_data)
                    else:
                        self.raw_log_buffer.append(log_data)
                    
                    # Commit offset
                    self.consumer.commit(msg)
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self.performance_metrics['total_errors'] += 1
        
        except KeyboardInterrupt:
            logger.info("Shutting down load service...")
        finally:
            batch_task.cancel()
            await self.connection_manager.close_pool()
            self.consumer.close()
    
    async def _process_batches(self):
        """Process batched messages."""
        while True:
            try:
                # Process enriched logs batch
                if len(self.enriched_log_buffer) >= self.batch_size:
                    batch = [self.enriched_log_buffer.popleft() 
                            for _ in range(min(self.batch_size, len(self.enriched_log_buffer)))]
                    
                    metrics = await self.bulk_inserter.bulk_insert_parsed_logs(batch)
                    await self.analytics_engine.update_statistics(batch)
                    
                    self._update_performance_metrics(metrics)
                    
                    logger.info(
                        f"Processed enriched batch: {metrics.success_count} records, "
                        f"{metrics.processing_time:.2f}s"
                    )
                
                # Process raw logs batch
                if len(self.raw_log_buffer) >= self.batch_size:
                    batch = [self.raw_log_buffer.popleft() 
                            for _ in range(min(self.batch_size, len(self.raw_log_buffer)))]
                    
                    metrics = await self.bulk_inserter.bulk_insert_raw_logs(batch)
                    self._update_performance_metrics(metrics)
                    
                    logger.info(
                        f"Processed raw batch: {metrics.success_count} records, "
                        f"{metrics.processing_time:.2f}s"
                    )
                
                # Wait before next batch check
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in batch processing: {e}")
                await asyncio.sleep(5)
    
    def _update_performance_metrics(self, batch_metrics: BatchMetrics):
        """Update performance metrics."""
        self.performance_metrics['total_processed'] += batch_metrics.success_count
        self.performance_metrics['total_errors'] += batch_metrics.error_count
        
        # Update average batch time
        current_avg = self.performance_metrics['avg_batch_time']
        new_avg = (current_avg + batch_metrics.processing_time) / 2
        self.performance_metrics['avg_batch_time'] = new_avg
        
        # Calculate records per second
        if batch_metrics.processing_time > 0:
            rps = batch_metrics.success_count / batch_metrics.processing_time
            current_rps = self.performance_metrics['records_per_second']
            self.performance_metrics['records_per_second'] = (current_rps + rps) / 2
    
    async def get_performance_stats(self) -> DatabaseStats:
        """Get current performance statistics."""
        try:
            async with self.connection_manager.get_connection() as conn:
                # Get total record counts
                raw_count = await conn.fetchval("SELECT COUNT(*) FROM raw_logs")
                parsed_count = await conn.fetchval("SELECT COUNT(*) FROM parsed_logs")
                
                return DatabaseStats(
                    total_records=raw_count + parsed_count,
                    records_per_second=self.performance_metrics['records_per_second'],
                    avg_processing_time=self.performance_metrics['avg_batch_time'],
                    connection_pool_size=self.connection_manager.pool.get_size() if self.connection_manager.pool else 0,
                    active_connections=self.connection_manager.pool.get_size() - self.connection_manager.pool.get_idle_size() if self.connection_manager.pool else 0
                )
        except Exception as e:
            logger.error(f"Error getting performance stats: {e}")
            return DatabaseStats()


async def main():
    """Main entry point."""
    service = EnhancedLoadService()
    await service.start_processing()


if __name__ == "__main__":
    asyncio.run(main())
