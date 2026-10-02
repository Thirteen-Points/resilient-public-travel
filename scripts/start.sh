#!/usr/bin/env bash
# ============================================================
# ResilientRoute - One-click startup script (Linux/Mac)
# ============================================================
# Usage: ./scripts/start.sh [--offline] [--no-llm] [--check-config]
#
# This script:
# 1. Checks Python availability
# 2. Creates virtual environment if needed
# 3. Installs dependencies
# 4. Validates data files
# 5. Starts the FastAPI backend server
#
# The system works without any API key or external service.
# ============================================================

set -e

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON="${PYTHON:-python3}"
PORT="${PORT:-8000}"

# Parse arguments
# Only promote an explicitly configured legacy variable; leave unset values for
# the backend's dotenv/config loader so saved configuration remains effective.
if [ -z "${AI_ENABLED+x}" ] && [ -n "${LLM_ENABLED+x}" ]; then
    export AI_ENABLED="$LLM_ENABLED"
fi
CHECK_CONFIG=false
for arg in "$@"; do
    case $arg in
        --offline)
            export OFFLINE_MODE=true
            echo "[INFO] Offline mode enabled - no external API calls"
            ;;
        --no-llm)
            export AI_ENABLED=false
            export LLM_ENABLED=false
            export AI_DISABLE_EXTERNAL=true
            echo "[INFO] LLM disabled - using deterministic fallback"
            ;;
        --check-config)
            CHECK_CONFIG=true
            ;;
        *)
            echo "[ERROR] Unknown argument: $arg" >&2
            exit 2
            ;;
    esac
done

if [ "$CHECK_CONFIG" = true ]; then
    printf 'OFFLINE_MODE=%s\nAI_ENABLED=%s\nAI_DISABLE_EXTERNAL=%s\nPORT=%s\n' "${OFFLINE_MODE:-true}" "${AI_ENABLED:-false}" "${AI_DISABLE_EXTERNAL:-false}" "$PORT"
    exit 0
fi

echo "============================================================"
echo "  ResilientRoute - Starting up..."
echo "============================================================"

# --- Step 1: Check Python ---
echo "[1/5] Checking Python..."
if ! command -v "$PYTHON" &> /dev/null; then
    echo "[ERROR] Python not found. Please install Python 3.11+."
    exit 1
fi
PY_VERSION=$($PYTHON --version 2>&1)
echo "  Found: $PY_VERSION"

# --- Step 2: Create venv if needed ---
echo ""
echo "[2/5] Setting up virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    echo "  Creating virtual environment..."
    "$PYTHON" -m venv "$VENV_DIR"
fi
PIP="$VENV_DIR/bin/pip"
PYTHON_BIN="$VENV_DIR/bin/python"

# --- Step 3: Install dependencies ---
echo ""
echo "[3/5] Installing dependencies..."
"$PIP" install --quiet --upgrade pip
"$PIP" install --quiet -r "$PROJECT_ROOT/backend/requirements.txt"
echo "  Dependencies installed."

# --- Step 4: Validate data ---
echo ""
echo "[4/5] Validating data files..."
"$PYTHON_BIN" "$PROJECT_ROOT/scripts/validate_data.py" || {
    echo "[WARN] Data validation found issues. Continuing anyway."
}

# --- Step 5: Start server ---
echo ""
echo "[5/5] Starting FastAPI server..."
echo "  Port: $PORT"
echo "  Docs: http://localhost:$PORT/docs"
echo "  Health: http://localhost:$PORT/api/health"
echo ""
echo "  Press Ctrl+C to stop."
echo "============================================================"

cd "$PROJECT_ROOT"
exec "$PYTHON_BIN" -m uvicorn backend.app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --reload
