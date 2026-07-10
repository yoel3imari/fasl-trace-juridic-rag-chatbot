#!/bin/bash
set -e

if [ -f /.dockerenv ]; then
    echo "Running in Docker"
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
    python watcher.py
else
    echo "Running locally with uv"
    uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
    uv run python watcher.py
fi

wait
