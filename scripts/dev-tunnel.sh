#!/usr/bin/env bash
# Usage: ./scripts/dev-tunnel.sh [start|stop|status|restart]
#
# Exposes the in-cluster services to the host (and the LAN/Tailscale
# interfaces) via `kubectl port-forward`. Backgrounds each forward, writes
# logs to /tmp/arena-dev/pf-*.log, and stores PIDs in /tmp/arena-dev/pf.pids.
#
#   start    Start all port-forwards (default)
#   stop     Kill all port-forwards
#   status   Show which port-forwards are running
#   restart  stop + start
set -euo pipefail

NS="${NAMESPACE:-arena}"
RELEASE="${RELEASE:-arena}"
LOG_DIR="${LOG_DIR:-/tmp/arena-dev}"
PID_FILE="$LOG_DIR/pf.pids"

mkdir -p "$LOG_DIR"

# service:port → host port mapping
declare -A FORWARDS=(
  ["${RELEASE}-backend"]="30090:8000"
  ["${RELEASE}-mcp"]="9998:9999"
  ["${RELEASE}-docs"]="8080:80"
  ["${RELEASE}-db"]="5432:5432"
  ["${RELEASE}-redis"]="6379:6379"
)

start_one() {
  local svc="$1"
  local hp_cp="$2"
  local hp="${hp_cp%%:*}"
  local log="$LOG_DIR/pf-${svc}.log"
  # setsid → new session, fully detached from the controlling tty so the
  # port-forward survives the launching shell exiting.
  setsid nohup kubectl -n "$NS" port-forward "svc/${svc}" "${hp_cp}" --address 0.0.0.0 \
    >"$log" 2>&1 < /dev/null &
  echo $! >> "$PID_FILE"
  printf "  %-25s 0.0.0.0:%-5s → svc/%-20s  (pid %s, log %s)\n" \
    "$svc" "$hp" "$svc" "$!" "$log"
}

start_all() {
  : > "$PID_FILE"
  echo "Starting port-forwards in $NS ..."
  for svc in "${!FORWARDS[@]}"; do
    if kubectl -n "$NS" get svc "$svc" >/dev/null 2>&1; then
      start_one "$svc" "${FORWARDS[$svc]}"
    else
      echo "  ! svc/$svc not found in namespace $NS — skipping"
    fi
  done
  echo
  echo "  Reach from this host (or any Tailscale node):"
  HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  # Pull host port from the FORWARDS map so the URL block can't lie.
  bp="${FORWARDS[${RELEASE}-backend]%%:*}"
  mp="${FORWARDS[${RELEASE}-mcp]%%:*}"
  dp="${FORWARDS[${RELEASE}-docs]%%:*}"
  pgp="${FORWARDS[${RELEASE}-db]%%:*}"
  rdp="${FORWARDS[${RELEASE}-redis]%%:*}"
  echo "    Backend    http://${HOST_IP}:${bp}/  (also serves the SPA at /)"
  echo "    MCP        http://${HOST_IP}:${mp}/"
  echo "    Docs       http://${HOST_IP}:${dp}/"
  echo "    Postgres   ${HOST_IP}:${pgp}"
  echo "    Redis      ${HOST_IP}:${rdp}"
  echo
  echo "  Stop with:  $0 stop"
}

stop_all() {
  if [ ! -f "$PID_FILE" ]; then
    echo "No PID file at $PID_FILE — nothing to stop."
    return 0
  fi
  echo "Stopping port-forwards ..."
  while read -r pid; do
    [ -z "$pid" ] && continue
    if kill "$pid" 2>/dev/null; then
      echo "  killed pid $pid"
    fi
  done < "$PID_FILE"
  rm -f "$PID_FILE"
  # Also clean up any stray kubectl port-forward processes
  pkill -f "kubectl .* port-forward" 2>/dev/null || true
}

status_all() {
  if [ ! -f "$PID_FILE" ]; then
    echo "No PID file at $PID_FILE — not running."
    return 0
  fi
  echo "Active port-forwards:"
  while read -r pid; do
    [ -z "$pid" ] && continue
    if kill -0 "$pid" 2>/dev/null; then
      printf "  pid %-7s %s\n" "$pid" "$(ps -p "$pid" -o args= 2>/dev/null | head -c 120)"
    else
      echo "  pid $pid (dead)"
    fi
  done < "$PID_FILE"
}

case "${1:-start}" in
  start)   start_all ;;
  stop)    stop_all ;;
  status)  status_all ;;
  restart) stop_all; sleep 1; start_all ;;
  *) echo "Usage: $0 [start|stop|status|restart]" >&2; exit 2 ;;
esac
