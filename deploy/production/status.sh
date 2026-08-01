#!/bin/zsh
set -u

DOMAIN="gui/$(id -u)"
FAILED=0

if launchctl print \
  "$DOMAIN/com.autodevplatform.backend-worker" >/dev/null 2>&1; then
  echo "backend-worker: loaded"
else
  echo "backend-worker: stopped"
  FAILED=1
fi

if launchctl print \
  "$DOMAIN/com.autodevplatform.frontend" >/dev/null 2>&1; then
  echo "frontend: loaded"
else
  echo "frontend: stopped"
  FAILED=1
fi

if HEALTH="$(curl --fail --silent --show-error \
  http://127.0.0.1:8000/health 2>/dev/null)"; then
  echo "health: $HEALTH"
else
  echo "health: unavailable"
  FAILED=1
fi

if FRONTEND_STATUS="$(curl --silent --output /dev/null \
  --write-out '%{http_code}' http://127.0.0.1:3000/)"; then
  if [[ "$FRONTEND_STATUS" == "200" ]]; then
    echo "frontend-http: 200"
  else
    echo "frontend-http: $FRONTEND_STATUS"
    FAILED=1
  fi
else
  echo "frontend-http: unavailable"
  FAILED=1
fi

exit "$FAILED"
