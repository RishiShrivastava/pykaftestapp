#!/bin/bash

# Registry Setup Script
# This script helps configure Docker registry settings securely

echo "🐳 Docker Registry Setup"
echo "========================"
echo ""

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running. Please start Docker."
    exit 1
fi

# Get current Docker login status
if docker info 2>/dev/null | grep -q "Username:"; then
    CURRENT_USER=$(docker info 2>/dev/null | grep "Username:" | awk '{print $2}')
    echo "✅ Already logged in to Docker Hub as: $CURRENT_USER"
else
    echo "📋 Not currently logged in to Docker Hub"
fi

echo ""
echo "Registry Configuration Options:"
echo "1. Docker Hub (hub.docker.com)"
echo "2. Private Registry"
echo "3. Local Registry"
echo "4. Show current configuration"
echo ""

read -p "Choose an option (1-4): " choice

case $choice in
    1)
        echo ""
        echo "🐳 Docker Hub Configuration"
        echo "============================"
        
        if [ -z "$CURRENT_USER" ]; then
            echo "Please log in to Docker Hub first:"
            echo "  docker login"
            echo ""
            read -p "Enter your Docker Hub username: " username
            echo "export DOCKER_REGISTRY=$username" > registry.env.local
            echo "export IMAGE_VERSION=1.0.0" >> registry.env.local
            echo ""
            echo "✅ Configuration saved to registry.env.local"
            echo "💡 Run 'docker login' to authenticate"
            echo "💡 Current version: 1.0.0 (managed in version.txt)"
        else
            echo "export DOCKER_REGISTRY=$CURRENT_USER" > registry.env.local
            echo "export IMAGE_VERSION=1.0.0" >> registry.env.local
            echo ""
            echo "✅ Configuration saved to registry.env.local"
            echo "📋 Using logged in user: $CURRENT_USER"
            echo "💡 Current version: 1.0.0 (managed in version.txt)"
        fi
        ;;
    2)
        echo ""
        echo "🏢 Private Registry Configuration"
        echo "================================="
        read -p "Enter your private registry URL: " registry_url
        echo "export DOCKER_REGISTRY=$registry_url" > registry.env.local
        echo "export IMAGE_VERSION=remote-db-v1.0.0" >> registry.env.local
        echo ""
        echo "✅ Configuration saved to registry.env.local"
        echo "💡 Make sure to authenticate with your private registry"
        ;;
    3)
        echo ""
        echo "🏠 Local Registry Configuration"
        echo "==============================="
        echo "export DOCKER_REGISTRY=localhost:5000" > registry.env.local
        echo "export IMAGE_VERSION=remote-db-v1.0.0" >> registry.env.local
        echo ""
        echo "✅ Configuration saved to registry.env.local"
        echo "💡 Make sure your local registry is running on port 5000"
        ;;
    4)
        echo ""
        echo "📋 Current Configuration"
        echo "======================="
        if [ -f "registry.env.local" ]; then
            echo "From registry.env.local:"
            cat registry.env.local
        elif [ -f "registry.env" ]; then
            echo "From registry.env:"
            cat registry.env
        else
            echo "No configuration files found"
        fi
        
        if [ -n "$DOCKER_REGISTRY" ]; then
            echo ""
            echo "From environment: DOCKER_REGISTRY=$DOCKER_REGISTRY"
        fi
        ;;
    *)
        echo "❌ Invalid option"
        exit 1
        ;;
esac

echo ""
echo "🚀 Next Steps:"
echo "Version Management:"
echo "  ./build_and_push.sh version    # Show version options"
echo "  ./build_and_push.sh patch      # Increment patch (1.0.0 → 1.0.1)"
echo "  ./build_and_push.sh minor      # Increment minor (1.0.0 → 1.1.0)"
echo "  ./build_and_push.sh major      # Increment major (1.0.0 → 2.0.0)"
echo ""
echo "Build and Deploy:"
echo "  ./build_and_push.sh            # Build with current version"
echo "  ./build_and_push.sh push       # Build and push to registry"
echo "  ./build_and_push.sh push patch # Increment patch, build, and push"
echo ""
echo "Kubernetes Deployment:"
echo "  kubectl apply -f k8s/deployment.yaml"
echo ""
echo "💡 Security Tips:"
echo "- Never commit passwords to version control"
echo "- Use access tokens instead of passwords for CI/CD"
echo "- Keep registry.env.local file secure (it's in .gitignore)"
echo "- Version numbers are automatically managed in version.txt"
