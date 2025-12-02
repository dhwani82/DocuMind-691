#!/bin/bash

# DocuMind Startup Script
# Set your OpenAI API key here or export it before running

# Option 1: Set it directly in this script (replace YOUR_API_KEY_HERE)
# export OPENAI_API_KEY="YOUR_API_KEY_HERE"

# Option 2: Uncomment the line below to read from a .env file
# source .env

# Start the Flask application
cd "$(dirname "$0")"
python3 app.py

