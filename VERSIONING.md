# Docker Image Versioning Guide

## Overview
This project uses semantic versioning (SemVer) for Docker images with automatic version management.

## Version Format
- **Format**: `MAJOR.MINOR.PATCH` (e.g., `1.0.0`, `1.2.3`, `2.0.0`)
- **Current Version**: Stored in `version.txt`
- **Auto-increment**: Available for patch, minor, and major releases

## Version Management Commands

### View Current Version
```bash
./build_and_push.sh version
```

### Increment Version
```bash
# Increment patch version (1.0.0 → 1.0.1)
./build_and_push.sh patch

# Increment minor version (1.0.0 → 1.1.0)
./build_and_push.sh minor

# Increment major version (1.0.0 → 2.0.0)
./build_and_push.sh major
```

### Set Custom Version
```bash
./build_and_push.sh set 2.1.0
```

## Build and Push Commands

### Build Only
```bash
# Build with current version
./build_and_push.sh

# Build with incremented version
./build_and_push.sh patch  # Increments and builds
```

### Build and Push
```bash
# Push existing built images
./build_and_push.sh push

# Increment, build, and push in one command
./build_and_push.sh push patch  # Patch increment
./build_and_push.sh push minor  # Minor increment
./build_and_push.sh push major  # Major increment
```

## Image Tags Created

For each service (extract, transform, load), the following tags are created:

### Local Tags
- `etl-extract:latest`
- `etl-transform:latest`
- `etl-load:latest`

### Registry Tags (when DOCKER_REGISTRY=username)
- `username/etl-extract:1.0.0` (specific version)
- `username/etl-extract:latest` (latest version)
- `username/etl-extract:1` (major version)
- `username/etl-extract:1.0` (major.minor version)

## Version Semantics

### When to Increment
- **Patch (1.0.0 → 1.0.1)**: Bug fixes, small improvements
- **Minor (1.0.0 → 1.1.0)**: New features, backward-compatible changes
- **Major (1.0.0 → 2.0.0)**: Breaking changes, major refactoring

### Examples
```bash
# Bug fix release
./build_and_push.sh push patch

# New feature release
./build_and_push.sh push minor

# Breaking change release
./build_and_push.sh push major
```

## Registry Configuration

### Set Docker Hub Username
```bash
# Method 1: Environment variable
export DOCKER_REGISTRY=your-dockerhub-username
./build_and_push.sh

# Method 2: Registry configuration file
./setup_registry.sh

# Method 3: Direct command
DOCKER_REGISTRY=your-username ./build_and_push.sh push
```

## Kubernetes Deployment

Images are referenced in `k8s/deployment.yaml` with:
- `rishishrivastava/etl-extract:latest` (updates with each push)
- `rishishrivastava/etl-extract:1.0.0` (specific version)

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Build and Push
  env:
    DOCKER_REGISTRY: ${{ secrets.DOCKERHUB_USERNAME }}
  run: |
    echo "${{ secrets.DOCKERHUB_TOKEN }}" | docker login -u "${{ secrets.DOCKERHUB_USERNAME }}" --password-stdin
    ./build_and_push.sh push patch
```

### Manual Release Process
1. Make code changes
2. Test locally: `./build_and_push.sh`
3. Choose version increment: `./build_and_push.sh push [patch|minor|major]`
4. Deploy to Kubernetes: `kubectl apply -f k8s/deployment.yaml`

## Version History

Version history is maintained in `version.txt`:
- **1.0.0**: Initial release with remote database integration
- **1.0.1**: Bug fixes and improvements
- **1.1.0**: New features added
- **2.0.0**: Major refactoring or breaking changes

## Best Practices

1. **Always increment version** before releasing changes
2. **Use patch** for bug fixes and minor improvements
3. **Use minor** for new features that don't break existing functionality
4. **Use major** for breaking changes or significant architecture changes
5. **Tag specific versions** in production deployments
6. **Use latest tag** only for development/testing environments

## Troubleshooting

### Check Current Version
```bash
cat version.txt
```

### View All Available Tags
```bash
docker images | grep etl-
```

### Reset Version
```bash
echo "1.0.0" > version.txt
```

### Force Rebuild
```bash
docker system prune -f
./build_and_push.sh
```
