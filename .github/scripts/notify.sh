#!/usr/bin/env bash
# Post CI/CD notifications to Discord and/or Slack webhooks.
# Set DISCORD_WEBHOOK_URL and/or SLACK_WEBHOOK_URL as GitHub secrets.
set -euo pipefail

STATUS="${1:-unknown}"
TITLE="${2:-Duo CI/CD}"
MESSAGE="${3:-No message}"
REPO="${GITHUB_REPOSITORY:-local/repo}"
BRANCH="${GITHUB_REF_NAME:-local}"
SHA="${GITHUB_SHA:-local}"
ACTOR="${GITHUB_ACTOR:-ci}"
RUN_URL="${GITHUB_SERVER_URL:-https://github.com}/${REPO}/actions/runs/${GITHUB_RUN_ID:-0}"

color="3447003"
case "$STATUS" in
  success) color="3066993" ;;
  failure) color="15158332" ;;
  warning) color="16776960" ;;
esac

payload_discord=$(cat <<EOF
{
  "embeds": [{
    "title": "${TITLE}",
    "description": "${MESSAGE}",
    "color": ${color},
    "fields": [
      {"name": "Repository", "value": "${REPO}", "inline": true},
      {"name": "Branch", "value": "${BRANCH}", "inline": true},
      {"name": "Commit", "value": "${SHA:0:7}", "inline": true},
      {"name": "Actor", "value": "${ACTOR}", "inline": true},
      {"name": "Status", "value": "${STATUS}", "inline": true},
      {"name": "Run", "value": "[View workflow](${RUN_URL})", "inline": false}
    ]
  }]
}
EOF
)

payload_slack=$(cat <<EOF
{
  "text": "*${TITLE}* — ${STATUS}\n${MESSAGE}\nRepo: ${REPO} | Branch: ${BRANCH} | Commit: ${SHA:0:7}\n<${RUN_URL}|View run>"
}
EOF
)

if [[ -n "${DISCORD_WEBHOOK_URL:-}" ]]; then
  curl -fsS -H "Content-Type: application/json" -d "$payload_discord" "$DISCORD_WEBHOOK_URL" || true
fi

if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
  curl -fsS -H "Content-Type: application/json" -d "$payload_slack" "$SLACK_WEBHOOK_URL" || true
fi

echo "Notification dispatched (status=${STATUS})."
