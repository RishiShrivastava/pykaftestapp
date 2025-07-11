#!/bin/bash

REGISTRY="rishi354"
VERSION="1.1.0"
SERVICES=("extract" "transform" "load")

for service in "${SERVICES[@]}"; do
    echo "Tagging and pushing etl-$service..."
    docker tag "etl-$service:latest" "$REGISTRY/etl-$service:$VERSION"
    docker push "$REGISTRY/etl-$service:$VERSION"
    docker tag "etl-$service:latest" "$REGISTRY/etl-$service:latest"
    docker push "$REGISTRY/etl-$service:latest"
done
