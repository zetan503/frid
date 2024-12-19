#!/usr/bin/env python3

import subprocess
import os
from pathlib import Path
import whisper
import json
import typer
import torch
import time
from typing import Optional, Dict
import ffmpeg
from identify_episode import fetch_friends_episodes, match_transcript_to_episode

app = typer.Typer()

MATCH_THRESHOLD = 50  # Lowered from 60 since we're getting close matches

def extract_audio_from_mkv(mkv_path, output_path, max_duration=None):
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
        print(f"Error extracting audio from {mkv_path}: {e}")
        if e.stderr:
            print(f"FFmpeg error: {e.stderr.decode()}")
        return False

def transcribe_audio(audio_path):
    """
    Transcribe audio using Whisper.
    Returns the transcribed text.
    """
    try:
        # Force CUDA device if available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            print(f"Using GPU: {torch.cuda.get_device_name(0)}")
            print(
                f"GPU Memory allocated: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB"
            )

            model = whisper.load_model("turbo")
            model = model.cuda()  # Explicitly move to GPU
            torch.cuda.synchronize()  # Ensure model is loaded to GPU

            print(
                f"GPU Memory after model load: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB"
            )

            # Create a more detailed initial prompt for better context
            initial_prompt = """
            This is a transcript from the TV show Friends. The main characters are:
            - Ross Geller: paleontologist, Monica's brother
            - Rachel Green: fashion enthusiast, Monica's friend
            - Monica Geller: chef, Ross's sister
            - Chandler Bing: office worker, Joey's roommate
            - Joey Tribbiani: actor
            - Phoebe Buffay: masseuse, musician

            Common locations include their apartments, Central Perk coffee shop, and various New York City settings.

            The transcript should focus on capturing:
            1. Key plot points and events
            2. Specific actions and decisions
            3. Important conversations and revelations
            4. Unique or special occasions

            Please transcribe with attention to these elements while maintaining accuracy of the dialogue.
            """

            # Enable mixed precision for faster processing
            with torch.cuda.amp.autocast():
                result = model.transcribe(
                    str(audio_path),
                    language="en",
                    initial_prompt=initial_prompt,
                    fp16=True,  # Enable FP16 on GPU
                    # Additional parameters for better transcription
                    task="transcribe",
                    condition_on_previous_text=True,
                    temperature=0.0,  # Reduce randomness
                    best_of=5,  # Increase beam search
                    no_speech_threshold=0.6,  # Stricter silence detection
                )
                torch.cuda.synchronize()  # Ensure processing is complete

            print(
                f"GPU Memory after transcription: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB"
            )
        else:
            print("No GPU found, using CPU for transcription...")
            model = whisper.load_model("tiny")
            result = model.transcribe(
                str(audio_path),
                language="en",
                initial_prompt=initial_prompt,
                condition_on_previous_text=True,
                temperature=0.0,
                best_of=5,
                no_speech_threshold=0.6,
            )

        # Post-process the transcript to improve readability and context
        transcript = result["text"].strip()

        # Clean up common transcription artifacts
        transcript = transcript.replace(" ,", ",")
        transcript = transcript.replace(" .", ".")
        transcript = transcript.replace(" ?", "?")
        transcript = transcript.replace(" !", "!")

        # Add paragraph breaks at natural pauses
        transcript = transcript.replace(". ", ".\n\n")

        return transcript
    except Exception as e:
        print(f"Error transcribing {audio_path}: {e}")
        return None

def display_mkv_metadata(mkv_path: Path):
    """
    Display metadata of the MKV file using ffmpeg-python.
    """
    try:
        probe = ffmpeg.probe(str(mkv_path))
        print("\nUpdated MKV Metadata:")
        print("-" * 50)
        for stream in probe["streams"]:
            if "tags" in stream:
                print(f"\nStream #{stream['index']} metadata:")
                for key, value in stream["tags"].items():
                    print(f"{key}: {value}")
        if "format" in probe and "tags" in probe["format"]:
            print("\nFormat metadata:")
            for key, value in probe["format"]["tags"].items():
                print(f"{key}: {value}")
        print("-" * 50)
    except ffmpeg.Error as e:
        print(f"Error reading metadata from {mkv_path}: {e.stderr.decode()}")

