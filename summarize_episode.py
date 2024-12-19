#!/usr/bin/env python3
import sys
import os
import subprocess


def summarize_transcript(transcript_file):
    try:
        # Create a custom prompt that focuses on unique plot points
        custom_prompt = """
        Analyze this Friends episode transcript and create a concise summary that focuses on:
        1. The main plot points and events that make this episode unique
        2. Specific situations, conflicts, or problems that occur
        3. Key decisions or actions taken by characters
        4. Notable locations or settings
        5. Special occasions or events (holidays, celebrations, etc)

        Exclude generic elements like:
        - Common character interactions
        - Regular settings (apartments, coffee shop)
        - Running gags or recurring jokes

        Format the summary as a brief paragraph focusing only on the distinctive elements that would identify this specific episode.
        """

        # Use fabric CLI with custom prompt
        cmd = [
            "fabric",
            "-p",
            "custom",  # use custom preset for specific episode identification
            "-t",
            "0.0",  # temperature 0 for consistent output
            "--prompt",
            custom_prompt,
            "--readability",  # optimize for readability
            transcript_file,  # input file as positional argument
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error running fabric: {result.stderr}", file=sys.stderr)
            return None

        return result.stdout.strip()
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return None


def main():
    if len(sys.argv) != 2:
        print("Usage: python summarize_episode.py <transcript_file>")
        sys.exit(1)

    transcript_file = sys.argv[1]

    # Check if file exists
    if not os.path.isfile(transcript_file):
        print(f"Error: Could not find transcript file: {transcript_file}")
        sys.exit(1)

    # Generate summary
    summary = summarize_transcript(transcript_file)
    if summary:
        print("\nGenerated Summary:")
        print("-----------------")
        print(summary)


if __name__ == "__main__":
    main()
