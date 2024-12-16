#!/bin/bash

# Check if OMDB API key is set
if [ ! -f .env ] || ! grep -q "OMDB_API_KEY" .env; then
    echo "Error: OMDB API key not found in .env file"
    echo "Please copy .env.example to .env and add your OMDB API key"
    exit 1
fi

# Create input directory
mkdir -p input

# Download sample episode clip
echo "Downloading sample Friends episode clip..."
python3 process_episode.py from-url "https://www.youtube.com/watch?v=mO133a-Tutw" input/

echo "Done! Check input/ directory for the processed episode."
