#!/usr/bin/env python3

import typer
from pathlib import Path
import json
import shutil
from typing import Dict, Optional
import re
from concurrent.futures import ThreadPoolExecutor
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
import threading

# Import functions from our existing scripts
from transcribe import extract_audio_from_mkv, transcribe_audio
from identify_episode import match_transcript_to_episode, fetch_friends_episodes

app = typer.Typer()

# Thread-safe progress tracking
progress_lock = threading.Lock()
progress = None

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

    return filename + '.mkv'

def process_file(mkv_file: Path, output_path: Path, task_id: int, max_duration: int) -> Optional[Dict]:
    """Process a single MKV file with progress tracking"""
    try:
        # Create temporary WAV file
        temp_wav = output_path / f"{mkv_file.stem}_temp.wav"

        with progress_lock:
            progress.update(task_id, description=f"Extracting audio from {mkv_file.name}")

        # Extract audio
        if extract_audio_from_mkv(mkv_file, temp_wav, max_duration):
            with progress_lock:
                progress.update(task_id, description=f"Transcribing {mkv_file.name}")

            # Transcribe audio
            transcript = transcribe_audio(temp_wav)

            if transcript:
                result = {
                    "file_path": str(mkv_file),
                    "transcript": transcript,
                }

                # Clean up temporary WAV file
                temp_wav.unlink()
                return result

        if temp_wav.exists():
            temp_wav.unlink()

    except Exception as e:
        print(f"Error processing {mkv_file.name}: {e}")

    return None

def rename_files(transcripts: Dict, input_dir: Path, min_score: int = 60,
                template: str = "{series}.S{season}E{episode}.{title}") -> None:
    """Rename MKV files based on identified episodes"""
    # Fetch episode data
    episodes = fetch_friends_episodes()

    # Process each transcript and rename corresponding files
    for filename, data in transcripts.items():
        print(f"\nProcessing: {filename}")

        # Match transcript to episodes
        matches = match_transcript_to_episode(data['transcript'], episodes)

        # Get best match above minimum score
        if matches and matches[0][1] >= min_score:
            best_match, score = matches[0]
            print(f"Matched to: {best_match['title']} (Score: {score}%)")

            # Generate new filename
            new_filename = format_episode_filename(best_match, template)
            old_path = Path(input_dir) / filename
            new_path = Path(input_dir) / new_filename

            # Rename file
            try:
                shutil.move(old_path, new_path)
                print(f"Renamed to: {new_filename}")
            except Exception as e:
                print(f"Error renaming file: {e}")
        else:
            best_score = matches[0][1] if matches else 0
            print(f"No confident match found (Best score: {best_score}%)")

@app.command()
def main(
    input_dir: str = typer.Argument(..., help="Directory containing MKV files"),
    min_score: int = typer.Option(60, help="Minimum confidence score for renaming"),
    max_duration: int = typer.Option(90, help="Seconds of audio to transcribe for matching"),
    workers: int = typer.Option(4, help="Number of parallel workers for transcription"),
    template: str = typer.Option(
        "{series}.S{season}E{episode}.{title}",
        help="Template for renamed files. Available variables: {series}, {season}, {episode}, {title}"
    )
):
    """
    Process MKV files in a directory:
    1. Transcribe the first N seconds of each file
    2. Identify the Friends episode
    3. Rename the file to match the episode
    """
    global progress

    input_path = Path(input_dir)
    temp_output = input_path / "temp_output"
    temp_output.mkdir(exist_ok=True)

    # Get list of MKV files
    mkv_files = list(input_path.glob("*.mkv"))
    if not mkv_files:
        print("No MKV files found in the input directory.")
        return

    results = {}

    # Process files in parallel with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
    ) as progress:
        task_id = progress.add_task("Processing files...", total=len(mkv_files))

        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all files for parallel processing
            future_to_file = {
                executor.submit(process_file, f, temp_output, task_id, max_duration): f
                for f in mkv_files
            }

            # Collect results as they complete
            for future in future_to_file:
                mkv_file = future_to_file[future]
                result = future.result()

                if result:
                    results[mkv_file.name] = result

                with progress_lock:
                    progress.advance(task_id)

    print("\nStep 2: Identifying episodes and renaming files...")
    rename_files(results, input_path, min_score, template)

    # Cleanup
    if temp_output.exists():
        shutil.rmtree(temp_output)

    print("\nDone!")

if __name__ == "__main__":
    app()
