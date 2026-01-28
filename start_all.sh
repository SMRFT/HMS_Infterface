#!/bin/bash

# Function to kill background processes when script is stopped
cleanup() {
    echo "Stopping services..."
    kill $(jobs -p)
    exit
}

# Trap SIGINT (Ctrl+C)
trap cleanup SIGINT

echo "Starting Django Server..."
python3 manage.py runserver &

echo "Starting Automation Worker..."
python3 manage.py automate_results &

# Wait for all background processes
wait
