#!/bin/zsh
set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_ROOT="${AUTO_DEV_RUNTIME_ROOT:-$HOME/AutoDevPlatform}"
BENCHMARK_ROOT="${AUTO_DEV_BENCHMARK_ROOT:-$HOME/AutoDevBenchmarks}"
UV_BIN="$(command -v uv)"
NPM_BIN="$(command -v npm)"
NODE_BIN="$(command -v node)"

escape_sed_replacement() {
  printf '%s' "$1" | /usr/bin/sed 's/[&\\]/\\&/g'
}

RUNTIME_ROOT_SED="$(escape_sed_replacement "$RUNTIME_ROOT")"
NODE_BIN_SED="$(escape_sed_replacement "$NODE_BIN")"
TOOL_PATH="$RUNTIME_ROOT/.venv/bin:$(dirname "$NODE_BIN"):$(dirname "$UV_BIN"):/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin"
TOOL_PATH_SED="$(escape_sed_replacement "$TOOL_PATH")"

mkdir -p \
  "$RUNTIME_ROOT/backend" \
  "$RUNTIME_ROOT/frontend" \
  "$RUNTIME_ROOT/src" \
  "$RUNTIME_ROOT/data" \
  "$RUNTIME_ROOT/logs" \
  "$RUNTIME_ROOT/workspaces" \
  "$RUNTIME_ROOT/config/launchd" \
  "$BENCHMARK_ROOT"

rsync -a --delete \
  --exclude '__pycache__' \
  "$SOURCE_ROOT/backend/" "$RUNTIME_ROOT/backend/"
rsync -a --delete \
  --exclude '__pycache__' \
  "$SOURCE_ROOT/src/" "$RUNTIME_ROOT/src/"
rsync -a --delete \
  --exclude '.next' \
  --exclude 'node_modules' \
  --exclude 'tests' \
  "$SOURCE_ROOT/frontend/" "$RUNTIME_ROOT/frontend/"

install -m 644 "$SOURCE_ROOT/pyproject.toml" "$RUNTIME_ROOT/pyproject.toml"
install -m 644 "$SOURCE_ROOT/uv.lock" "$RUNTIME_ROOT/uv.lock"
install -m 644 "$SOURCE_ROOT/LICENSE" "$RUNTIME_ROOT/LICENSE"
install -m 644 \
  "$SOURCE_ROOT/docs/production/workspace-policy.md" \
  "$RUNTIME_ROOT/config/workspace-policy.md"
install -m 755 "$SOURCE_ROOT/deploy/production/start.sh" "$RUNTIME_ROOT/start.sh"
install -m 755 "$SOURCE_ROOT/deploy/production/stop.sh" "$RUNTIME_ROOT/stop.sh"
install -m 755 "$SOURCE_ROOT/deploy/production/status.sh" "$RUNTIME_ROOT/status.sh"
/usr/bin/sed \
  -e "s|__RUNTIME_ROOT__|$RUNTIME_ROOT_SED|g" \
  -e "s|__TOOL_PATH__|$TOOL_PATH_SED|g" \
  "$SOURCE_ROOT/deploy/production/launchd/com.autodevplatform.backend-worker.plist" \
  > "$RUNTIME_ROOT/config/launchd/com.autodevplatform.backend-worker.plist"
/usr/bin/sed \
  -e "s|__RUNTIME_ROOT__|$RUNTIME_ROOT_SED|g" \
  -e "s|__NODE_BIN__|$NODE_BIN_SED|g" \
  -e "s|__TOOL_PATH__|$TOOL_PATH_SED|g" \
  "$SOURCE_ROOT/deploy/production/launchd/com.autodevplatform.frontend.plist" \
  > "$RUNTIME_ROOT/config/launchd/com.autodevplatform.frontend.plist"
chmod 644 "$RUNTIME_ROOT/config/launchd/"*.plist

if [[ ! -f "$RUNTIME_ROOT/config/production.env" ]]; then
  /usr/bin/sed \
    -e "s|__RUNTIME_ROOT__|$RUNTIME_ROOT_SED|g" \
    "$SOURCE_ROOT/config/production.env.example" \
    > "$RUNTIME_ROOT/config/production.env"
  chmod 600 "$RUNTIME_ROOT/config/production.env"
fi

cd "$RUNTIME_ROOT"
"$UV_BIN" sync --frozen --no-dev

cd "$RUNTIME_ROOT/frontend"
"$NPM_BIN" ci
"$NPM_BIN" run build
"$NPM_BIN" prune --omit=dev

echo "Production runtime installed at $RUNTIME_ROOT"
echo "Benchmark root prepared at $BENCHMARK_ROOT"
echo "Review $RUNTIME_ROOT/config/production.env before enabling AI execution."
