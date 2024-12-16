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

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/mkv-transcribe.git
cd mkv-transcribe
```

2. Install dependencies:
```bash
# Install system requirements
sudo apt install ffmpeg

# Install Python packages
pip install --user -r requirements.txt
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
