#!/bin/zsh
set -euo pipefail

RUNTIME_ROOT="$(cd "$(dirname "$0")" && pwd)"
DOMAIN="gui/$(id -u)"
AGENT_DIR="$HOME/Library/LaunchAgents"
BACKEND_LABEL="com.autodevplatform.backend-worker"
FRONTEND_LABEL="com.autodevplatform.frontend"

mkdir -p "$AGENT_DIR" "$RUNTIME_ROOT/logs"
install -m 644 \
  "$RUNTIME_ROOT/config/launchd/$BACKEND_LABEL.plist" \
  "$AGENT_DIR/$BACKEND_LABEL.plist"
install -m 644 \
  "$RUNTIME_ROOT/config/launchd/$FRONTEND_LABEL.plist" \
  "$AGENT_DIR/$FRONTEND_LABEL.plist"

bootstrap_agent() {
  local label="$1"
  local plist="$2"
  local attempt

  if launchctl print "$DOMAIN/$label" >/dev/null 2>&1; then
    return 0
  fi

  for attempt in 1 2 3 4 5; do
    if launchctl bootstrap "$DOMAIN" "$plist" >/dev/null 2>&1; then
      return 0
    fi

    # Some macOS versions report EIO even though the new job was loaded.
    if launchctl print "$DOMAIN/$label" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "Failed to bootstrap $label after 5 attempts." >&2
  return 1
}

bootstrap_agent "$BACKEND_LABEL" "$AGENT_DIR/$BACKEND_LABEL.plist"
bootstrap_agent "$FRONTEND_LABEL" "$AGENT_DIR/$FRONTEND_LABEL.plist"
launchctl enable "$DOMAIN/$BACKEND_LABEL"
launchctl enable "$DOMAIN/$FRONTEND_LABEL"

wait_for_http() {
  local name="$1"
  local url="$2"
  local attempt

  for attempt in {1..30}; do
    if /usr/bin/curl --fail --silent --show-error \
      --connect-timeout 1 --max-time 2 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "$name did not become ready within 30 seconds: $url" >&2
  return 1
}

wait_for_http "Backend" "http://127.0.0.1:8000/health"
wait_for_http "Frontend" "http://127.0.0.1:3000/"

echo "Auto Dev Platform production services started."
echo "Backend: http://127.0.0.1:8000"
echo "Frontend: http://127.0.0.1:3000"
