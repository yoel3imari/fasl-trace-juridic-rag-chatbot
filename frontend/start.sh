#!/bin/bash
set -e

echo "💻 Starting frontend..."
pnpm run dev &

node watcher.js

wait
