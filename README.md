# Kafka ETL Pipeline

A distributed ETL (Extract, Transform, Load) pipeline built with Python, Apache Kafka, and PostgreSQL.

## Architecture

The project consists of three microservices:

1. **Extract Service**: Receives input data and publishes to Kafka
2. **Transform Service**: Processes data from Kafka and republishes
3. **Load Service**: Consumes transformed data and stores in PostgreSQL

### Components

- **Apache Kafka**: Message broker for data streaming
- **PostgreSQL**: Data storage
- **Kafka UI**: Web interface for monitoring Kafka
- **FastAPI**: Web framework for microservices
- **Docker**: Containerization and orchestration

## Project Structure

```
.
├── docker-compose.yml           # Docker services configuration
├── .env                        # Environment variables (not in version control)
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore file
├── version.txt                # Version tracking file
├── registry.env               # Registry configuration template
├── registry.env.local         # Local registry configuration (not in version control)
├── build_and_push.sh          # Build and push automation script
├── setup_registry.sh          # Registry setup and configuration script
├── DEPLOYMENT_OPTIONS.sh      # Deployment scenarios documentation
├── DOCKER_IMAGES_STATUS.sh    # Docker images status and information
├── REMOTE_DB_STATUS.sh        # Remote database status and testing
├── setup_remote_db.py         # Remote database setup script
├── test_remote_db.py          # Remote database connectivity testing
├── extract/                   # Extract service
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── transform/                 # Transform service
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── load/                      # Load service
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
└── k8s/                       # Kubernetes deployment manifests
    └── deployment.yaml
```

## Configuration

The project uses environment variables for configuration. Create a `.env` file with the following variables:

```env
# PostgreSQL Configuration
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=your_db
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Kafka Configuration
KAFKA_CLUSTER_ID=your_cluster_id
KAFKA_BROKER_ID=1
KAFKA_NODE_ID=1
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
KAFKA_EXTERNAL_BOOTSTRAP_SERVERS=localhost:9092

# Kafka UI Configuration
KAFKA_UI_PORT=8080
KAFKA_UI_CLUSTER_NAME=local
```

## Services

### Extract Service (Port: 8001)
- Receives data via REST API
- Publishes to `raw-data` Kafka topic
- Generates unique message IDs
- Handles data validation

### Transform Service (Port: 8002)
- Consumes from `raw-data` topic
- Transforms data
- Publishes to `transformed-data` topic
- Maintains message tracking

### Load Service (Port: 8003)
- Consumes from `transformed-data` topic
- Stores data in PostgreSQL
- Manages database schema
- Tracks message processing

## Database Schema

### processed_data
- `id`: Serial Primary Key
- `message_id`: Unique identifier
- `original_source`: Data source
- `original_timestamp`: Extraction time
- `transform_timestamp`: Processing time
- `load_timestamp`: Storage time
- `data`: JSONB data

### message_tracking
- `message_id`: Primary Key
- `source`: Data source
- `extract_timestamp`: Extraction time
- `transform_timestamp`: Transform time
- `load_timestamp`: Load time
- `status`: Processing status
- `metadata`: JSONB metadata

## End-to-End Testing

The project includes a comprehensive end-to-end test suite (`e2e_test.py`) that verifies the entire ETL pipeline:

### Test Components
- Data injection into Extract Service
- Message processing through Kafka
- Data transformation verification
- Database storage validation

### Running Tests
```bash
# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install requests psycopg2-binary

# Run the test
python e2e_test.py
```

### Test Report
The test generates a detailed report (`etl_test_report.log`) containing:
- Input data validation
- Service responses
- Processing steps
- Data transformations
- Final database state
- Integrity verification

### Success Criteria
- Extract Service data acceptance
- Kafka message propagation
- Transform Service processing
- Load Service database storage
- Data integrity maintenance

## Getting Started

1. Clone the repository
2. Create `.env` file with required variables
3. Start the services:
   ```bash
   docker compose up -d
   ```
4. Access services:
   - Extract API: http://localhost:8001
   - Transform API: http://localhost:8002
   - Load API: http://localhost:8003
   - Kafka UI: http://localhost:8080

## API Endpoints

### Extract Service
- `POST /extract`: Submit data for processing
- `GET /`: Service information
- `GET /health`: Health check

