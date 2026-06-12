#!/usr/bin/env bash
# Deploy kotoba to Kubernetes.
#
# Usage:
#   ./scripts/deploy.sh [tag]          # deploy (default tag: latest)
#   ./scripts/deploy.sh --build [tag]  # build+push then deploy
#   ./scripts/deploy.sh --delete       # teardown (keeps PVC)
#
# Prerequisites:
#   - kubectl configured for the target cluster
#   - ghcr-creds in kotoba namespace, or GHCR_TOKEN/GHCR_USER available
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../deploy" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="${KOTOBA_NAMESPACE:-kotoba}"
IMAGE_REPO="${KOTOBA_IMAGE_REPO:-ghcr.io/etzhayyim/kotoba}"
PULL_SECRET="${KOTOBA_IMAGE_PULL_SECRET:-ghcr-creds}"
STORAGE_CLASS="${KOTOBA_STORAGE_CLASS:-}"

TAG="latest"
BUILD=false
DELETE=false

render_with_image() {
  sed -E \
    -e "s#image: ghcr.io/(etzhayyim|gftdcojp)/kotoba:[^[:space:]]+#image: ${IMAGE_REPO}:${TAG}#g" \
    -e "s|name: ghcr-creds|name: ${PULL_SECRET}|g" \
    -e "s|namespace: kotoba|namespace: ${NAMESPACE}|g" \
    "${DEPLOY_DIR}/deployment.yaml"
}

render_pvc() {
  if [[ -n "${STORAGE_CLASS}" ]]; then
    sed -E \
      -e "s|storageClassName: [^[:space:]]+|storageClassName: ${STORAGE_CLASS}|g" \
      -e "s|namespace: kotoba|namespace: ${NAMESPACE}|g" \
      "${DEPLOY_DIR}/pvc.yaml"
  else
    sed -E "s|namespace: kotoba|namespace: ${NAMESPACE}|g" "${DEPLOY_DIR}/pvc.yaml"
  fi
}

render_namespace() {
  sed -E "s|name: kotoba|name: ${NAMESPACE}|g" "${DEPLOY_DIR}/namespace.yaml"
}

render_manifest() {
  sed -E "s|namespace: kotoba|namespace: ${NAMESPACE}|g" "$1"
}

for arg in "$@"; do
  case "$arg" in
    --build)  BUILD=true ;;
    --delete) DELETE=true ;;
    *)        TAG="$arg" ;;
  esac
done

# ── teardown ──────────────────────────────────────────────────────────────────
if $DELETE; then
  echo "Deleting kotoba deployment in namespace ${NAMESPACE} (PVC preserved)..."
  render_manifest "${DEPLOY_DIR}/service.yaml" | kubectl delete -f - --ignore-not-found
  render_with_image | kubectl delete -f - --ignore-not-found
  render_manifest "${DEPLOY_DIR}/configmap.yaml" | kubectl delete -f - --ignore-not-found
  echo "Done. PVC kotoba-sled preserved. To also delete PVC:"
  echo "  kubectl delete pvc kotoba-sled -n ${NAMESPACE}"
  exit 0
fi

# ── build & push (optional) ───────────────────────────────────────────────────
if $BUILD; then
  echo "Building & pushing ${IMAGE_REPO}:${TAG}..."
  "${SCRIPT_DIR}/build-push.sh" "${TAG}"
fi

# ── 0. Pull secret (idempotent — skip if exists) ──────────────────────────────
# Creates ghcr-creds from token env, or from local docker credentials.
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
if ! kubectl get secret "${PULL_SECRET}" -n "${NAMESPACE}" &>/dev/null; then
  echo "Creating ${PULL_SECRET}..."
  if [[ -n "${GHCR_TOKEN:-}" ]]; then
    kubectl create secret docker-registry "${PULL_SECRET}" \
      --docker-server=ghcr.io \
      --docker-username="${GHCR_USER:-etzhayyim}" \
      --docker-password="${GHCR_TOKEN}" \
      --namespace="${NAMESPACE}"
  elif [[ -f "${HOME}/.docker/config.json" ]]; then
    kubectl create secret generic "${PULL_SECRET}" \
      --from-file=.dockerconfigjson="${HOME}/.docker/config.json" \
      --type=kubernetes.io/dockerconfigjson \
      --namespace="${NAMESPACE}"
  else
    echo "Set GHCR_TOKEN/GHCR_USER or run docker login ghcr.io before deploying." >&2
    exit 1
  fi
fi

# ── 1. Namespace + PVC ────────────────────────────────────────────────────────
render_namespace | kubectl apply -f -
render_pvc | kubectl apply -f -

# ── 2. ConfigMap ──────────────────────────────────────────────────────────────
render_manifest "${DEPLOY_DIR}/configmap.yaml" | kubectl apply -f -

# ── 3. Deployment (pin image repo/tag and pull secret) ────────────────────────
render_with_image | kubectl apply -f -

# ── 4. Service ────────────────────────────────────────────────────────────────
render_manifest "${DEPLOY_DIR}/service.yaml" | kubectl apply -f -

# ── 5. Wait for rollout ───────────────────────────────────────────────────────
echo "Waiting for rollout..."
kubectl rollout status deployment/kotoba -n "${NAMESPACE}" --timeout=120s

# ── 6. Health check ───────────────────────────────────────────────────────────
POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=kotoba -o jsonpath='{.items[0].metadata.name}')
echo ""
echo "Pod: ${POD}"
echo "Logs (last 20 lines):"
kubectl logs -n "${NAMESPACE}" "${POD}" --tail=20

echo ""
echo "Port-forward to verify locally:"
echo "  kubectl port-forward -n ${NAMESPACE} svc/kotoba 8080:8080 &"
echo "  curl http://localhost:8080/health"
