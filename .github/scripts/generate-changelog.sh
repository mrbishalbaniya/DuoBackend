#!/usr/bin/env bash
# Generate changelog from conventional commits since the last tag.
set -euo pipefail

OUTPUT="${1:-CHANGELOG.md}"
LAST_TAG="${2:-}"

if [[ -z "$LAST_TAG" ]]; then
  LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
fi

{
  echo "# Changelog"
  echo ""
  echo "Generated: $(date -u +"%Y-%m-%d %H:%M UTC")"
  echo ""
  if [[ -n "$LAST_TAG" ]]; then
    echo "## Changes since ${LAST_TAG}"
    git log "${LAST_TAG}..HEAD" --pretty=format:"- %s (%h)" --no-merges
  else
    echo "## Recent changes"
    git log -n 50 --pretty=format:"- %s (%h)" --no-merges
  fi
  echo ""
} > "$OUTPUT"

echo "Wrote ${OUTPUT}"
