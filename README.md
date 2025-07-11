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
├── docker-compose.yml    # Docker services configuration
├── .env                 # Environment variables (not in version control)
├── .gitignore          # Git ignore file
├── extract/            # Extract service
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── transform/          # Transform service
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
└── load/              # Load service
    ├── Dockerfile
    ├── main.py
    └── requirements.txt
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

### Security Requirements

**⚠️ IMPORTANT SECURITY NOTICE:**

The following environment variables are **REQUIRED** and **MUST** be set for the application to start:

- `DB_USER` (or `POSTGRES_USER`): Database username
- `DB_PASSWORD` (or `POSTGRES_PASSWORD`): Database password

These variables have **NO DEFAULT VALUES** for security reasons. The application will refuse to start if these are not explicitly set in your environment.

**Security Best Practices:**
- Never use weak or default credentials in production
- Use strong, unique passwords for database connections
- Store sensitive credentials securely using environment variables or secrets management systems
- Never commit credentials to version control

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

## Getting Started

1. Clone the repository
2. Create `.env` file with required variables (**⚠️ Must include DB_USER and DB_PASSWORD - see Security Requirements above**)
3. Start the services:
   ```bash
   docker compose up -d
   ```
4. Access services:
   - Extract API: http://localhost:8001
   - Transform API: http://localhost:8002
   - Load API: http://localhost:8003
   - Kafka UI: http://localhost:8080

**Note:** The Load service will fail to start if `DB_USER` and `DB_PASSWORD` environment variables are not set.

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

## Next Steps (July 11, 2025)

1. Remote Database Integration
   - Set up remote PostgreSQL instance
   - Configure SSL certificates and connection
   - Update connection strings
   - Migrate local data to remote database
   - Test connection pooling and failover

2. Docker Image Publishing
   - Set up Docker Hub repository access
   - Update image tags for your repository
   - Push images to Docker Hub:
     - etl-extract
     - etl-transform
     - etl-load
   - Test image pull from registry

3. Kubernetes Deployment
   - Configure access to your Kubernetes cluster
   - Update deployment manifests with new image paths
   - Set up secrets for remote database
   - Deploy services to cluster
   - Configure ingress and DNS
   - Test end-to-end functionality

Starting Point for Tomorrow:
1. Remote Database Setup
   ```
   Host: your-remote-db-host
   Port: 5432
   Database: etldb
   User: etluser
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


Let me explain what we've done and what needs to be configured to deploy the application:

Database Configuration:
Added SSL and connection pooling support
Enhanced schema with additional columns for tracking and timestamps
Added performance optimization with proper indexes
Implemented connection pooling for better resource management
Kubernetes Configuration (k8s/deployment.yaml):
Created separate deployments for each service with 2 replicas
Set up ConfigMap for configuration and Secrets for sensitive data
Added health checks (liveness and readiness probes)
Configured services and ingress for routing
Docker Registry Setup:
Created build_and_push.sh script for automated image building and pushing
Made the script executable
To deploy this application, you'll need to:

Update the following in k8s/deployment.yaml:
Replace your-registry.com with your private registry URL
Replace your-remote-db-host with your remote PostgreSQL host
Update etl.your-domain.com with your actual domain
Update build_and_push.sh:
Replace your-registry.com with your private registry URL
Deploy to Kubernetes:
# Create secrets and configmap
kubectl apply -f k8s/deployment.yaml

# Verify deployments
kubectl get deployments
kubectl get pods
kubectl get services
kubectl get ingress
Monitor the deployment:
# Check pod logs
kubectl logs -f deployment/extract-service
kubectl logs -f deployment/transform-service
kubectl logs -f deployment/load-service

# Check pod status
kubectl describe pods

Would you like me to help you configure any specific part of the deployment or explain anything in more detail?