#!/usr/bin/env bash
# Build TimeTracker.app for macOS
set -e

echo "Installing dependencies..."
pip3 install pyinstaller supabase reportlab

echo ""
echo "Building TimeTracker.app..."
pyinstaller \
    --onefile \
    --noconsole \
    --name TimeTracker \
    --collect-all supabase \
    --collect-all gotrue \
    --collect-all postgrest \
    --collect-all realtime \
    --collect-all storage3 \
    --collect-all supafunc \
    --hidden-import httpx \
    --hidden-import httpcore \
    --hidden-import anyio \
    --hidden-import sniffio \
    --hidden-import certifi \
    timetracker.py

echo ""
if [ -f dist/TimeTracker ]; then
    echo "SUCCESS: dist/TimeTracker is ready."
else
    echo "FAILED: check the output above."
fi