def update_mkv_metadata(
    mkv_path: Path, episode_info: Dict, min_score: int = MATCH_THRESHOLD
):
    """
    Update MKV file metadata with episode information.
    Only updates if match score meets minimum threshold.
    """
    try:
        print(
            f"\nUpdating metadata for episode: S{episode_info['season']:02d}E{episode_info['episode']:02d} - {episode_info['title']}"
        )

        # Extract episode information
        title = f"Friends - S{episode_info['season']:02d}E{episode_info['episode']:02d} - {episode_info['title']}"

        # Create temporary file for output
        temp_path = mkv_path.parent / f"temp_{mkv_path.name}"

        # Build ffmpeg command using subprocess for better metadata handling
        command = [
            "ffmpeg",
            "-y",  # Automatically overwrite output files
            "-loglevel",
            "error",  # Show errors only
            "-i",
            str(mkv_path),
            "-c",
            "copy",
            "-metadata",
            f"title={title}",
            "-metadata",
            f"show=Friends",
            "-metadata",
            f"season_number={episode_info['season']}",
            "-metadata",
            f"episode_sort={episode_info['episode']}",
            "-metadata",
            f"episode_id=S{episode_info['season']:02d}E{episode_info['episode']:02d}",
            "-metadata",
            f"description={episode_info['summary']}",
            str(temp_path),
        ]

        print("Running ffmpeg to update metadata...")
        # Run ffmpeg command
        subprocess.run(command, check=True, capture_output=True)

        print(f"Replacing {mkv_path.name} with updated version...")
        # Replace original file with updated one
        os.replace(temp_path, mkv_path)
        print(f"Updated metadata for {mkv_path.name}")

        # Display the updated metadata
        display_mkv_metadata(mkv_path)

        return True

    except subprocess.CalledProcessError as e:
        print(f"Error updating metadata for {mkv_path}: {e.stderr.decode()}")
        if temp_path.exists():
            temp_path.unlink()
        return False
    except Exception as e:
        print(f"Error updating metadata for {mkv_path}: {e}")
        if temp_path.exists():
            temp_path.unlink()
        return False

def process_mkv_files(input_dir, output_dir, max_duration=None):
    """
    Process all MKV files in a directory, extracting audio and transcribing.
    Saves transcripts to JSON files and updates MKV metadata.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Fetch episode data
    episodes = fetch_friends_episodes()
    if not episodes:
        print("Failed to fetch episode data. Please check your internet connection.")
        return {}

    results = {}

    for mkv_file in input_path.glob("*.mkv"):
        print(f"Processing {mkv_file.name}...")

        # Create temporary WAV file
        temp_wav = output_path / f"{mkv_file.stem}_temp.wav"

        # Extract audio
        if extract_audio_from_mkv(mkv_file, temp_wav, max_duration):
            # Transcribe audio
            transcript = transcribe_audio(temp_wav)

            if transcript:
                # Match transcript to episode
                matches = match_transcript_to_episode(transcript, episodes)
                if matches:
                    match_score = matches[0][1]
                    best_match = matches[0][0]
                    print(
                        f"\nBest match: S{best_match['season']:02d}E{best_match['episode']:02d} - {best_match['title']}"
                    )
                    print(f"Match score: {match_score}")

                    if match_score >= MATCH_THRESHOLD:
                        print(
                            f"Found match above threshold ({MATCH_THRESHOLD}), updating metadata..."
                        )
                        update_mkv_metadata(mkv_file, best_match)
                    else:
                        print(
                            f"Match score {match_score} is below threshold of {MATCH_THRESHOLD}. Skipping metadata update."
                        )
                        print(
                            f"You may need to process more audio (current: {max_duration}s) or check if this is the correct episode."
                        )
                else:
                    print("\nNo matches found for this transcript.")

                results[mkv_file.name] = {
                    "file_path": str(mkv_file),
                    "transcript": transcript,
                    "matched_episode": (
                        best_match
                        if matches and matches[0][1] >= MATCH_THRESHOLD
                        else None
                    ),
                    "match_score": match_score if matches else 0,
                }

            # Clean up temporary WAV file
            temp_wav.unlink()

    # Save results to JSON
    with open(output_path / "transcripts.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results

@app.command()
def main(
    input_dir: str = typer.Argument(..., help="Directory containing MKV files"),
    output_dir: str = typer.Argument(..., help="Directory to save transcripts"),
    max_duration: Optional[int] = typer.Option(
        90,  # Keep original 90 seconds requirement
        help="Maximum duration in seconds to transcribe from each file",
    ),
):
    """
    Process MKV files in the input directory, extract audio, generate transcripts,
    and update MKV metadata with episode information.
    Saves results to a JSON file in the output directory.
    """
    results = process_mkv_files(input_dir, output_dir, max_duration)
    print(f"Processed {len(results)} files.")

if __name__ == "__main__":
    app()
