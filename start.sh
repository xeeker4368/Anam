#!/usr/bin/env bash

set -euo pipefail
set -m

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID=""
FRONTEND_PID=""
COMFYUI_PID=""
COMFYUI_REUSED=false
CLEANED_UP=false
LAN_MODE=false
WITH_COMFYUI=false

BACKEND_HOST="127.0.0.1"
BACKEND_PORT="${ANAM_API_PORT:-8000}"
FRONTEND_PORT="${ANAM_FRONTEND_PORT:-5173}"
COMFYUI_HOST="127.0.0.1"
COMFYUI_PORT="${ANAM_COMFYUI_PORT:-8188}"
COMFYUI_URL="http://${COMFYUI_HOST}:${COMFYUI_PORT}"
COMFYUI_DIR="${COMFYUI_DIR:-$ROOT_DIR/ComfyUI}"
COMFYUI_PYTHON="${COMFYUI_PYTHON:-python3}"

usage() {
  cat <<EOF
Usage: ./start.sh [options]

Options:
  --lan             Expose the Vite frontend on the local network.
                    Backend remains bound to 127.0.0.1 and is reached through Vite proxy.
  --with-comfyui    Start or reuse local ComfyUI on 127.0.0.1:${COMFYUI_PORT}.
  --no-comfyui      Explicitly skip ComfyUI startup.
  --help            Show this help.

Environment:
  ANAM_API_PORT       Backend port, default 8000.
  ANAM_FRONTEND_PORT  Frontend port, default 5173.
  COMFYUI_DIR         ComfyUI checkout, default ./ComfyUI.
  COMFYUI_PYTHON      Python executable for ComfyUI, default python3.

Default mode is local-only. LAN mode is for trusted household LAN/VPN use only.
EOF
}

is_process_alive() {
  local pid="$1"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

process_group_for_pid() {
  local pid="$1"
  ps -o pgid= -p "$pid" 2>/dev/null | tr -d '[:space:]' || true
}

collect_descendants() {
  local parent="$1"
  local child

  if ! command -v pgrep >/dev/null 2>&1; then
    return 0
  fi

  while IFS= read -r child; do
    [ -z "$child" ] && continue
    collect_descendants "$child"
    echo "$child"
  done < <(pgrep -P "$parent" 2>/dev/null || true)
}

wait_for_processes_to_exit() {
  local attempts="${1:-20}"
  shift
  local pid

  for _ in $(seq 1 "$attempts"); do
    local any_alive=false
    for pid in "$@"; do
      if is_process_alive "$pid"; then
        any_alive=true
        break
      fi
    done

    if [ "$any_alive" = false ]; then
      return 0
    fi
    sleep 0.2
  done

  return 1
}

stop_started_process_tree() {
  local label="$1"
  local root_pid="$2"

  if [ -z "$root_pid" ]; then
    return 0
  fi

  if ! is_process_alive "$root_pid"; then
    echo "$label PID $root_pid is already stopped."
    return 0
  fi

  echo "Stopping $label PID $root_pid..."

  local pgid
  pgid="$(process_group_for_pid "$root_pid")"

  if [ -n "$pgid" ] && [ "$pgid" = "$root_pid" ]; then
    kill -TERM "-$pgid" 2>/dev/null || true
    if wait_for_processes_to_exit 20 "$root_pid"; then
      wait "$root_pid" 2>/dev/null || true
      echo "Stopped $label PID $root_pid."
      return 0
    fi

    echo "$label PID $root_pid did not stop after TERM; sending KILL."
    kill -KILL "-$pgid" 2>/dev/null || true
    wait "$root_pid" 2>/dev/null || true
    return 0
  fi

  local process_list
  process_list="$(collect_descendants "$root_pid"; echo "$root_pid")"
  # shellcheck disable=SC2086
  kill -TERM $process_list 2>/dev/null || true

  # shellcheck disable=SC2086
  if wait_for_processes_to_exit 20 $process_list; then
    wait "$root_pid" 2>/dev/null || true
    echo "Stopped $label PID $root_pid."
    return 0
  fi

  echo "$label PID $root_pid did not stop after TERM; sending KILL."
  process_list="$(collect_descendants "$root_pid"; echo "$root_pid")"
  # shellcheck disable=SC2086
  kill -KILL $process_list 2>/dev/null || true
  wait "$root_pid" 2>/dev/null || true
}

cleanup() {
  if [ "$CLEANED_UP" = true ]; then
    return 0
  fi
  CLEANED_UP=true
  trap - INT TERM

  echo ""
  echo "Stopping Project Anam..."

  stop_started_process_tree "frontend" "$FRONTEND_PID"
  stop_started_process_tree "backend" "$BACKEND_PID"
  if [ -n "$COMFYUI_PID" ]; then
    stop_started_process_tree "ComfyUI" "$COMFYUI_PID"
  elif [ "$COMFYUI_REUSED" = true ]; then
    echo "Skipped pre-existing ComfyUI; it was not started by this script."
  fi

  echo "Stopped."
}

handle_shutdown_signal() {
  cleanup
  exit 130
}

is_url_ready() {
  local url="$1"
  curl -fsS "$url" >/dev/null 2>&1
}

wait_for_url() {
  local url="$1"
  local label="$2"
  local attempts="${3:-30}"
  local delay="${4:-1}"

  for _ in $(seq 1 "$attempts"); do
    if is_url_ready "$url"; then
      echo "$label is ready: $url"
      return 0
    fi
    sleep "$delay"
  done

  echo "Warning: $label did not become ready at $url"
  return 1
}

detect_lan_urls() {
  local seen=""
  local ips=""

  if command -v ipconfig >/dev/null 2>&1; then
    for iface in en0 en1 en2 bridge0; do
      local ip
      ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
      if [ -n "$ip" ] && [[ "$seen" != *" $ip "* ]]; then
        ips="${ips}${ip}"$'\n'
        seen="${seen} ${ip} "
      fi
    done
  fi

  if [ -z "$ips" ] && command -v ifconfig >/dev/null 2>&1; then
    ips="$(ifconfig 2>/dev/null | awk '/inet / && $2 != "127.0.0.1" {print $2}' || true)"
  fi

  if [ -n "$ips" ]; then
    while IFS= read -r ip; do
      [ -n "$ip" ] && echo "  http://${ip}:${FRONTEND_PORT}"
    done <<< "$ips"
  else
    echo "  Could not detect a LAN IPv4 address. Check macOS Network settings."
  fi

  return 0
}

python_for_backend() {
  if [ -x "$ROOT_DIR/.pyanam/bin/python" ]; then
    echo "$ROOT_DIR/.pyanam/bin/python"
  elif [ -x "$ROOT_DIR/.venv/bin/python" ]; then
    echo "$ROOT_DIR/.venv/bin/python"
  else
    echo "python3"
  fi
}

start_backend() {
  local python_bin
  python_bin="$(python_for_backend)"
  echo "Starting backend on ${BACKEND_HOST}:${BACKEND_PORT}..."
  (
    cd "$ROOT_DIR"
    ANAM_API_HOST="$BACKEND_HOST" ANAM_API_PORT="$BACKEND_PORT" "$python_bin" run_server.py
  ) &
  BACKEND_PID=$!
}

start_frontend() {
  local frontend_host="127.0.0.1"
  if [ "$LAN_MODE" = true ]; then
    frontend_host="0.0.0.0"
  fi

  echo "Starting frontend on ${frontend_host}:${FRONTEND_PORT}..."
  (
    cd "$ROOT_DIR/frontend"
    if [ ! -d "node_modules" ]; then
      echo "Installing frontend dependencies..."
      npm install
    fi
    npm run dev -- --host "$frontend_host" --port "$FRONTEND_PORT"
  ) &
  FRONTEND_PID=$!
}

start_comfyui_if_requested() {
  if [ "$WITH_COMFYUI" != true ]; then
    echo "ComfyUI skipped."
    return 0
  fi

  if is_url_ready "${COMFYUI_URL}/system_stats"; then
    echo "ComfyUI already running at ${COMFYUI_URL}; reusing it."
    COMFYUI_REUSED=true
    return 0
  fi

  if [ ! -f "$COMFYUI_DIR/main.py" ]; then
    echo "Warning: ComfyUI main.py not found at $COMFYUI_DIR/main.py"
    echo "Image generation may be unavailable until ComfyUI is started separately."
    return 0
  fi

  echo "Starting ComfyUI on ${COMFYUI_HOST}:${COMFYUI_PORT}..."
  echo "ComfyUI Python: $COMFYUI_PYTHON"
  (
    cd "$COMFYUI_DIR"
    "$COMFYUI_PYTHON" main.py --listen "$COMFYUI_HOST" --port "$COMFYUI_PORT"
  ) &
  COMFYUI_PID=$!

  if ! wait_for_url "${COMFYUI_URL}/system_stats" "ComfyUI" 45 1; then
    echo "Warning: ComfyUI did not become ready."
    echo "If this is a dependency error, set COMFYUI_PYTHON to the Python executable for your ComfyUI install."
    echo "Continuing Project Anam startup without ready ComfyUI."
    if ! kill -0 "$COMFYUI_PID" 2>/dev/null; then
      COMFYUI_PID=""
    fi
  fi
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --lan)
      LAN_MODE=true
      ;;
    --with-comfyui)
      WITH_COMFYUI=true
      ;;
    --no-comfyui)
      WITH_COMFYUI=false
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo ""
      usage
      exit 2
      ;;
  esac
  shift
