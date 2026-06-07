#!/usr/bin/env python3
"""
video_denoise.py — Remove noise from a video using reference noise audio files.

Directory structure:
    video_denoise_app/
    ├── input/    Place exactly one input video file here
    ├── noise/    Place one or more noise reference files here (all are combined)
    └── output/   Denoised video is saved here

Usage:
    python video_denoise.py <output_filename> [options]

Arguments:
    output_filename   File name for the output video (saved in output/)

Options:
    --prop-decrease FLOAT   Strength of noise reduction 0.0–1.0 (default: 1.0)
    --n-fft INT             FFT window size (default: 2048)
    --hop-length INT        Hop length for STFT (default: 512)
    --chunk-seconds FLOAT   Process audio in chunks to limit memory (default: 60)

Examples:
    python video_denoise.py result.mp4
    python video_denoise.py result.mp4 --prop-decrease 0.8
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import noisereduce as nr


def find_ffmpeg() -> str:
    """Return the path to ffmpeg, searching common Homebrew locations."""
    cmd = shutil.which("ffmpeg")
    if cmd:
        return cmd
    for candidate in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        if Path(candidate).exists():
            return candidate
    print("Error: ffmpeg not found. Install with: brew install ffmpeg", file=sys.stderr)
    sys.exit(1)


FFMPEG = find_ffmpeg()


def extract_audio(video_path: Path, audio_path: Path, sample_rate: int = 44100) -> int:
    """Extract audio from video using ffmpeg. Returns the actual sample rate."""
    cmd = [
        FFMPEG, "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_f32le",
        "-ar", str(sample_rate),
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return sample_rate


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return data, sr


def reduce_noise_chunked(
    audio: np.ndarray,
    noise_profile: np.ndarray,
    sr: int,
    prop_decrease: float,
    n_fft: int,
    hop_length: int,
    chunk_seconds: float,
) -> np.ndarray:
    """Apply noise reduction channel-by-channel in chunks to manage memory."""
    n_channels = audio.shape[1]
    chunk_samples = int(chunk_seconds * sr)
    output = np.zeros_like(audio)

    for ch in range(n_channels):
        ch_audio = audio[:, ch]
        ch_noise = noise_profile[:, ch] if noise_profile.shape[1] > ch else noise_profile[:, 0]
        ch_out = np.zeros_like(ch_audio)

        for start in range(0, len(ch_audio), chunk_samples):
            end = min(start + chunk_samples, len(ch_audio))
            chunk = ch_audio[start:end]
            reduced = nr.reduce_noise(
                y=chunk,
                y_noise=ch_noise,
                sr=sr,
                prop_decrease=prop_decrease,
                n_fft=n_fft,
                hop_length=hop_length,
                stationary=False,
            )
            ch_out[start:end] = reduced
            progress = end / len(ch_audio) * 100
            print(f"  Channel {ch + 1}/{n_channels}: {progress:.0f}%", end="\r")

        output[:, ch] = ch_out
        print()

    return output


def merge_audio_into_video(video_path: Path, audio_path: Path, output_path: Path) -> None:
    cmd = [
        FFMPEG, "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)


SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wav", ".mp3", ".flac", ".aac", ".m4a"}


def find_single_file(directory: Path, label: str) -> Path:
    files = sorted(f for f in directory.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS)
    if len(files) == 0:
        print(f"Error: No supported file found in {directory}/", file=sys.stderr)
        sys.exit(1)
    if len(files) > 1:
        names = ", ".join(f.name for f in files)
        print(f"Error: Multiple files found in {directory}/: {names}", file=sys.stderr)
        print(f"  Place exactly one {label} file in {directory}/", file=sys.stderr)
        sys.exit(1)
    return files[0]


def find_noise_files(directory: Path) -> list[Path]:
    files = sorted(f for f in directory.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS)
    if len(files) == 0:
        print(f"Error: No supported file found in {directory}/", file=sys.stderr)
        sys.exit(1)
    return files


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def load_and_merge_noise(noise_files: list[Path], target_sr: int, n_channels: int) -> np.ndarray:
    """Load multiple noise files, resample to target_sr, and concatenate into one profile.
    Video files (.mov, .mp4, etc.) are first decoded to WAV via ffmpeg."""
    import librosa

    segments = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, path in enumerate(noise_files):
            # Video files need audio extraction via ffmpeg first
            if path.suffix.lower() in VIDEO_EXTENSIONS:
                wav_path = Path(tmpdir) / f"noise_{i}.wav"
                cmd = [
                    FFMPEG, "-y",
                    "-i", str(path),
                    "-vn",
                    "-acodec", "pcm_f32le",
                    "-ar", str(target_sr),
                    str(wav_path),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"ffmpeg error on noise file {path.name}:\n{result.stderr}", file=sys.stderr)
                    sys.exit(1)
                data, file_sr = sf.read(str(wav_path), dtype="float32", always_2d=True)
            else:
                data, file_sr = sf.read(str(path), dtype="float32", always_2d=True)

            if file_sr != target_sr:
                data = np.stack([
                    librosa.resample(data[:, ch], orig_sr=file_sr, target_sr=target_sr)
                    for ch in range(data.shape[1])
                ], axis=1)

            # Match channel count
            if data.shape[1] < n_channels:
                data = np.tile(data, (1, n_channels // data.shape[1] + 1))
                data = data[:, :n_channels]
            elif data.shape[1] > n_channels:
                data = data[:, :n_channels]

            segments.append(data)

    return np.concatenate(segments, axis=0)


def main() -> None:
    base_dir = Path(__file__).parent
    input_dir = base_dir / "input"
    noise_dir = base_dir / "noise"
    output_dir = base_dir / "output"
    output_dir.mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(
        description="Remove noise from video using files in input/ and noise/ subdirectories."
    )
    parser.add_argument("output_filename", help="Output file name (saved in output/)")
    parser.add_argument("--prop-decrease", type=float, default=1.0,
                        help="Noise reduction strength 0.0–1.0 (default: 1.0)")
    parser.add_argument("--n-fft", type=int, default=2048)
    parser.add_argument("--hop-length", type=int, default=512)
    parser.add_argument("--chunk-seconds", type=float, default=60.0,
                        help="Process audio in N-second chunks (default: 60)")
    args = parser.parse_args()

    input_video = find_single_file(input_dir, "input video")
    noise_files = find_noise_files(noise_dir)
    output_video = output_dir / args.output_filename

    print(f"Input video    : {input_video}")
    print(f"Noise files    : {', '.join(f.name for f in noise_files)}")
    print(f"Output         : {output_video}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        raw_audio = tmp / "raw_audio.wav"
        clean_audio = tmp / "clean_audio.wav"

        print("Step 1/4: Extracting audio from video...")
        sr = extract_audio(input_video, raw_audio)

        print("Step 2/4: Loading audio and noise references...")
        video_audio, sr = load_audio(raw_audio)
        n_channels = video_audio.shape[1]

        print(f"  Merging {len(noise_files)} noise file(s)...")
        noise_audio = load_and_merge_noise(noise_files, target_sr=sr, n_channels=n_channels)

        print("Step 3/4: Applying noise reduction...")
        clean = reduce_noise_chunked(
            audio=video_audio,
            noise_profile=noise_audio,
            sr=sr,
            prop_decrease=args.prop_decrease,
            n_fft=args.n_fft,
            hop_length=args.hop_length,
            chunk_seconds=args.chunk_seconds,
        )


        sf.write(str(clean_audio), clean, sr, subtype="FLOAT")

        print("Step 4/4: Merging clean audio back into video...")
        merge_audio_into_video(input_video, clean_audio, output_video)

    print(f"\nDone! Output saved to: {output_video}")


if __name__ == "__main__":
    main()
