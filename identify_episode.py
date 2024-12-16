#!/usr/bin/env python3

import json
import requests
import typer
from typing import Dict, List, Tuple
from pathlib import Path
from fuzzywuzzy import fuzz
from time import sleep
import os
from datetime import datetime, timedelta
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from concurrent.futures import ThreadPoolExecutor
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = typer.Typer()

# OMDb API settings
OMDB_API_KEY = os.getenv("OMDB_API_KEY")  # Load from environment variable
if not OMDB_API_KEY:
    raise ValueError("OMDB_API_KEY environment variable is not set")

FRIENDS_IMDB_ID = "tt0108778"  # Friends series IMDb ID
CACHE_FILE = "friends_episodes_cache.json"
CACHE_EXPIRY_DAYS = 30  # Refresh cache after 30 days

# Thread-safe progress bars
progress_lock = threading.Lock()
progress = None

def load_transcripts(transcript_path: str) -> Dict:
    """Load transcripts from JSON file"""
    with open(transcript_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def is_cache_valid() -> bool:
    """Check if cache exists and is not expired"""
    if not os.path.exists(CACHE_FILE):
        return False

    # Check cache age
    cache_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
    age = datetime.now() - cache_time
    return age.days < CACHE_EXPIRY_DAYS

def load_cached_episodes() -> List[Dict]:
    """Load episodes from cache file"""
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_episodes_cache(episodes: List[Dict]):
    """Save episodes to cache file"""
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(episodes, f, indent=2)

def fetch_episode_data(season: int, ep_data: Dict, task_id) -> Dict:
    """Fetch detailed episode data with progress tracking"""
    try:
        ep_url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&i={ep_data['imdbID']}"
        ep_response = requests.get(ep_url)
        ep_response.raise_for_status()
        ep_detail = ep_response.json()

        with progress_lock:
            progress.update(task_id, advance=1)

        return {
            "season": season,
            "episode": int(ep_data['Episode']),
            "title": ep_detail['Title'],
            "summary": ep_detail['Plot']
        }
    except requests.RequestException as e:
        print(f"Error fetching episode {ep_data['Episode']} of season {season}: {e}")
        return None

def fetch_friends_episodes() -> List[Dict]:
    """Fetch Friends episodes data from OMDb API or cache with progress bar"""
    global progress

    # Check cache first
    if is_cache_valid():
        print("Loading episodes from cache...")
        return load_cached_episodes()

    print("Fetching episodes from OMDB API...")
    episodes = []
    total_episodes = 0
    season_data_list = []

    # First pass: get all season data and count episodes
    for season in range(1, 11):
        try:
            url = f"http://www.omdbapi.com/?apikey={OMDB_API_KEY}&i={FRIENDS_IMDB_ID}&Season={season}"
            response = requests.get(url)
            response.raise_for_status()
            season_data = response.json()

            if 'Episodes' in season_data:
                total_episodes += len(season_data['Episodes'])
                season_data_list.append((season, season_data['Episodes']))

            sleep(0.1)  # Respect API rate limits
        except requests.RequestException as e:
            print(f"Error fetching season {season}: {e}")

    # Second pass: fetch episode details with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
    ) as progress:
        task_id = progress.add_task("Fetching episode details...", total=total_episodes)

        with ThreadPoolExecutor(max_workers=5) as executor:
            for season, eps in season_data_list:
                # Submit all episodes for parallel fetching
                future_to_ep = {
                    executor.submit(fetch_episode_data, season, ep, task_id): ep
                    for ep in eps
                }

                # Collect results as they complete
                for future in future_to_ep:
                    result = future.result()
                    if result:
                        episodes.append(result)
                    sleep(0.1)  # Respect API rate limits

    # Save to cache if we got episodes
    if episodes:
        print(f"Caching {len(episodes)} episodes...")
        save_episodes_cache(episodes)

    return episodes

def match_transcript_to_episode(transcript: str, episodes: List[Dict]) -> List[Tuple[Dict, int]]:
    """
    Match transcript against episode summaries using fuzzy text matching.
    Returns list of (episode, score) tuples sorted by match score.
    """
    matches = []
    for episode in episodes:
        # Calculate multiple similarity scores
        plot_score = fuzz.token_set_ratio(transcript.lower(), episode['summary'].lower())
        title_score = fuzz.token_set_ratio(transcript.lower(), episode['title'].lower())

        # Weight plot matches more heavily than title matches
        combined_score = (plot_score * 0.8) + (title_score * 0.2)
        matches.append((episode, int(combined_score)))

    # Sort by score in descending order
    return sorted(matches, key=lambda x: x[1], reverse=True)

def format_episode_info(episode: Dict, score: int) -> str:
    """Format episode information for display"""
    return (
        f"Season {episode['season']} Episode {episode['episode']}\n"
        f"Title: {episode['title']}\n"
        f"Match Score: {score}%\n"
        f"Summary: {episode['summary']}"
    )

@app.command()
def main(
    transcript_path: str = typer.Argument(..., help="Path to transcripts.json file"),
    top_n: int = typer.Option(3, help="Number of top matches to display"),
    min_score: int = typer.Option(50, help="Minimum match score percentage to display")
):
    """
    Identify Friends episodes based on transcript content.
    Displays top matching episodes with confidence scores.
    """
    # Load transcripts
    transcripts = load_transcripts(transcript_path)

    # Fetch episode data (from cache if available)
    episodes = fetch_friends_episodes()
    if not episodes:
        print("Failed to fetch episode data. Please check your internet connection.")
        return

    # Process each transcript with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%")
    ) as progress:
        task = progress.add_task("Processing transcripts...", total=len(transcripts))

        for filename, data in transcripts.items():
            progress.update(task, description=f"Processing {filename}")
            transcript = data['transcript']

            # Match transcript to episodes
            matches = match_transcript_to_episode(transcript, episodes)

            # Filter and display top matches
            filtered_matches = [(ep, score) for ep, score in matches if score >= min_score]
            if filtered_matches:
                print(f"\nResults for {filename}:")
                for episode, score in filtered_matches[:top_n]:
                    print("\n" + format_episode_info(episode, score))
                    print("-" * 50)
            else:
                print(f"\nNo matches found for {filename} with confidence score >= {min_score}%")

            progress.advance(task)

if __name__ == "__main__":
    app()
