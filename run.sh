#!/usr/bin/env bash
# One-command setup + run: Star-Office backend + herdr bridge.
#   ./run.sh              # setup (if needed), start backend, then run the bridge (foreground)
#   ./run.sh backend      # only (re)start the backend
#   ./run.sh bridge       # only run the bridge (backend must be up)
#   ./run.sh --all        # bridge includes unnamed pi panes too
set -euo pipefail
cd "$(dirname "$0")"

OFFICE_URL="${OFFICE_URL:-http://127.0.0.1:19000}"
PORT="${PORT:-19000}"
UPSTREAM="https://github.com/ringhyacinth/Star-Office-UI.git"

setup() {
  [ -d star-office/.git ] || git clone --depth 1 "$UPSTREAM" star-office
  [ -d .venv ] || python3 -m venv .venv
  ./.venv/bin/pip install --quiet -r star-office/backend/requirements.txt
  [ -f star-office/state.json ] || cp star-office/state.sample.json star-office/state.json
  # one reusable join key with room for all local agents
  cat > star-office/join-keys.json <<'JSON'
{ "keys": [ { "key": "ocj_example_team_01", "used": false, "reusable": true, "maxConcurrent": 30, "usedBy": null, "usedByAgentId": null, "usedAt": null } ] }
JSON
}

start_backend() {
  pkill -f "star-office/backend/app.py" 2>/dev/null || true
  sleep 1
  PORT="$PORT" nohup ./.venv/bin/python star-office/backend/app.py > backend.log 2>&1 &
  echo "backend pid $! -> $OFFICE_URL (log: backend.log)"
  for i in $(seq 1 15); do
    sleep 1
    curl -sf "$OFFICE_URL/health" >/dev/null 2>&1 && { echo "backend healthy"; return 0; }
  done
  echo "backend did not become healthy; see backend.log" >&2; return 1
}

run_bridge() { exec ./.venv/bin/python bridge/herdr_bridge.py "$@"; }

case "${1:-run}" in
  backend) setup; start_backend ;;
  bridge)  shift || true; run_bridge "$@" ;;
  run|--all|*)
    setup; start_backend
    echo "open $OFFICE_URL in a browser, then the bridge streams herdr agent states:"
    [ "${1:-}" = "--all" ] && run_bridge --all || run_bridge ;;
esac
