#!/usr/bin/env bash
set -euo pipefail

URL="${1:-}"
MAX_ATTEMPTS="${2:-12}"
SLEEP_SECONDS="${3:-10}"

if [[ -z "$URL" ]]; then
  echo "Usage: verify-deployment.sh <health-url> [max_attempts] [sleep_seconds]"
  exit 1
fi

echo "Verifying deployment at ${URL}"

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  if response=$(curl -fsS "$URL" 2>/dev/null); then
    echo "Health check passed on attempt ${attempt}: ${response}"
    exit 0
  fi
  echo "Attempt ${attempt}/${MAX_ATTEMPTS} failed — retrying in ${SLEEP_SECONDS}s..."
  sleep "$SLEEP_SECONDS"
done

echo "Deployment verification failed after ${MAX_ATTEMPTS} attempts."
exit 1