### Transform Service
- `GET /`: Service information
- `GET /health`: Health check

### Load Service
- `GET /`: Service information
- `GET /health`: Health check

## Recent Updates (July 10, 2025)

1. Enhanced Database Configuration
   - Added SSL support for secure remote database connections
   - Implemented connection pooling for better performance
   - Enhanced database schema with tracking columns
   - Added performance optimization indexes
   - Added retry and error tracking in message_tracking table

2. Kubernetes Configuration
   - Created k8s/deployment.yaml with:
     - Deployments for each service (2 replicas each)
     - ConfigMap for configuration
     - Secrets for sensitive data
     - Health checks and probes
     - Services and Ingress configuration

3. Docker Registry Preparation
   - Added build_and_push.sh script for image management
   - Prepared for private registry deployment

4. Implemented Full Data Persistence
   - Added named volumes for all services:
     - PostgreSQL data (etl_pgdata)
     - Kafka data (etl_kafka_data)
     - Kafka logs (etl_kafka_logs)
     - Application logs for each service
   - Configured automatic container restart
   - Added health checks for service monitoring
   - Implemented rotating log files
   - Verified data persistence across container restarts

## Latest Updates (July 11, 2025)

### Remote Database Integration Completed ✅
1. **PostgreSQL Remote Database Setup**
   - Configured remote PostgreSQL server at `192.168.0.190:5432`
   - Database: `etldb`, User: ``, Password: ``
   - SSL mode set to `prefer` for secure connections
   - Connection pooling: 20 connections with 10 overflow, 30-second timeout

2. **Enhanced Load Service**
   - Added graceful degradation for database unavailability
   - Implemented 5-attempt retry logic with 10-second intervals
   - Services start in degraded mode when database is unreachable
   - Comprehensive error handling and logging

3. **Docker Images Built and Ready**
   - Successfully built production-ready Docker images:
     - `etl-extract:latest` (188MB)
     - `etl-transform:latest` (188MB)
     - `etl-load:latest` (195MB)
   - Tagged with version `remote-db-v1.0.0` for deployment tracking
   - Images configured for Docker Hub registry publishing

4. **Updated Configuration Files**
   - **`.env`**: Updated `POSTGRES_HOST` from `db` to ``
   - **`docker-compose.yml`**: Modified to use pre-built images instead of build contexts
   - **`k8s/deployment.yaml`**: Updated ConfigMap with remote database settings
   - All services tested and validated with remote database configuration

5. **Deployment Scripts and Documentation**
   - **`build_and_push.sh`**: Automated Docker image building and registry pushing
   - **`DEPLOYMENT_OPTIONS.sh`**: Comprehensive deployment scenarios documentation
   - **`DOCKER_IMAGES_STATUS.sh`**: Docker image status and registry information
   - **`REMOTE_DB_STATUS.sh`**: Remote database connection testing and status
   - **`setup_remote_db.py`**: Database setup and schema creation script
   - **`test_remote_db.py`**: Remote database connectivity testing

6. **Production Readiness Features**
   - **Health Checks**: All services have `/health` endpoints
   - **Graceful Degradation**: Services continue running when database is unavailable
   - **Connection Pooling**: Optimized database connections for production load
   - **SSL Support**: Secure database connections with SSL preference
   - **Kubernetes Ready**: Complete deployment manifests with secrets and config maps

### Git Repository Integration ✅
- Repository initialized and pushed to GitHub: `https://github.com/RishiShrivastava/pykaftestapp.git`
- All 21 files committed with comprehensive project structure
- Ready for collaborative development and CI/CD integration

### Current Status
- **Docker Images**: Built and tested locally with remote database configuration
- **Services**: All three services (Extract, Transform, Load) operational
- **Database**: Remote PostgreSQL at  configured (requires manual setup)
- **Deployment**: Ready for Docker Hub publishing and Kubernetes deployment



Starting Point for :
1. Remote Database Setup
   ```
   Host: your-remote-db-host
   Port: 5432
   Database: etldb
   User: 
   ```
   - Generate and configure SSL certificates
   - Update connection parameters in .env
   - Test remote connection
   - Migrate existing data

## Development

### Requirements
- Docker and Docker Compose
- Python 3.11+
- PostgreSQL 15
- Kafka 7.5.0

### Local Development
1. Copy `.env.example` to `.env`
2. Update environment variables
3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start services with Docker Compose

