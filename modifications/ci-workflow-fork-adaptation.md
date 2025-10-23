# CI Workflow Fork Adaptation

## Overview

This modification introduces a custom GitHub Actions CI workflow specifically adapted for the Garden of Concepts fork of paperless-ngx. The workflow automates Docker image building and publishing to GitHub Container Registry (GHCR).

## Changes Summary

### New File Created
- `.github/workflows/ci_goc.yml` - Custom CI workflow for the fork

### Key Features

#### 1. **Automated Docker Image Building**
- Builds Docker images automatically on:
  - Push to branches (excluding translation branches)
  - Pull requests (excluding translation branches)
  - Semantic version tags (e.g., `v1.2.3`, `v1.2.3-beta.rc1`)

#### 2. **Multi-Platform Support**
- Builds for both `linux/amd64` and `linux/arm64` architectures
- Uses QEMU emulation for ARM64 builds
- Leverages Docker Buildx for efficient multi-platform builds

#### 3. **Image Publishing**
- Publishes images to GitHub Container Registry (ghcr.io)
- Automatic repository name conversion to lowercase
- Images tagged with:
  - Branch names for branch builds
  - Semantic versions for tagged releases (e.g., `1.2.3`, `1.2`)

#### 4. **Build Caching Strategy**
- Implements layer caching to speed up builds
- Cache hierarchy:
  1. Current branch cache (primary)
  2. `dev` branch cache (fallback)
  3. `dev-goc` branch cache (additional fallback)
- Sanitizes branch names (replaces `/` with `-`) for valid cache keys

#### 5. **Environment Configuration**
- Default UV version: `0.8.x`
- Default Python version: `3.11`
- Concurrency control to prevent duplicate builds

## Technical Implementation Details

### Branch Name Sanitization
The workflow handles branch names containing slashes by sanitizing them:
```bash
SANITIZED_BRANCH_NAME=${BRANCH_NAME//\//-}
```
This ensures cache references are valid Docker registry tags.

### Build Arguments
- `PNGX_TAG_VERSION`: Set to the Docker metadata version output

### Docker Metadata Action
Configured to:
- Tag images with branch names for branch events
- Apply semantic versioning patterns for tags
- Generate both full version tags (`x.y.z`) and minor version tags (`x.y`)

### Registry Authentication
- Uses GitHub Actor credentials
- Authenticates via `GITHUB_TOKEN` secret
- Automatic login to ghcr.io

### Image Inspection
After successful build and push, the workflow inspects and displays metadata for the built image.

## Iteration History

The workflow went through several refinements across 7 commits:

1. **Initial creation** - Base workflow structure
2. **Cache disabled** - Temporarily commented out caching
3. **Cache re-enabled** - Restored cache functionality with single source
4. **Multiple cache sources** - Added dev and dev-goc fallback caches
5. **Cache cleanup** - Removed unnecessary commented code
6. **Branch sanitization** - Added logic to handle branch names with slashes
7. **Fixed sanitization** - Corrected branch name sanitization logic

## Benefits

1. **Automation**: Eliminates manual Docker image building and publishing
2. **Consistency**: Ensures reproducible builds across environments
3. **Performance**: Layer caching significantly reduces build times
4. **Multi-arch Support**: Native support for both AMD64 and ARM64 platforms
5. **Fork Independence**: Custom workflow allows fork-specific configurations without conflicting with upstream

## Usage

### For Maintainers
- Push to any branch triggers an automatic build
- Images are automatically tagged and pushed to ghcr.io
- Creating version tags (e.g., `v1.2.3`) triggers versioned releases

### For Users
Pull images from:
```bash
docker pull ghcr.io/gardenofconcepts/paperless-ngx:<tag>
```

Where `<tag>` can be:
- A branch name (e.g., `dev-goc`, `feature-extended-custom-fields`)
- A version number (e.g., `1.2.3`, `1.2`)