done

trap cleanup EXIT
trap handle_shutdown_signal INT TERM

cd "$ROOT_DIR"

echo "Starting Project Anam..."
if [ "$LAN_MODE" = true ]; then
  echo "LAN/VPN trusted-household mode only. Do not expose to public internet."
fi

start_backend
wait_for_url "http://${BACKEND_HOST}:${BACKEND_PORT}/api/health" "Backend" 30 1 || true

start_comfyui_if_requested

start_frontend
wait_for_url "http://127.0.0.1:${FRONTEND_PORT}" "Frontend" 30 1 || true

echo ""
echo "Project Anam is starting."
echo "Backend PID:  $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
if [ -n "$COMFYUI_PID" ]; then
  echo "ComfyUI PID:  $COMFYUI_PID"
fi
echo ""
echo "Frontend local URL: http://127.0.0.1:${FRONTEND_PORT}"
echo "Backend local URL:  http://${BACKEND_HOST}:${BACKEND_PORT}"
if [ "$LAN_MODE" = true ]; then
  echo ""
  echo "Frontend LAN URL(s):"
  detect_lan_urls
fi
if [ "$WITH_COMFYUI" = true ]; then
  echo ""
  echo "ComfyUI local URL:  ${COMFYUI_URL}"
fi
echo ""
echo "Press Ctrl+C to stop services started by this script."
echo ""

while true; do
  sleep 2

  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Backend stopped unexpectedly."
    exit 1
  fi

  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "Frontend stopped unexpectedly."
    exit 1
  fi

  if [ -n "$COMFYUI_PID" ] && ! kill -0 "$COMFYUI_PID" 2>/dev/null; then
    echo "Warning: ComfyUI stopped unexpectedly. Continuing Project Anam."
    COMFYUI_PID=""
  fi
done
