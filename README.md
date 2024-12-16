# MKV Transcribe and Episode Identifier

A tool to transcribe MKV video files, identify Friends TV show episodes based on their content, and automatically rename files to match the correct episode.

## Features

- Extract and transcribe audio from MKV files using Whisper (GPU-accelerated when available)
- Choice of Whisper models (tiny or small) for different accuracy/performance tradeoffs
- Identify Friends episodes using OMDB API with local caching
- Automatically rename files to standardized format (e.g., "Friends.S07E09.The.One.with.All.the.Candy.mkv")
- Fuzzy text matching for reliable episode identification
- Configurable confidence thresholds and match limits

## Requirements

- Python 3.10+
- ffmpeg
- CUDA-capable GPU (optional, for faster transcription)
  - ~256MB GPU memory for tiny model
  - ~925MB GPU memory for small model
- yt-dlp (optional, for downloading sample episodes)

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

## Quick Start Demo

A demo script is provided to show the complete workflow:

```bash
# Clone the repository
git clone https://github.com/zetan503/frid.git
cd frid

# Set up environment
cp .env.example .env
# Edit .env and add your OMDB API key

# Run the demo
./demo.sh
```

The demo will:
1. Download a sample Friends episode clip
2. Convert it to MKV format
3. Run the episode detection
4. Automatically rename the file based on the identified episode

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

# Install Python packages
pip install --user -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your OMDB API key
```

## Usage

### Batch Rename Friends Episodes

The fastest way to organize your Friends collection is using the `rename_episodes.py` script:

```bash
python3 rename_episodes.py /path/to/your/mkv/files
```

This will:
1. Transcribe the first 90 seconds of each MKV file (using GPU if available)
2. Match the transcript against Friends episode data from OMDB
3. Rename files to the format: `Friends.S##E##.Episode.Title.mkv`

Options:
- `--min-score`: Minimum confidence score required to rename (default: 55)
- `--max-duration`: Seconds of audio to transcribe for matching (default: 90)

Example with options:
```bash
python3 rename_episodes.py /path/to/your/mkv/files --min-score 55 --max-duration 120
```

### Individual Components

If you want to run the transcription or identification steps separately:

#### 1. Transcribe MKV Files

```bash
# Create input and output directories
mkdir -p input output

# Place your MKV files in the input directory
# Then run the transcription
python3 transcribe.py input output
```

Model Selection:
The script uses Whisper's "tiny" model by default, which provides good accuracy with lower resource usage. For higher accuracy at the cost of increased GPU memory and processing time, you can modify the script to use the "small" model:

- tiny model: Faster processing, ~256MB GPU memory, typical match scores 58-60
- small model: Better accuracy, ~925MB GPU memory, typical match scores 60-65

Optional: Download a sample episode using yt-dlp:
```bash
# Install yt-dlp if needed
pip install --user --upgrade yt-dlp

# Download and convert to MKV
python3 -m yt_dlp -f 'bestaudio[ext=m4a]' "YOUR_VIDEO_URL" -o "audio.m4a"
ffmpeg -i audio.m4a -c copy sample_episode.mkv
mv sample_episode.mkv input/
rm audio.m4a
```

### 2. Identify Episodes

The `identify_episode.py` script matches transcripts against Friends episode data:

```bash
python3 identify_episode.py output/transcripts.json
```

Options:
- `--min-score`: Minimum confidence score (default: 55)
- `--top-n`: Number of top matches to display (default: 3)

Example with options:
```bash
python3 identify_episode.py output/transcripts.json --min-score 55 --top-n 5
```

## How It Works

1. **Transcription (`transcribe.py`)**:
   - Extracts audio from MKV files using ffmpeg
   - Transcribes audio using OpenAI's Whisper model (choice of tiny or small)
   - Uses GPU acceleration when available
   - Saves transcripts to JSON in the output directory

2. **Episode Identification (`identify_episode.py`)**:
   - Loads transcripts from JSON
   - Fetches episode data from OMDB API
   - Caches episode data locally for 30 days
   - Uses fuzzy text matching to find best episode matches
   - Displays results with confidence scores

3. **Batch Renaming (`rename_episodes.py`)**:
   - Combines transcription and identification
   - Only renames files when match confidence exceeds threshold (default: 55)
   - Uses standardized naming format for consistency
   - Creates temporary files that are cleaned up after processing

## Episode Data Caching

The system caches Friends episode data from OMDB locally to improve performance:

- First run fetches all episode data from OMDB API
- Data is cached in `friends_episodes_cache.json`
- Cache expires after 30 days to ensure data freshness
- Subsequent runs use cached data unless expired

## Notes

- Whisper is a general-purpose speech recognition model trained on diverse audio data
- Two model options available:
  - tiny: Fast, efficient, good accuracy (58-60 match scores)
  - small: Higher accuracy, more resources (60-65 match scores)
- GPU acceleration is used automatically when available for faster transcription
- The episode identification uses fuzzy text matching to handle variations in transcription
- Default confidence threshold is 55% (lowered from 60% after testing)
- Original filenames are preserved if no confident match is found

## License

[Your License Here]
