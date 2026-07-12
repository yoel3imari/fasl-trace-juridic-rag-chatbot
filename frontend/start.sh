#!/bin/sh
set -e

echo "💻 Starting frontend..."
bun run dev &

bun watcher.js

wait
