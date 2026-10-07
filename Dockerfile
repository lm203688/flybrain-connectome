# syntax=docker/dockerfile:1.6
#
# flybrain-connectome — container image.
#
# Two flavors baked into one image:
#   * MCP stdio server (`docker run --rm flybrain-connectome serve-mcp`)
#   * HTTP API on :8799 (`docker run --rm -p 8799:8799 flybrain-connectome serve-http`)
#
# The image ships the toolkit only. The 5.63 GB MaleCNS dataset is NOT baked
# in — mount it at /data/male_cns and set FLYBRAIN_DATA_DIR=/data/male_cns:
#
#   docker run --rm \
#     -v "$(pwd)/male_cns:/data/male_cns:ro" \
#     -e FLYBRAIN_DATA_DIR=/data/male_cns \
#     -p 8799:8799 \
#     flybrain-connectome serve-http
#
# Build:
#   docker build -t flybrain-connectome:latest .
#   docker build -t flybrain-connectome:2.43.0 --build-arg VERSION=2.43.0 .

FROM python:3.12-slim AS base

# Non-root user is a real production concern; run as `flybrain` (uid 10001).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FLYBRAIN_DATA_DIR=/data/male_cns \
    FLYBRAIN_HOME=/opt/flybrain \
    FLYBRAIN_API_PORT=8799

RUN useradd --uid 10001 --create-home --shell /bin/bash flybrain \
    && mkdir -p /opt/flybrain /data \
    && chown -R flybrain:flybrain /opt/flybrain /data

WORKDIR /opt/flybrain

# --- Layer 1: install Python deps first so code churn doesn't invalidate ---
COPY pyproject.toml README.md CHANGELOG.md LICENSE CITATION.cff ./
COPY flybrain_cli.py ./
COPY flybrain-connectome-mcp/ flybrain-connectome-mcp/
COPY scripts/ scripts/

RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir ".[prov]"

# Baked-in runtime smoke test so the image cannot ship broken.
RUN flybrain --help >/dev/null \
    && flybrain generate --motif-source local --modules 2 \
        --agents-per-module 3 --name docker_smoke --out /tmp/docker_smoke --no-html \
    && rm -rf /tmp/docker_smoke

USER flybrain

# Default entry point: MCP stdio server. Override the CMD to run the HTTP API.
ENTRYPOINT ["flybrain"]
CMD ["--help"]

# Convenience: expose the HTTP API port.
EXPOSE 8799

LABEL org.opencontainers.image.title="flybrain-connectome" \
      org.opencontainers.image.description="Traceable synthetic bio-topology generator (MaleCNS v1.0)" \
      org.opencontainers.image.repository="https://github.com/lm203688/flybrain-connectome" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/lm203688/flybrain-connectome"
