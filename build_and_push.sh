#!/bin/bash

# Load registry configuration if available
if [ -f "registry.env" ]; then
    source registry.env
    echo "📋 Loaded registry configuration from registry.env"
elif [ -f "registry.env.local" ]; then
    source registry.env.local
    echo "📋 Loaded registry configuration from registry.env.local"
fi

# Version management
VERSION_FILE="version.txt"
DEFAULT_VERSION="1.0.0"

# Function to get current version
get_version() {
    if [ -f "$VERSION_FILE" ]; then
        cat "$VERSION_FILE"
    else
        echo "$DEFAULT_VERSION"
    fi
}

# Function to increment version
increment_version() {
    local version=$1
    local type=${2:-patch}  # patch, minor, major
    
    IFS='.' read -r major minor patch <<< "$version"
    
    case $type in
        "major")
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        "minor")
            minor=$((minor + 1))
            patch=0
            ;;
        "patch"|*)
            patch=$((patch + 1))
            ;;
    esac
    
    echo "$major.$minor.$patch"
}

# Function to save version
save_version() {
    echo "$1" > "$VERSION_FILE"
}

# Get current version
CURRENT_VERSION=$(get_version)

# Configuration for Remote Database Build
# Docker Hub username - set via environment variable or override
REGISTRY="${DOCKER_REGISTRY:-your-dockerhub-username}"
# Use version from version.txt unless IMAGE_VERSION is explicitly set
VERSION="${IMAGE_VERSION:-$(get_version)}"
LOCAL_VERSION="latest"

# Alternative configurations (uncomment as needed)
# REGISTRY="your-registry.com"  # For private registry
# REGISTRY="localhost:5000"     # For local registry

# Validate registry configuration
if [ "$REGISTRY" = "your-dockerhub-username" ]; then
    echo "⚠️  Warning: Please set DOCKER_REGISTRY environment variable"
    echo "   Method 1: export DOCKER_REGISTRY=your-dockerhub-username"
    echo "   Method 2: Edit registry.env file"
    echo "   Method 3: DOCKER_REGISTRY=your-username ./build_and_push.sh"
    echo ""
fi

echo "🚀 Building Docker Images for Remote Database Configuration"
echo "=========================================================="
echo "Registry: $REGISTRY"
echo "Current Version: $CURRENT_VERSION"
echo "Building Version: $VERSION"
echo "Local Version: $LOCAL_VERSION"
echo ""

# Function to show version options
show_version_options() {
    echo "📋 Version Management Options:"
    echo "1. Use current version ($CURRENT_VERSION)"
    echo "2. Increment patch version (${CURRENT_VERSION} → $(increment_version $CURRENT_VERSION patch))"
    echo "3. Increment minor version (${CURRENT_VERSION} → $(increment_version $CURRENT_VERSION minor))"
    echo "4. Increment major version (${CURRENT_VERSION} → $(increment_version $CURRENT_VERSION major))"
    echo "5. Specify custom version"
    echo ""
}

# Function to build and tag images with comprehensive tagging
build_and_tag() {
    local service=$1
    echo "📦 Building $service service..."
    
    # Build with local tag first
    docker build -t etl-$service:$LOCAL_VERSION ./$service
    
    # Tag for registry with version
    docker tag etl-$service:$LOCAL_VERSION $REGISTRY/etl-$service:$VERSION
    docker tag etl-$service:$LOCAL_VERSION $REGISTRY/etl-$service:latest
    
    # Additional semantic versioning tags
    IFS='.' read -r major minor patch <<< "$VERSION"
    docker tag etl-$service:$LOCAL_VERSION $REGISTRY/etl-$service:$major
    docker tag etl-$service:$LOCAL_VERSION $REGISTRY/etl-$service:$major.$minor
    
    echo "✅ Built and tagged $service service with:"
    echo "   - $REGISTRY/etl-$service:$VERSION"
    echo "   - $REGISTRY/etl-$service:latest"
    echo "   - $REGISTRY/etl-$service:$major"
    echo "   - $REGISTRY/etl-$service:$major.$minor"
}

