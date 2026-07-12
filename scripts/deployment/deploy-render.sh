#!/usr/bin/env bash
set -euo pipefail
: "${RENDER_DEPLOY_HOOK_URL:?Set RENDER_DEPLOY_HOOK_URL}"
curl -fsS -X POST "$RENDER_DEPLOY_HOOK_URL"
HEALTH_URL="${RENDER_HEALTH_URL:-https://duobackend.onrender.com/health/}"
bash "$(dirname "$0")/../../.github/scripts/verify-deployment.sh" "$HEALTH_URL"
