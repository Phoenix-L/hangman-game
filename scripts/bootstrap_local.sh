#!/usr/bin/env bash
# Idempotent local setup: git pull, venv, dependencies, tests, database seed.
# Usage (from anywhere): bash scripts/bootstrap_local.sh
# Offline / no DNS: BOOTSTRAP_SKIP_GIT=1 bash scripts/bootstrap_local.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [ -n "${BOOTSTRAP_SKIP_GIT:-}" ]; then
  echo "==> Skipping git pull (BOOTSTRAP_SKIP_GIT is set)."
elif [ -d .git ]; then
  echo "==> Pulling latest updates from remote (git pull)..."
  GIT_TERMINAL_PROMPT=0 git pull || {
    echo "Error: git pull failed; aborting bootstrap." >&2
    echo "       Fix network/DNS (e.g. getent hosts github.com) or run offline with:" >&2
    echo "       BOOTSTRAP_SKIP_GIT=1 bash scripts/bootstrap_local.sh" >&2
    exit 1
  }
else
  echo "==> Skipping git pull (no .git directory — not a git checkout)."
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required but was not found in PATH." >&2
  exit 1
fi

echo "==> Repository root: ${REPO_ROOT}"

echo "==> Creating virtual environment (if missing)..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate

echo "==> Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "==> Running tests..."
python -m pytest -q

echo "==> Initializing database..."
if [ -f "scripts/init_db.py" ]; then
  python scripts/init_db.py
else
  echo "    (skipped: scripts/init_db.py not found)"
fi

echo ""
echo "==> Done!"
echo "Activate the venv and run the app:"
echo "    cd \"${REPO_ROOT}\""
echo "    source .venv/bin/activate && python server.py"
echo "Then open http://localhost:5000"
echo ""
echo "Optional: LAN mode — source .venv/bin/activate && python run_lan_server.py"
