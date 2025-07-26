#!/bin/bash
# restore.sh
# Created by Rishi on July 27, 2025
# Script to restore the ETL application with HTTPS-only access

echo "Restoring ETL application with HTTPS-only access..."

# Navigate to the project directory
cd /home/rishi/Documents/pykaftestapp

# Pull the latest changes from the repository
git pull origin master

# Start all services with HTTPS-only access
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to start
sleep 10

# Run the verification script to confirm everything is working
./verify-https.sh

echo "ETL application restored successfully. Access the application at https://localhost/"
