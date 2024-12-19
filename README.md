# Friends Episode Processor

A tool to automatically identify, rename, and tag Friends TV show episodes. It can process videos from URLs (like YouTube) or local MKV files, using audio transcription to match against the Friends episode database.

## Features

- Complete episode processing pipeline:
  - Process videos from two sources:
    - Download from URLs (YouTube, etc.) using yt-dlp
    - Use existing local MKV files
  - Extract and transcribe audio (using Whisper)
  - Match against Friends episode database
  - Update metadata and rename files
- Saves transcripts alongside video files
- Shows complete OMDB episode data
- GPU-accelerated transcription when available
- Fuzzy text matching for reliable episode identification
- Configurable confidence thresholds and match limits
- Batch processing support for local files

## Requirements

- Python 3.10+
- ffmpeg
- yt-dlp (for downloading videos)
- CUDA-capable GPU (optional, for faster transcription)
  - ~256MB GPU memory for tiny model
  - ~925MB GPU memory for small model

## Getting an OMDB API Key

The script uses the OMDB API to fetch Friends episode data. To get your free API key:

1. Visit [OMDB API Key Registration](https://www.omdbapi.com/apikey.aspx)
2. Choose the FREE tier (1,000 daily limit)
3. Enter your email address
4. Click "Submit"
5. Check your email for the verification link
6. Click the verification link to activate your API key
7. Copy your API key and add it to the .env file:
   ```
   OMDB_API_KEY=your_api_key_here
   ```

Note: The FREE tier allows 1,000 requests per day, which is more than enough as the script caches episode data locally.

## Installation

1. Clone the repository:
```bash
git clone https://github.com/zetan503/frid.git
cd frid
```

2. Install dependencies:
```bash
# Install system requirements
sudo apt install ffmpeg
pip install --user --upgrade yt-dlp

# Install Python packages
pip install --user -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your OMDB API key
```

## Fabric Setup (Ubuntu)

1. Install Go from backports:
```bash
# Add the repository
sudo add-apt-repository ppa:longsleep/golang-backports

# Update package list
sudo apt update

# Install Go
sudo apt install golang-go
```

2. Install Fabric:
```bash
go install github.com/danielmiessler/fabric@latest
```

3. Update PATH to include Go binaries:
```bash
# Add to your ~/.bashrc or ~/.zshrc
export PATH=$GOPATH/bin:$GOROOT/bin:$HOME/.local/bin:$PATH
```

4. Reload your shell configuration:
```bash
source ~/.bashrc  # or source ~/.zshrc if using zsh
```

## Usage

The script provides three main approaches for processing episodes:

### 1. Process from URL (YouTube, etc.)

Download and process a video from a URL:

```bash
python3 process_episode.py from-url "VIDEO_URL" output/
```

This will:
1. Download the video's audio (optimized for transcription)
2. Extract and transcribe the audio
3. Match against episode database
4. Update metadata and rename file
5. Save transcript alongside video

Example:
```bash
# Process a YouTube video of a Friends episode
python3 process_episode.py from-url "https://youtube.com/watch?v=..." output/
```

### 2. Process Local Files

#### Single File
Process an existing MKV file:

```bash
python3 process_episode.py from-file episode.mkv
```

This will:
1. Extract and transcribe audio
2. Match against episode database
3. Update metadata and rename file
4. Save transcript alongside video

Example:
```bash
# Process a single local MKV file
python3 process_episode.py from-file "Friends.S01E01.mkv"
```

#### Batch Directory
Process all MKV files in a directory:

```bash
python3 process_episode.py batch input_dir/
```

This will process each MKV file in the directory, updating metadata and renaming files that match episodes.

Example:
```bash
# Process all MKV files in the input directory
python3 process_episode.py batch input/
```

### Common Options

All commands support these options:
- `--min-score`: Minimum confidence score for matching (default: 60)
- `--max-duration`: Seconds of audio to transcribe (default: 90)
- `--template`: Filename template (default: "{series}.S{season}E{episode}.{title}")

Example with options:
```bash
# Process with custom settings
python3 process_episode.py from-url "VIDEO_URL" output/ --min-score 55 --max-duration 120

# Process local file with custom template
python3 process_episode.py from-file episode.mkv --template "Friends.{season}x{episode}.{title}"
```

## Output

For each processed episode, you'll see:

1. OMDB Episode Data:
   - Title, Plot, Runtime
   - Air date, Ratings
   - Director, Writer, Actors
   - All other OMDB metadata

2. MKV Metadata:
   - Episode title and ID
   - Season and episode numbers
   - Show name
   - Description

3. Generated Files:
   - Renamed MKV file with episode information
   - Text file containing the transcript
   - Both files use the same naming template

Example output:
```
OMDB Episode Data:
--------------------------------------------------
Title: The One with Monica and Chandler's Wedding: Part 2
Year: 2001
Rated: TV-PG
Released: 17 May 2001
Season: 7
Episode: 24
Runtime: 22 min
Genre: Comedy, Romance
Director: Kevin Bright
Writer: David Crane, Marta Kauffman, Patty Lin
Actors: Jennifer Aniston, Courteney Cox, Lisa Kudrow
Plot: Ross tries to find Chandler with Phoebe's help...
...

MKV Metadata:
--------------------------------------------------
title: Friends - S07E24 - The One with Monica and Chandler's Wedding: Part 2
show: Friends
season_number: 7
episode_sort: 24
episode_id: S07E24
description: Ross tries to find Chandler with Phoebe's help...
--------------------------------------------------

Generated Files:
Friends.S07E24.The.One.with.Monica.and.Chandlers.Wedding.Part.2.mkv
Friends.S07E24.The.One.with.Monica.and.Chandlers.Wedding.Part.2.txt
```

## How It Works

1. **Video Processing**:
   - For URLs: Downloads audio using yt-dlp (optimized for transcription)
   - For local files: Uses existing MKV files
   - Extracts first N seconds of audio (default: 90s)

2. **Audio Transcription**:
   - Uses OpenAI's Whisper model
   - GPU acceleration when available
   - Optimized for TV show dialogue

3. **Episode Matching**:
   - Fetches episode data from OMDB API
   - Uses fuzzy text matching to find best episode match
   - Requires minimum confidence score (default: 60%)

4. **File Processing**:
   - Updates MKV metadata with episode information
   - Renames file using standardized format
   - Saves transcript to accompanying text file
   - Preserves original if no confident match found

## Episode Data Caching

The system caches Friends episode data from OMDB locally to improve performance:

- First run fetches all episode data from OMDB API
- Data is cached in `friends_episodes_cache.json`
- Cache expires after 30 days to ensure data freshness
- Subsequent runs use cached data unless expired

## Notes

- Whisper is a general-purpose speech recognition model trained on diverse audio data
- The script uses Whisper's "tiny" model by default:
  - Fast processing
  - ~256MB GPU memory
  - Good accuracy for TV show dialogue
- Default confidence threshold is 60%
- Original filenames are preserved if no confident match is found
- Transcripts are saved for verification and debugging

## License

[Your License Here]
