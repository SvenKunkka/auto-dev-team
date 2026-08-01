#!/bin/zsh
set -euo pipefail

DOMAIN="gui/$(id -u)"
FRONTEND_LABEL="com.autodevplatform.frontend"
BACKEND_LABEL="com.autodevplatform.backend-worker"

launchctl bootout \
  "$DOMAIN/$FRONTEND_LABEL" >/dev/null 2>&1 || true
launchctl bootout \
  "$DOMAIN/$BACKEND_LABEL" >/dev/null 2>&1 || true

wait_for_unload() {
  local label="$1"
  local attempt

  for attempt in {1..30}; do
    if ! launchctl print "$DOMAIN/$label" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "Failed to stop $label within 30 seconds." >&2
  return 1
}

wait_for_unload "$FRONTEND_LABEL"
wait_for_unload "$BACKEND_LABEL"

echo "Auto Dev Platform production services stopped."
