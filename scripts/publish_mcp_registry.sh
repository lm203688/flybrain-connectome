#!/usr/bin/env bash
# ============================================================
# flybrain-connectome MCP Registry publisher
# 
# Usage:
#   bash scripts/publish_mcp_registry.sh              # Publish current server.json
#   bash scripts/publish_mcp_registry.sh --validate   # Validate only, no publish
#   bash scripts/publish_mcp_registry.sh --login      # Login only (first time)
#
# Prerequisites:
#   - GitHub PAT with repo scope (stored in ~/.workbuddy/secrets/github.json)
#   - Network access to registry.modelcontextprotocol.io
#   - Bash + curl + tar (standard on Windows Git Bash)
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MCP_DIR="$ROOT_DIR/mcp-registry"
PUBLISHER_BIN="$MCP_DIR/mcp-publisher.exe"
SERVER_JSON="$MCP_DIR/server.json"
SECRETS_FILE="$HOME/.workbuddy/secrets/github.json"

# --- Helpers ---
log() { echo "[$(date +%H:%M:%S)] $*"; }
error() { echo "[ERROR] $*" >&2; exit 1; }

# --- Load GitHub token ---
get_github_token() {
  if [ -f "$SECRETS_FILE" ]; then
    python -c "import json; print(json.load(open('$SECRETS_FILE'))['GITHUB_TOKEN'])" 2>/dev/null
  else
    error "No GitHub token found at $SECRETS_FILE"
  fi
}

# --- Download mcp-publisher if not present ---
download_publisher() {
  if [ -f "$PUBLISHER_BIN" ]; then
    log "mcp-publisher.exe already exists"
    return 0
  fi
  log "Downloading mcp-publisher..."
  mkdir -p "$MCP_DIR"
  local arch
  if [[ "$(uname -s)" == MINGW* ]] || [[ "$(uname -s)" == CYGWIN* ]]; then
    # Windows
    local os=windows
    if [ "$(uname -m)" = "aarch64" ]; then
      arch=arm64
    else
      arch=amd64
    fi
    local ext=.exe
  else
    # Unix
    local os=linux
    if [ "$(uname -m)" = "aarch64" ]; then
      arch=arm64
    else
      arch=amd64
    fi
    local ext=""
  fi
  
  local url="https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_${os}_${arch}.tar.gz"
  local tmp="$MCP_DIR/mcp-publisher.tar.gz"
  log "Fetching: $url"
  curl -sL --max-time 60 "$url" -o "$tmp"
  tar -xzf "$tmp" -C "$MCP_DIR" "mcp-publisher${ext}"
  rm -f "$tmp"
  chmod +x "$PUBLISHER_BIN" 2>/dev/null || true
  log "Downloaded mcp-publisher.exe ($(du -h "$PUBLISHER_BIN" | cut -f1))"
}

# --- Main ---
CMD="${1:---validate}"

case "$CMD" in
  --validate)
    download_publisher
    "$PUBLISHER_BIN" validate "$SERVER_JSON"
    ;;
  --login)
    download_publisher
    TOKEN=$(get_github_token)
    "$PUBLISHER_BIN" login github -token "$TOKEN"
    ;;
  --publish)
    download_publisher
    TOKEN=$(get_github_token)
    "$PUBLISHER_BIN" login github -token "$TOKEN"
    "$PUBLISHER_BIN" publish "$SERVER_JSON"
    ;;
  *)
    echo "Usage: $0 [--validate|--login|--publish]"
    exit 1
    ;;
esac