## Notes
- Keep `.env` file secure and never commit to version control
- Monitor Kafka UI for message flow
- Check service health endpoints for status
- Use proper error handling in production

## Deployment Commands

### Local Development with Remote Database
```bash
# Start services with remote database
docker compose up -d

# Check service status
docker compose ps

# View logs
docker compose logs -f extract
docker compose logs -f transform
docker compose logs -f load

# Test service endpoints
curl http://localhost:8001/health  # Extract service
curl http://localhost:8002/health  # Transform service
curl http://localhost:8003/health  # Load service
```

### Docker Image Management
```bash
# Build all images
docker compose build

# Build and push to registry
./build_and_push.sh

# Check image status
./DOCKER_IMAGES_STATUS.sh

# View deployment options
./DEPLOYMENT_OPTIONS.sh
```

### Remote Database Setup
```bash
# Test remote database connection
python test_remote_db.py

# Set up remote database schema
python setup_remote_db.py

# Check remote database status
./REMOTE_DB_STATUS.sh
```

### Kubernetes Deployment
```bash
# Deploy to Kubernetes cluster
kubectl apply -f k8s/deployment.yaml

# Check deployment status
kubectl get deployments
kubectl get pods
kubectl get services

# View pod logs
kubectl logs -f deployment/extract-service
kubectl logs -f deployment/transform-service
kubectl logs -f deployment/load-service

# Port forward for local access
kubectl port-forward service/extract-service 8001:8000
kubectl port-forward service/transform-service 8002:8000
kubectl port-forward service/load-service 8003:8000
```

### Environment Configuration
```bash
# Copy example environment file
cp .env.example .env

# Edit with your specific values
nano .env

# Key configurations for remote database:
POSTGRES_HOST=192.168.0.190
POSTGRES_PORT=5432
POSTGRES_USER=etluser
POSTGRES_PASSWORD=
POSTGRES_DB=etldb
POSTGRES_SSL_MODE=prefer
DB_POOL_SIZE=20
DB_POOL_OVERFLOW=10
DB_POOL_TIMEOUT=30
```

### Docker Registry Setup and Authentication
```bash
# Configure Docker registry securely
./setup_registry.sh

# Options available:
# 1. Docker Hub (hub.docker.com)
# 2. Private Registry
# 3. Local Registry
# 4. Show current configuration

# Login to Docker Hub
docker login

# For credential store issues on Linux:
mkdir -p ~/.docker
echo '{"credsStore": ""}' > ~/.docker/config.json

# Using personal access token (recommended for CI/CD)
echo 'your-access-token' | docker login -u your-username --password-stdin
```

### Version Management
```bash
# Show current version
./build_and_push.sh version

# Increment version types
./build_and_push.sh patch      # 1.0.0 → 1.0.1
./build_and_push.sh minor      # 1.0.0 → 1.1.0  
./build_and_push.sh major      # 1.0.0 → 2.0.0

# Build with version increment
./build_and_push.sh push patch # Increment patch, build, and push
```

### Registry Configuration Files
```bash
# Create secure registry configuration
cp registry.env.example registry.env.local

# Edit with your registry details
nano registry.env.local

# Example registry.env.local content:
export DOCKER_REGISTRY=your-username
export IMAGE_VERSION=1.0.0
```

### Troubleshooting Docker Issues
```bash
# Fix Docker credential store error on Linux
mkdir -p ~/.docker
echo '{"credsStore": ""}' > ~/.docker/config.json

# Check Docker login status
docker info | grep -i username

# Check current registry configuration
./setup_registry.sh
# Choose option 4 to show current configuration

# Verify Docker daemon is running
docker info

# Check Docker version
docker --version
```


## Security Considerations (Auto-Scanned)



### Example: Secure Dockerfile (multi-stage, minimal copy)
```
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY main.py ./
# Do NOT copy .env or secrets
```

### Example: Secure Kubernetes Secret Management
- Use sealed-secrets, Vault, or cloud secret managers
- Never store real secrets in version-controlled YAML

### General Best Practices
- Never log secrets or full connection strings
- Rotate credentials regularly
- Use access tokens for CI/CD
- Review `.dockerignore` and `.gitignore` regularly

---
**These issues and recommendations were auto-generated by a security scan of your codebase.**
