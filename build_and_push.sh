#!/bin/bash

# Configuration for Remote Database Build
REGISTRY="your-dockerhub-username"  # Replace with your Docker Hub username
VERSION="remote-db-v1.0.0"
LOCAL_VERSION="latest"

# Alternative configurations (uncomment as needed)
# REGISTRY="your-registry.com"  # For private registry
# REGISTRY="localhost:5000"     # For local registry

echo "🚀 Building Docker Images for Remote Database Configuration"
echo "=========================================================="
echo "Registry: $REGISTRY"
echo "Version: $VERSION"
echo "Local Version: $LOCAL_VERSION"
echo ""

# Function to build and tag images
build_and_tag() {
    local service=$1
    echo "📦 Building $service service..."
    
    # Build with local tag first
    docker build -t etl-$service:$LOCAL_VERSION ./$service
    
    # Tag for registry
    docker tag etl-$service:$LOCAL_VERSION $REGISTRY/etl-$service:$VERSION
    docker tag etl-$service:$LOCAL_VERSION $REGISTRY/etl-$service:latest
    
    echo "✅ Built and tagged $service service"
}

# Build all services locally first
echo "🔨 Building all services locally..."
build_and_tag "extract"
build_and_tag "transform" 
build_and_tag "load"

echo ""
echo "📋 Available Images:"
docker images | grep -E "(etl-|$REGISTRY)"

echo ""
echo "🎯 Next Steps:"
echo "1. To push to Docker Hub:"
echo "   docker login"
echo "   docker push $REGISTRY/etl-extract:$VERSION"
echo "   docker push $REGISTRY/etl-transform:$VERSION"
echo "   docker push $REGISTRY/etl-load:$VERSION"
echo ""
echo "2. To test locally with remote DB:"
echo "   docker compose up -d"
echo ""
echo "3. To update Kubernetes manifests:"
echo "   Update image paths in k8s/deployment.yaml"