# Handle command line arguments for version management
if [ "$1" = "version" ]; then
    show_version_options
    exit 0
elif [ "$1" = "patch" ]; then
    NEW_VERSION=$(increment_version $CURRENT_VERSION patch)
    save_version $NEW_VERSION
    VERSION=$NEW_VERSION
    echo "🔄 Version incremented to: $NEW_VERSION"
elif [ "$1" = "minor" ]; then
    NEW_VERSION=$(increment_version $CURRENT_VERSION minor)
    save_version $NEW_VERSION
    VERSION=$NEW_VERSION
    echo "🔄 Version incremented to: $NEW_VERSION"
elif [ "$1" = "major" ]; then
    NEW_VERSION=$(increment_version $CURRENT_VERSION major)
    save_version $NEW_VERSION
    VERSION=$NEW_VERSION
    echo "🔄 Version incremented to: $NEW_VERSION"
elif [ "$1" = "set" ] && [ -n "$2" ]; then
    save_version $2
    VERSION=$2
    echo "🔄 Version set to: $2"
fi

# Build all services locally first
echo "🔨 Building all services locally..."
build_and_tag "extract"
build_and_tag "transform" 
build_and_tag "load"

echo ""
echo "📋 Available Images:"
docker images | grep -E "(etl-|$REGISTRY)"

echo ""
echo "🎯 Usage Options:"
echo "Version Management:"
echo "  $0 version           # Show version options"
echo "  $0 patch             # Increment patch version (1.0.0 → 1.0.1)"
echo "  $0 minor             # Increment minor version (1.0.0 → 1.1.0)"
echo "  $0 major             # Increment major version (1.0.0 → 2.0.0)"
echo "  $0 set X.Y.Z         # Set custom version"
echo ""
echo "Registry Operations:"
echo "  $0 push              # Push all images to registry"
echo "  $0 push patch        # Increment patch version and push"
echo "  $0 push minor        # Increment minor version and push"
echo "  $0 push major        # Increment major version and push"
echo ""
echo "Current Version: $VERSION"
echo "Next patch: $(increment_version $VERSION patch)"
echo "Next minor: $(increment_version $VERSION minor)"
echo "Next major: $(increment_version $VERSION major)"

# Function to push images to registry with comprehensive tagging
push_images() {
    echo "🚀 Pushing images to Docker Hub..."
    echo "Registry: $REGISTRY"
    echo "Version: $VERSION"
    
    # Validate registry name
    if [ "$REGISTRY" = "your-dockerhub-username" ]; then
        echo "❌ Please set your Docker Hub username first:"
        echo "   export DOCKER_REGISTRY=your-dockerhub-username"
        echo "   Or run: DOCKER_REGISTRY=your-username ./build_and_push.sh push"
        exit 1
    fi
    
    # Check if logged in to Docker Hub
    if ! docker info 2>/dev/null | grep -q "Username:"; then
        echo "❌ Not logged in to Docker Hub."
        echo "Please run: docker login"
        echo ""
        echo "💡 For automated CI/CD, consider using:"
        echo "   - Docker Hub access tokens"
        echo "   - GitHub Secrets for CI/CD"
        exit 1
    fi
    
    # Parse version components for semantic versioning
    IFS='.' read -r major minor patch <<< "$VERSION"
    
    # Push all service images with comprehensive tagging
    for service in extract transform load; do
        echo "📤 Pushing $service service..."
        
        # Push specific version
        docker push $REGISTRY/etl-$service:$VERSION
        
        # Push latest
        docker push $REGISTRY/etl-$service:latest
        
        # Push major version tag
        docker push $REGISTRY/etl-$service:$major
        
        # Push major.minor version tag
        docker push $REGISTRY/etl-$service:$major.$minor
        
        echo "✅ Pushed $service service with tags:"
        echo "   - $REGISTRY/etl-$service:$VERSION"
        echo "   - $REGISTRY/etl-$service:latest"
        echo "   - $REGISTRY/etl-$service:$major"
        echo "   - $REGISTRY/etl-$service:$major.$minor"
        echo ""
    done
    
    echo "✅ All images pushed successfully!"
    echo ""
    echo "📋 Pushed Images Summary:"
    echo "  Version: $VERSION"
    echo "  Services: extract, transform, load"
    echo "  Tags per service: $VERSION, latest, $major, $major.$minor"
}

