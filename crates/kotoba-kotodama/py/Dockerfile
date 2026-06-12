FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/etzhayyim/root"
LABEL org.opencontainers.image.description="mitama reactive agent pool + religious-corp cell catalog (ADR-0049 + ADR-2605232100)"

# Build context: repo root. Bundles both the kotodama Python package
# and the religious-corp cell catalog + cells.toml registry so the
# k3s DaemonSet pods can resolve cells without a hostPath mount of the
# repo (per ADR-2605232100 Stage 2 — replaces the orbstack-only hostPath
# pattern).

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# Default repo root layout inside the image — cell_runner_main reads
# ETZ_REPO and resolves $ETZ_REPO/20-actors/kotoba-kotodama/cells/<name>/cell.py.
ENV ETZ_REPO=/repo
ARG WASMTIME_VERSION=44.0.0
ARG FOUNDRY_VERSION=1.5.0
ARG GH_VERSION=2.63.2
ARG TARGETARCH
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
 && apt-get install -y --no-install-recommends bash git postgresql-client ca-certificates poppler-utils tesseract-ocr tesseract-ocr-jpn \
 && rm -rf /var/lib/apt/lists/*

ARG CACHE_BUST=1
COPY 20-actors/kotoba-kotodama/py/pyproject.toml /app/
COPY 20-actors/kotoba-kotodama/py/src /app/src

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl xz-utils \
 && case "${TARGETARCH}" in \
      amd64) wasmtime_arch="x86_64-linux"; foundry_arch="amd64" ;; \
      arm64) wasmtime_arch="aarch64-linux"; foundry_arch="arm64" ;; \
      *) echo "unsupported TARGETARCH=${TARGETARCH}" >&2; exit 1 ;; \
    esac \
 && curl -fsSL "https://github.com/bytecodealliance/wasmtime/releases/download/v${WASMTIME_VERSION}/wasmtime-v${WASMTIME_VERSION}-${wasmtime_arch}.tar.xz" \
    | tar -xJ --strip-components=1 -C /usr/local/bin "wasmtime-v${WASMTIME_VERSION}-${wasmtime_arch}/wasmtime" \
 && curl -fsSL "https://github.com/foundry-rs/foundry/releases/download/v${FOUNDRY_VERSION}/foundry_v${FOUNDRY_VERSION}_linux_${foundry_arch}.tar.gz" \
    | tar -xz -C /usr/local/bin cast \
 && curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${foundry_arch}.tar.gz" \
    | tar -xz --strip-components=2 -C /usr/local/bin "gh_${GH_VERSION}_linux_${foundry_arch}/bin/gh" \
 && apt-get purge -y --auto-remove curl xz-utils \
 && rm -rf /var/lib/apt/lists/*

# Install PyTorch from the CPU-only wheel index so sentence-transformers
# (required by handlers/actor_embed.py per ADR-0092 L2) does not pull the
# ~2 GB CUDA build. Everything else stays on PyPI. Image layer ≈ 900 MB.
RUN pip install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      "torch>=2.2,<3" \
 && pip install --no-cache-dir .

# Religious-corp cell catalog + registry (ADR-2605232100 Stage 2).
# Placed under /repo/... so cell_runner_main resolves them against
# ETZ_REPO=/repo without needing hostPath mounts.
COPY 20-actors/kotoba-kotodama/cells /repo/20-actors/kotoba-kotodama/cells
COPY 50-infra/cluster/murakumo/cell-runner/cells.toml /repo/50-infra/cluster/murakumo/cell-runner/cells.toml

EXPOSE 8815 9090

CMD ["python", "-m", "kotodama.server"]
