#!/usr/bin/env bash
set -e
echo "========================================================"
echo "  Starting Adaptive AI Orchestrator..."
echo "========================================================"

if ! command -v python3 &> /dev/null; then
    echo "[Error] python3 could not be found. Please install Python 3.10+."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate || true

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "Creating initial .env from template..."
    cp .env.example .env
fi

python3 run_server.py
