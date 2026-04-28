#!/usr/bin/env bash

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "Stopping Project Anam..."

  if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi

  if [ -n "$FRONTEND_PID" ]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi

  wait 2>/dev/null || true
  echo "Stopped."
}

trap cleanup EXIT INT TERM

cd "$ROOT_DIR"

echo "Starting Project Anam..."

if [ -d ".venv" ]; then
  echo "Activating Python virtual environment..."
  source ".venv/bin/activate"
fi

echo "Starting backend..."
python run_server.py &
BACKEND_PID=$!

echo "Starting frontend..."
cd "$ROOT_DIR/frontend"

if [ ! -d "node_modules" ]; then
  echo "Installing frontend dependencies..."
  npm install
fi

npm run dev &
FRONTEND_PID=$!

echo ""
echo "Project Anam is starting."
echo "Backend PID:  $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Frontend is usually at: http://localhost:5173"
echo "Backend is usually at:  http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop both."
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
done
