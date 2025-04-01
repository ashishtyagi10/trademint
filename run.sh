#!/bin/bash

echo "Starting Daphne server..."
daphne -v 2 -b localhost -p 8000 --proxy-headers trademint.asgi:application &
DAPHNE_PID=$!

# Wait for Daphne to start
sleep 2

echo "Starting Forex generator..."
python manage.py run_forex_generator &
FOREX_PID=$!

echo "Starting Thinkorswim generator..."
python manage.py run_thinkorswim_generator &
THINKORSWIM_PID=$!

# Function to cleanup processes
cleanup() {
    echo "Cleaning up processes..."
    kill $DAPHNE_PID
    kill $FOREX_PID
    kill $THINKORSWIM_PID
    exit 0
}

# Setup trap for cleanup
trap cleanup SIGINT SIGTERM

echo "All services started. Press Ctrl+C to stop."

# Keep script running
wait 