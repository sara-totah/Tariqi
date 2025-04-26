#!/bin/bash
set -e

# Function to start the FastAPI app
start_fastapi() {
    echo "Starting FastAPI application..."
    uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --workers 4
}

# Function to start the scheduler
start_scheduler() {
    echo "Starting verification pipeline scheduler..."
    python app/scheduler.py
}

# Check if we should run in combined mode or specific service
if [ "${SERVICE_TYPE}" = "scheduler" ]; then
    start_scheduler
elif [ "${SERVICE_TYPE}" = "api" ]; then
    start_fastapi
else
    echo "Please set SERVICE_TYPE environment variable to either 'api' or 'scheduler'"
    exit 1
fi 