#!/bin/bash

echo "Waiting for 60 seconds..."
sleep 60  # sleep one minute to wait for chroma and postgres start
echo "Starting..."
python3 main.py