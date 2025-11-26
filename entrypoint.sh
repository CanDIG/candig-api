#!/bin/bash

# Start the daemon in the background
python -m src.daemon &

# Start the app
exec uvicorn --host 0.0.0.0 --port 8000 src.app:app