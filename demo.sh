#!/bin/bash

# Exit on error
set -e

echo "Creating demo directories..."
mkdir -p input output

echo "Installing yt-dlp if not present..."
pip install --user --upgrade yt-dlp

echo "Downloading sample video..."
yt-dlp -f 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' \
    "https://www.youtube.com/watch?v=gmr41ht2Sq4" \
    -o "input/sample_episode.mp4"

echo "Converting to MKV..."
ffmpeg -i input/sample_episode.mp4 -c copy input/sample_episode.mkv

echo "Cleaning up MP4..."
rm input/sample_episode.mp4

echo "Running episode detection and automatic renaming..."
python3 rename_episodes.py input --min-score 55 --max-duration 90

echo "Done! The MKV file has been renamed according to the detected episode."
echo "Check the input directory for the renamed file."
