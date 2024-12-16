#!/usr/bin/env python3

import typer
from pathlib import Path
import json
import shutil
import re
import os
import subprocess
from typing import Dict, Optional, List
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
import threading
import ffmpeg
import whisper
import torch
from identify_episode import match_transcript_to_episode, fetch_friends_episodes

app = typer.Typer()

def download_episode(url: str, output_dir: Path) -> Optional[Path]:
    """
    Download video from URL using yt-dlp and convert to MKV format.
    Returns the path to the downloaded MKV file.
    """
    try:
        print(f"Downloading audio from {url}...")

        # Download only audio
        temp_audio = output_dir / "temp_audio.m4a"
        download_cmd = [
            "yt-dlp",
            "-f", "worstaudio[ext=m4a]",  # Use lowest quality audio since we only need it for transcription
            "-o", str(temp_audio),
            "--progress",  # Show download progress
            "--no-warnings",  # Reduce output noise
            "--no-playlist",  # Don't process playlists
            url
        ]
        subprocess.run(download_cmd, check=True, capture_output=True, text=True)

        # Convert to MKV
        output_mkv = output_dir / "episode.mkv"
        convert_cmd = [
            "ffmpeg",
            "-y",
            "-i", str(temp_audio),
            "-c", "copy",
            str(output_mkv)
        ]
        subprocess.run(convert_cmd, check=True, capture_output=True, text=True)

        # Clean up temporary file
        temp_audio.unlink()

        return output_mkv
    except subprocess.CalledProcessError as e:
        print(f"Error downloading/converting video: {e}")
        if e.stdout:
            print(f"Output: {e.stdout}")
        if e.stderr:
            print(f"Error details: {e.stderr}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def extract_audio(mkv_path: Path, output_path: Path, max_duration: Optional[int] = None) -> bool:
    """
    Extract audio from MKV file using ffmpeg.
    Converts to WAV format which is well-supported by most STT engines.
    Optionally limits the duration of the extracted audio.
    """
    try:
        command = [
            "ffmpeg",
            "-y",  # Automatically overwrite output files
            "-loglevel",
            "error",  # Show errors only
            "-i",
            str(mkv_path),
            "-vn",  # No video
            "-acodec",
            "pcm_s16le",  # Convert to PCM WAV
            "-ar",
            "16000",  # 16kHz sample rate
            "-ac",
            "1",  # Mono channel
        ]

        # Add duration limit if specified
        if max_duration:
            command.extend(["-t", str(max_duration)])

        command.extend(["-f", "wav", str(output_path)])

        subprocess.run(command, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error extracting audio: {e}")
        if e.stderr:
            print(f"FFmpeg error: {e.stderr.decode()}")
        return False

def transcribe_audio(audio_path: Path) -> Optional[str]:
    """
    Transcribe audio using Whisper.
    Returns the transcribed text.
    """
    try:
        # Force CUDA device if available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            print(f"Using GPU: {torch.cuda.get_device_name(0)}")
            print(f"GPU Memory allocated: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")

            # load model on GPU
            model = whisper.load_model("tiny")
            model = model.cuda()
            torch.cuda.synchronize()

            print(f"GPU Memory after model load: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")

            # Enable mixed precision for faster processing
            with torch.cuda.amp.autocast():
                result = model.transcribe(
                    str(audio_path),
                    language="en",
                    initial_prompt="TV show episode transcript:",
                    fp16=True,
                )
                torch.cuda.synchronize()

            print(f"GPU Memory after transcription: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")
        else:
            print("No GPU found, using CPU for transcription...")
            model = whisper.load_model("tiny")
            result = model.transcribe(
                str(audio_path),
                language="en",
                initial_prompt="TV show episode transcript:",
            )

        return result["text"].strip()
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return None

def format_episode_filename(episode: Dict, template: str) -> str:
    """Format episode information into filename using template"""
    # Clean title by replacing spaces with dots and removing special characters
    clean_title = re.sub(r'[^\w\s-]', '', episode['title'])
    clean_title = clean_title.replace(' ', '.')

    # Available template variables
    variables = {
        '{series}': 'Friends',
        '{season}': f"{episode['season']:02d}",
        '{episode}': f"{episode['episode']:02d}",
        '{title}': clean_title
    }

    # Replace template variables
    filename = template
    for var, value in variables.items():
        filename = filename.replace(var, value)

    return filename

def update_mkv_metadata(mkv_path: Path, episode_info: Dict) -> bool:
    """
    Update MKV file metadata with episode information.
    """
    try:
        print(f"\nUpdating metadata for episode: S{episode_info['season']:02d}E{episode_info['episode']:02d} - {episode_info['title']}")

        # Create temporary file for output
        temp_path = mkv_path.parent / f"temp_{mkv_path.name}"

        # Build ffmpeg command
        command = [
            "ffmpeg",
            "-y",
            "-loglevel", "error",
            "-i", str(mkv_path),
            "-c", "copy",
            "-metadata", f"title=Friends - S{episode_info['season']:02d}E{episode_info['episode']:02d} - {episode_info['title']}",
            "-metadata", "show=Friends",
            "-metadata", f"season_number={episode_info['season']}",
            "-metadata", f"episode_sort={episode_info['episode']}",
            "-metadata", f"episode_id=S{episode_info['season']:02d}E{episode_info['episode']:02d}",
            "-metadata", f"description={episode_info['summary']}",
            str(temp_path)
        ]

        subprocess.run(command, check=True)
        os.replace(temp_path, mkv_path)
        return True

    except Exception as e:
        print(f"Error updating metadata: {e}")
        if temp_path and temp_path.exists():
            temp_path.unlink()
        return False

def process_episode(
    mkv_path: Path,
    min_score: int = 60,
    max_duration: Optional[int] = 90,
    template: str = "{series}.S{season}E{episode}.{title}"
) -> bool:
    """
    Process a single episode:
    1. Extract audio
    2. Transcribe
    3. Match to episode
    4. Update metadata and rename
    """
    try:
        # Create temporary directory
        temp_dir = mkv_path.parent / "temp"
        temp_dir.mkdir(exist_ok=True)
        temp_wav = temp_dir / "temp.wav"

        # Extract audio
        print("Extracting audio...")
        if not extract_audio(mkv_path, temp_wav, max_duration):
            return False

        # Transcribe audio
        print("Transcribing audio...")
        transcript = transcribe_audio(temp_wav)
        if not transcript:
            return False

        # Save transcript with original filename
        transcript_path = mkv_path.parent / f"{mkv_path.stem}.txt"
        with open(transcript_path, 'w') as f:
            f.write(transcript)
        print(f"Saved transcript to: {transcript_path}")

        # Match transcript to episode
        print("Matching transcript to episode...")
        episodes = fetch_friends_episodes()
        matches = match_transcript_to_episode(transcript, episodes)

        if matches and matches[0][1] >= min_score:
            best_match, score = matches[0]
            print(f"Matched to: {best_match['title']} (Score: {score}%)")

            # Update metadata
            if not update_mkv_metadata(mkv_path, best_match):
                return False

            # Generate new filename without extension
            new_filename = format_episode_filename(best_match, template)

            # Rename video file
            new_video_path = mkv_path.parent / f"{new_filename}.mkv"
            shutil.move(mkv_path, new_video_path)
            print(f"Renamed video to: {new_video_path.name}")

            # Rename transcript file to match
            new_transcript_path = mkv_path.parent / f"{new_filename}.txt"
            shutil.move(transcript_path, new_transcript_path)
            print(f"Renamed transcript to: {new_transcript_path.name}")

            return True
        else:
            best_score = matches[0][1] if matches else 0
            print(f"No confident match found (Best score: {best_score}%)")
            return False

    except Exception as e:
        print(f"Error processing episode: {e}")
        return False
    finally:
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

@app.command()
def from_url(
    url: str = typer.Argument(..., help="URL of the video to download"),
    output_dir: str = typer.Argument(..., help="Directory to save the processed file"),
    min_score: int = typer.Option(60, help="Minimum confidence score for matching"),
    max_duration: int = typer.Option(90, help="Seconds of audio to transcribe for matching"),
    template: str = typer.Option(
        "{series}.S{season}E{episode}.{title}",
        help="Template for renamed files. Available variables: {series}, {season}, {episode}, {title}"
    )
):
    """
    Process a Friends episode from a video URL:
    1. Download video and convert to MKV
    2. Extract and transcribe audio
    3. Match to episode database
    4. Update metadata and rename file
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Download and convert video
    mkv_path = download_episode(url, output_path)  # Removed max_duration parameter
    if not mkv_path:
        print("Failed to download/convert video")
        return

    # Process the episode
    if process_episode(mkv_path, min_score, max_duration, template):
        print("\nSuccessfully processed episode!")
    else:
        print("\nFailed to process episode")

@app.command()
def from_file(
    input_file: str = typer.Argument(..., help="Path to input MKV file"),
    min_score: int = typer.Option(60, help="Minimum confidence score for matching"),
    max_duration: int = typer.Option(90, help="Seconds of audio to transcribe for matching"),
    template: str = typer.Option(
        "{series}.S{season}E{episode}.{title}",
        help="Template for renamed files. Available variables: {series}, {season}, {episode}, {title}"
    )
):
    """
    Process an existing MKV file:
    1. Extract and transcribe audio
    2. Match to episode database
    3. Update metadata and rename file
    """
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"File not found: {input_file}")
        return

    if process_episode(input_path, min_score, max_duration, template):
        print("\nSuccessfully processed episode!")
    else:
        print("\nFailed to process episode")

@app.command()
def batch(
    input_dir: str = typer.Argument(..., help="Directory containing MKV files"),
    min_score: int = typer.Option(60, help="Minimum confidence score for matching"),
    max_duration: int = typer.Option(90, help="Seconds of audio to transcribe for matching"),
    template: str = typer.Option(
        "{series}.S{season}E{episode}.{title}",
        help="Template for renamed files. Available variables: {series}, {season}, {episode}, {title}"
    )
):
    """
    Process all MKV files in a directory:
    1. Extract and transcribe audio from each file
    2. Match to episode database
    3. Update metadata and rename files
    """
    input_path = Path(input_dir)
    mkv_files = list(input_path.glob("*.mkv"))
    if not mkv_files:
        print("No MKV files found in the input directory")
        return

    success_count = 0
    for mkv_file in mkv_files:
        print(f"\nProcessing: {mkv_file.name}")
        if process_episode(mkv_file, min_score, max_duration, template):
            success_count += 1

    print(f"\nProcessed {success_count} of {len(mkv_files)} files successfully")

if __name__ == "__main__":
    app()
