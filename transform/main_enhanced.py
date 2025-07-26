"""
Enhanced Transform Service with GeoIP, User Agent, and URL Analysis
Enriches log data with geographic, device, and security intelligence.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import re
import asyncio
import aiohttp
import os
import logging
from logging.handlers import RotatingFileHandler
from confluent_kafka import Consumer, Producer
from user_agents import parse as parse_user_agent
import geoip2.database
import geoip2.errors
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
import hashlib
import ipaddress

# Load environment variables
load_dotenv()

# Set up logging
os.makedirs('/app/logs', exist_ok=True)
file_handler = RotatingFileHandler('/app/logs/transform.log', maxBytes=10485760, backupCount=5)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[file_handler, logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


@dataclass
class GeoLocation:
    """Geographic location data."""
    country: Optional[str] = None
    country_code: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    isp: Optional[str] = None
    is_anonymous_proxy: bool = False
    is_satellite_provider: bool = False


@dataclass
class DeviceInfo:
    """User agent device information."""
    browser_family: Optional[str] = None
    browser_version: Optional[str] = None
    os_family: Optional[str] = None
    os_version: Optional[str] = None
    device_family: Optional[str] = None
    device_brand: Optional[str] = None
    device_model: Optional[str] = None
    is_mobile: bool = False
    is_tablet: bool = False
    is_pc: bool = False
    is_bot: bool = False


@dataclass
class URLAnalysis:
    """URL analysis and categorization."""
    domain: Optional[str] = None
    path: Optional[str] = None
    parameters: Dict[str, List[str]] = None
    file_extension: Optional[str] = None
    is_static_resource: bool = False
    is_api_endpoint: bool = False
    is_admin_path: bool = False
    suspicious_patterns: List[str] = None
    query_complexity: int = 0
    path_depth: int = 0


@dataclass
class SecurityAnalysis:
    """Security threat analysis."""
    threat_level: str = "low"  # low, medium, high, critical
    threat_types: List[str] = None
    is_malicious_ip: bool = False
    has_sql_injection: bool = False
    has_xss_attempt: bool = False
    has_path_traversal: bool = False
    has_command_injection: bool = False
    suspicious_user_agent: bool = False
    reputation_score: float = 0.0


@dataclass
class EnrichedLogEntry:
    """Complete enriched log entry."""
    # Original log data
    original_data: Dict[str, Any]
    
    # Enriched data
    geo_location: Optional[GeoLocation] = None
    device_info: Optional[DeviceInfo] = None
    url_analysis: Optional[URLAnalysis] = None
    security_analysis: Optional[SecurityAnalysis] = None
    
    # Processing metadata
    processing_timestamp: datetime = None
    enrichment_version: str = "2.0.0"
    data_quality_score: float = 0.0


class GeoIPEnricher:
    """GeoIP data enrichment service."""
    
    def __init__(self):
        self.city_db_path = "/app/data/geoip/GeoLite2-City.mmdb"
        self.asn_db_path = "/app/data/geoip/GeoLite2-ASN.mmdb"
        self.city_reader = None
        self.asn_reader = None
        
        self._initialize_databases()
    
    def _initialize_databases(self):
        """Initialize GeoIP databases."""
        try:
            if os.path.exists(self.city_db_path):
                self.city_reader = geoip2.database.Reader(self.city_db_path)
                logger.info("GeoIP City database loaded successfully")
            else:
                logger.warning(f"GeoIP City database not found at {self.city_db_path}")
            
            if os.path.exists(self.asn_db_path):
                self.asn_reader = geoip2.database.Reader(self.asn_db_path)
                logger.info("GeoIP ASN database loaded successfully")
            else:
                logger.warning(f"GeoIP ASN database not found at {self.asn_db_path}")
                
        except Exception as e:
            logger.error(f"Error initializing GeoIP databases: {e}")
    
    def enrich_ip(self, ip_address: str) -> Optional[GeoLocation]:
        """Enrich IP address with geographic data."""
        if not ip_address or not self._is_valid_ip(ip_address):
            return None
        
        geo_location = GeoLocation()
        
        try:
            # Get city/location data
            if self.city_reader:
                try:
                    response = self.city_reader.city(ip_address)
                    geo_location.country = response.country.name
                    geo_location.country_code = response.country.iso_code
                    geo_location.region = response.subdivisions.most_specific.name
                    geo_location.city = response.city.name
                    geo_location.latitude = float(response.location.latitude) if response.location.latitude else None
                    geo_location.longitude = float(response.location.longitude) if response.location.longitude else None
                    geo_location.timezone = response.location.time_zone
                    geo_location.is_anonymous_proxy = response.traits.is_anonymous_proxy
                    geo_location.is_satellite_provider = response.traits.is_satellite_provider
                except geoip2.errors.AddressNotFoundError:
                    logger.debug(f"IP address {ip_address} not found in city database")
            
            # Get ISP/ASN data
            if self.asn_reader:
                try:
                    asn_response = self.asn_reader.asn(ip_address)
                    geo_location.isp = asn_response.autonomous_system_organization
                except geoip2.errors.AddressNotFoundError:
                    logger.debug(f"IP address {ip_address} not found in ASN database")
            
            return geo_location
            
        except Exception as e:
            logger.error(f"Error enriching IP {ip_address}: {e}")
            return geo_location
    
    @staticmethod
    def _is_valid_ip(ip_address: str) -> bool:
        """Validate IP address."""
        try:
            ipaddress.ip_address(ip_address)
            return True
        except ValueError:
            return False


class UserAgentAnalyzer:
    """User agent analysis and device detection."""
    
    # Bot patterns
    BOT_PATTERNS = [
        r'bot', r'crawler', r'spider', r'scraper', r'curl', r'wget',
        r'python-requests', r'apache-httpclient', r'java/', r'okhttp'
    ]
    
    # Suspicious user agent patterns
    SUSPICIOUS_PATTERNS = [
        r'<script', r'javascript:', r'eval\(', r'document\.', r'window\.',
        r'alert\(', r'prompt\(', r'confirm\(', r'\.\./', r'%2e%2e%2f'
    ]
    
    @classmethod
    def analyze_user_agent(cls, user_agent: str) -> DeviceInfo:
        """Analyze user agent string."""
        if not user_agent:
            return DeviceInfo()
        
        device_info = DeviceInfo()
        
        try:
            # Parse with user-agents library
            parsed = parse_user_agent(user_agent)
            
            device_info.browser_family = parsed.browser.family
            device_info.browser_version = parsed.browser.version_string
            device_info.os_family = parsed.os.family
            device_info.os_version = parsed.os.version_string
            device_info.device_family = parsed.device.family
            device_info.device_brand = parsed.device.brand
            device_info.device_model = parsed.device.model
            
            device_info.is_mobile = parsed.is_mobile
            device_info.is_tablet = parsed.is_tablet
            device_info.is_pc = parsed.is_pc
            
            # Check for bots
            device_info.is_bot = cls._is_bot(user_agent)
            
        except Exception as e:
            logger.error(f"Error parsing user agent: {e}")
        
        return device_info
    
    @classmethod
    def _is_bot(cls, user_agent: str) -> bool:
        """Check if user agent is a bot."""
        user_agent_lower = user_agent.lower()
        return any(re.search(pattern, user_agent_lower) for pattern in cls.BOT_PATTERNS)


class URLAnalyzer:
    """URL analysis and categorization."""
    
    # Static resource extensions
    STATIC_EXTENSIONS = {
        '.css', '.js', '.jpg', '.jpeg', '.png', '.gif', '.ico', '.svg',
        '.woff', '.woff2', '.ttf', '.eot', '.mp4', '.mp3', '.pdf'
    }
    
    # API patterns
    API_PATTERNS = [
        r'/api/', r'/v\d+/', r'\.json$', r'\.xml$', r'/rest/', r'/graphql'
    ]
    
    # Admin/sensitive paths
    ADMIN_PATTERNS = [
        r'/admin', r'/administrator', r'/wp-admin', r'/phpmyadmin',
        r'/cpanel', r'/webmail', r'/manager', r'/console'
    ]
    
    # Suspicious patterns
    SUSPICIOUS_PATTERNS = [
        r'\.\./', r'%2e%2e%2f', r'/etc/passwd', r'/proc/', r'cmd=',
        r'exec\(', r'system\(', r'passthru\(', r'shell_exec\('
    ]
    
    @classmethod
    def analyze_url(cls, url: str) -> URLAnalysis:
        """Analyze URL for patterns and categorization."""
        if not url:
            return URLAnalysis()
        
        analysis = URLAnalysis()
        analysis.parameters = {}
        analysis.suspicious_patterns = []
        
        try:
            parsed = urlparse(url)
            
            analysis.domain = parsed.netloc
            analysis.path = parsed.path
            
            # Parse query parameters
            if parsed.query:
                analysis.parameters = parse_qs(parsed.query)
                analysis.query_complexity = len(analysis.parameters)
            
            # Get file extension
            if '.' in parsed.path:
                analysis.file_extension = parsed.path.split('.')[-1].lower()
            
            # Path analysis
            path_parts = [part for part in parsed.path.split('/') if part]
            analysis.path_depth = len(path_parts)
            
            # Categorization
            analysis.is_static_resource = (
                analysis.file_extension and 
                f'.{analysis.file_extension}' in cls.STATIC_EXTENSIONS
            )
            
            analysis.is_api_endpoint = any(
                re.search(pattern, url, re.IGNORECASE) 
                for pattern in cls.API_PATTERNS
            )
            
            analysis.is_admin_path = any(
                re.search(pattern, url, re.IGNORECASE) 
                for pattern in cls.ADMIN_PATTERNS
            )
            
            # Security analysis
            for pattern in cls.SUSPICIOUS_PATTERNS:
                if re.search(pattern, url, re.IGNORECASE):
                    analysis.suspicious_patterns.append(pattern)
            
        except Exception as e:
            logger.error(f"Error analyzing URL {url}: {e}")
        
        return analysis


class SecurityAnalyzer:
    """Security threat analysis."""
    
    # SQL injection patterns
    SQL_PATTERNS = [
        r"(\%27)|(\')|(\-\-)|(\%23)|(#)",
        r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))",
        r"\w*((\%27)|(\'))((\%6F)|o|(\%4F))((\%72)|r|(\%52))",
        r"((\%27)|(\'))union",
        r"exec(\s|\+)+(s|x)p\w+"
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"vbscript:",
        r"onload\s*=",
        r"onerror\s*=",
        r"onclick\s*="
    ]
    
    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\.\/",
        r"\.\.\\",
        r"%2e%2e%2f",
        r"%2e%2e%5c"
    ]
    
    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        r";\s*(cat|ls|pwd|id|uname)",
        r"\|\s*(cat|ls|pwd|id|uname)",
        r"&&\s*(cat|ls|pwd|id|uname)",
        r";\s*rm\s+",
        r"\|\s*rm\s+"
    ]
    
    @classmethod
    def analyze_security(
        cls, 
        ip_address: str = None, 
        url: str = None, 
        user_agent: str = None,
        request_body: str = None
    ) -> SecurityAnalysis:
        """Perform comprehensive security analysis."""
        
        analysis = SecurityAnalysis()
        analysis.threat_types = []
        threats_found = 0
        
        # Combine all text for analysis
        all_text = ' '.join(filter(None, [url, user_agent, request_body]))
        
        # SQL Injection detection
        if cls._check_patterns(all_text, cls.SQL_PATTERNS):
            analysis.has_sql_injection = True
            analysis.threat_types.append("sql_injection")
            threats_found += 1
        
        # XSS detection
        if cls._check_patterns(all_text, cls.XSS_PATTERNS):
            analysis.has_xss_attempt = True
            analysis.threat_types.append("xss")
            threats_found += 1
        
        # Path traversal detection
        if cls._check_patterns(all_text, cls.PATH_TRAVERSAL_PATTERNS):
            analysis.has_path_traversal = True
            analysis.threat_types.append("path_traversal")
            threats_found += 1
        
        # Command injection detection
        if cls._check_patterns(all_text, cls.COMMAND_INJECTION_PATTERNS):
            analysis.has_command_injection = True
            analysis.threat_types.append("command_injection")
            threats_found += 1
        
        # Suspicious user agent
        if user_agent and cls._is_suspicious_user_agent(user_agent):
            analysis.suspicious_user_agent = True
            analysis.threat_types.append("suspicious_user_agent")
            threats_found += 1
        
        # Calculate threat level
        if threats_found == 0:
            analysis.threat_level = "low"
            analysis.reputation_score = 1.0
        elif threats_found <= 2:
            analysis.threat_level = "medium"
            analysis.reputation_score = 0.5
        elif threats_found <= 4:
            analysis.threat_level = "high"
            analysis.reputation_score = 0.2
        else:
            analysis.threat_level = "critical"
            analysis.reputation_score = 0.0
        
        return analysis
    
    @classmethod
    def _check_patterns(cls, text: str, patterns: List[str]) -> bool:
        """Check if text matches any of the patterns."""
        if not text:
            return False
        
        text_lower = text.lower()
        return any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in patterns)
    
    @classmethod
    def _is_suspicious_user_agent(cls, user_agent: str) -> bool:
        """Check for suspicious user agent patterns."""
        suspicious_patterns = [
            r'<script', r'javascript:', r'eval\(', r'document\.',
            r'window\.', r'alert\(', r'\.\./', r'%2e%2e%2f'
        ]
        return cls._check_patterns(user_agent, suspicious_patterns)


class EnhancedTransformService:
    """Enhanced transform service with enrichment capabilities."""
    
    def __init__(self):
        self.geo_enricher = GeoIPEnricher()
        
        # Kafka configuration
        kafka_config = {
            'bootstrap.servers': os.getenv('KAFKA_BROKER', 'kafka:29092'),
            'group.id': 'enhanced-transform-service',
            'auto.offset.reset': 'earliest'
        }
        
        self.consumer = Consumer(kafka_config)
        self.producer = Producer({
            'bootstrap.servers': os.getenv('KAFKA_BROKER', 'kafka:29092'),
            'client.id': 'enhanced-transform-service'
        })
        
        self.consumer.subscribe(['parsed-logs'])
        
    async def start_processing(self):
        """Start processing messages from Kafka."""
        logger.info("Starting enhanced transform service...")
        
        try:
            while True:
                msg = self.consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    logger.error(f"Consumer error: {msg.error()}")
                    continue
                
                try:
                    # Process message
                    log_data = json.loads(msg.value().decode('utf-8'))
                    enriched_entry = await self._enrich_log_entry(log_data)
                    
                    # Send enriched data to next stage
                    await self._send_to_load_service(enriched_entry)
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                
        except KeyboardInterrupt:
            logger.info("Shutting down transform service...")
        finally:
            self.consumer.close()
    
    async def _enrich_log_entry(self, log_data: Dict[str, Any]) -> EnrichedLogEntry:
        """Enrich log entry with all available data."""
        
        enriched = EnrichedLogEntry(
            original_data=log_data,
            processing_timestamp=datetime.now()
        )
        
        # Extract relevant fields
        ip_address = log_data.get('log_data', {}).get('ip_address')
        url = log_data.get('log_data', {}).get('url')
        user_agent = log_data.get('log_data', {}).get('user_agent')
        
        try:
            # GeoIP enrichment
            if ip_address:
                enriched.geo_location = self.geo_enricher.enrich_ip(ip_address)
            
            # User agent analysis
            if user_agent:
                enriched.device_info = UserAgentAnalyzer.analyze_user_agent(user_agent)
            
            # URL analysis
            if url:
                enriched.url_analysis = URLAnalyzer.analyze_url(url)
            
            # Security analysis
            enriched.security_analysis = SecurityAnalyzer.analyze_security(
                ip_address=ip_address,
                url=url,
                user_agent=user_agent
            )
            
            # Calculate data quality score
            enriched.data_quality_score = self._calculate_quality_score(enriched)
            
        except Exception as e:
            logger.error(f"Error during enrichment: {e}")
        
        return enriched
    
    def _calculate_quality_score(self, enriched: EnrichedLogEntry) -> float:
        """Calculate data quality score based on available enrichments."""
        score = 0.0
        max_score = 4.0
        
        if enriched.geo_location and enriched.geo_location.country:
            score += 1.0
        
        if enriched.device_info and enriched.device_info.browser_family:
            score += 1.0
        
        if enriched.url_analysis and enriched.url_analysis.domain:
            score += 1.0
        
        if enriched.security_analysis:
            score += 1.0
        
        return score / max_score
    
    async def _send_to_load_service(self, enriched_entry: EnrichedLogEntry):
        """Send enriched data to load service."""
        
        try:
            message = {
                "message_id": f"enriched_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "timestamp": datetime.now().isoformat(),
                "enriched_data": asdict(enriched_entry),
                "processing_stage": "transform_complete"
            }
            
            # Convert datetime objects to strings for JSON serialization
            def json_serializer(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return str(obj)
            
            self.producer.produce(
                'enriched-logs',
                key=enriched_entry.original_data.get('source_name', 'unknown'),
                value=json.dumps(message, default=json_serializer),
                callback=self._delivery_report
            )
            
            self.producer.flush()
            
        except Exception as e:
            logger.error(f"Error sending enriched data: {e}")
    
    def _delivery_report(self, err, msg):
        """Kafka delivery callback."""
        if err is not None:
            logger.error(f'Message delivery failed: {err}')
        else:
            logger.debug(f'Enriched message delivered to {msg.topic()}')


async def main():
    """Main entry point."""
    service = EnhancedTransformService()
    await service.start_processing()


if __name__ == "__main__":
    asyncio.run(main())
