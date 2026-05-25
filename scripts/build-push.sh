#!/usr/bin/env bash
# Build kotoba image and push to GHCR.
# Usage: ./scripts/build-push.sh [tag]
set -euo pipefail

TAG="${1:-latest}"
IMAGE="ghcr.io/etzhayyim/kotoba:${TAG}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GIT_SHA="$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "Building ${IMAGE} (sha=${GIT_SHA})"
echo "Context: ${REPO_ROOT}"

docker buildx build \
    --platform linux/amd64 \
    --build-arg GIT_SHA="${GIT_SHA}" \
    --build-arg BUILD_DATE="${BUILD_DATE}" \
    --tag "${IMAGE}" \
    --push \
    "${REPO_ROOT}"

echo "Pushed ${IMAGE}"
