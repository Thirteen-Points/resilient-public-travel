#!/usr/bin/env bash
# ============================================================
# ResilientRoute - One-click startup script (Linux/Mac)
# ============================================================
# Usage: ./scripts/start.sh [--offline] [--no-llm]
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
OFFLINE_FLAG=""
for arg in "$@"; do
    case $arg in
        --offline)
            OFFLINE_FLAG="OFFLINE_MODE=true"
            echo "[INFO] Offline mode enabled - no external API calls"
            ;;
        --no-llm)
            export LLM_ENABLED=false
            echo "[INFO] LLM disabled - using deterministic fallback"
            ;;
    esac
done

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