# Handle command line arguments
case "$1" in
    "version")
        show_version_options
        exit 0
        ;;
    "patch")
        NEW_VERSION=$(increment_version $CURRENT_VERSION patch)
        save_version $NEW_VERSION
        VERSION=$NEW_VERSION
        echo "🔄 Version incremented to: $NEW_VERSION"
        ;;
    "minor")
        NEW_VERSION=$(increment_version $CURRENT_VERSION minor)
        save_version $NEW_VERSION
        VERSION=$NEW_VERSION
        echo "🔄 Version incremented to: $NEW_VERSION"
        ;;
    "major")
        NEW_VERSION=$(increment_version $CURRENT_VERSION major)
        save_version $NEW_VERSION
        VERSION=$NEW_VERSION
        echo "🔄 Version incremented to: $NEW_VERSION"
        ;;
    "set")
        if [ -n "$2" ]; then
            save_version $2
            VERSION=$2
            echo "🔄 Version set to: $2"
        else
            echo "❌ Please specify a version: $0 set X.Y.Z"
            exit 1
        fi
        ;;
    "push")
        # Handle push with version increment
        if [ -n "$2" ]; then
            case "$2" in
                "patch"|"minor"|"major")
                    NEW_VERSION=$(increment_version $CURRENT_VERSION $2)
                    save_version $NEW_VERSION
                    VERSION=$NEW_VERSION
                    echo "🔄 Version incremented to: $NEW_VERSION"
                    echo "🔨 Building with new version..."
                    ;;
                *)
                    echo "❌ Invalid version type: $2"
                    echo "Valid options: patch, minor, major"
                    exit 1
                    ;;
            esac
        fi
        
        # Build images if push with version increment
        if [ -n "$2" ]; then
            echo "🔨 Building services with new version..."
            build_and_tag "extract"
            build_and_tag "transform"
            build_and_tag "load"
        fi
        
        # Push images
        push_images
        exit 0
        ;;
esac
        echo "   - Environment variables for credentials"
        exit 1
    fi
    
    # Get current logged in user
    CURRENT_USER=$(docker info 2>/dev/null | grep "Username:" | awk '{print $2}')
    echo "📋 Logged in as: $CURRENT_USER"
    
    # Warning if registry doesn't match logged in user
    if [ "$REGISTRY" != "$CURRENT_USER" ]; then
        echo "⚠️  Warning: Registry ($REGISTRY) doesn't match logged in user ($CURRENT_USER)"
        echo "   This may cause push failures. Continue? (y/N)"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            echo "❌ Cancelled by user"
            exit 1
        fi
    fi
    
    # Push versioned images
    echo "📤 Pushing versioned images..."
    docker push $REGISTRY/etl-extract:$VERSION
    docker push $REGISTRY/etl-transform:$VERSION
    docker push $REGISTRY/etl-load:$VERSION
    
    # Push latest tags
    echo "📤 Pushing latest tags..."
    docker push $REGISTRY/etl-extract:latest
    docker push $REGISTRY/etl-transform:latest
    docker push $REGISTRY/etl-load:latest
    
    echo "✅ All images pushed successfully!"
    echo ""
    echo "📋 Pushed Images:"
    echo "  - $REGISTRY/etl-extract:$VERSION"
    echo "  - $REGISTRY/etl-extract:latest"
    echo "  - $REGISTRY/etl-transform:$VERSION"
    echo "  - $REGISTRY/etl-transform:latest"
    echo "  - $REGISTRY/etl-load:$VERSION"
    echo "  - $REGISTRY/etl-load:latest"
}

# Handle command line arguments
if [ "$1" = "push" ]; then
    push_images
fi