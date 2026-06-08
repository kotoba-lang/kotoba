#!/usr/bin/env bash
# Build kotoba image and push to GHCR.
# Usage: ./scripts/build-push.sh [tag]
set -euo pipefail

TAG="${1:-latest}"
IMAGE="ghcr.io/etzhayyim/kotoba:${TAG}"
PLATFORMS="${KOTOBA_IMAGE_PLATFORMS:-linux/amd64,linux/arm64}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
KOTOBA_DIR="${REPO_ROOT}/40-engine/kotoba"

GIT_SHA="$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "Building ${IMAGE} (sha=${GIT_SHA}, platforms=${PLATFORMS})"
echo "Context: ${KOTOBA_DIR}"

docker buildx build \
    --platform "${PLATFORMS}" \
    --cache-from type=registry,ref=ghcr.io/etzhayyim/build-cache:kotoba \
    --cache-to   type=registry,ref=ghcr.io/etzhayyim/build-cache:kotoba,mode=max \
    --build-arg GIT_SHA="${GIT_SHA}" \
    --build-arg BUILD_DATE="${BUILD_DATE}" \
    --tag "${IMAGE}" \
    --push \
    "${KOTOBA_DIR}"

echo "Pushed ${IMAGE}"
