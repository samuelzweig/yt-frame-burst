#!/usr/bin/env python3
"""
Grab a burst of frames from a YouTube video at highest available *video* resolution.

Features:
- Pass URL and start timestamp as arguments.
- Auto-detect timestamp from YouTube URLs with ?t= or &t= (e.g., t=8s, t=180).
- Flexible timestamp parsing: "3:00", "00:03:00", "180", "3m0s", "3 min 0 seconds", "9.40" => 9m40s.
- Burst controls: --count (frames) and --step (seconds between frames).
- Downloads the video *once* (video-only, no audio), then extracts frames locally.
- Output folder:
    * If --outdir is provided, use it.
    * Otherwise auto-name based on the YouTube title (sanitized for filesystem safety).

Requirements:
  - yt-dlp  (pip install -U yt-dlp)  or (brew install yt-dlp)
  - ffmpeg  (brew install ffmpeg) or your OS package manager

Examples:
  python3 grab_burst.py --url "https://www.youtube.com/watch?v=oZOGrNVrd78" --start "00:09:40"
  python3 grab_burst.py --url "https://www.youtube.com/watch?v=EbkUkpWq_pM&t=8s" --start "3:00" --count 10 --step 0.1
  # If --start is omitted, t= in the URL (if present) is used.
"""

import argparse
import math
import re
import shlex
import subprocess
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASENAME_DEFAULT = "frame_"

# ---------- shell helpers ----------
def run(cmd, check=True, capture=False):
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture,
    )

def ensure_tools():
    for tool in ("yt-dlp", "ffmpeg"):
        version_flag = "--version" if tool == "yt-dlp" else "-version"
        try:
            run([tool, version_flag])
        except FileNotFoundError:
            raise SystemExit(
                f"Error: '{tool}' not found on PATH.\n"
                "Install with Homebrew (macOS): brew install ffmpeg yt-dlp\n"
                "Or pip for yt-dlp: python3 -m pip install -U yt-dlp"
            )

# ---------- title & path helpers ----------
def sanitize_for_path(name: str) -> str:
    """Make a safe folder name: keep letters, numbers, _, -, . ; replace others with _"""
    cleaned = re.sub(r'[^A-Za-z0-9_\-\.]+', '_', name).strip('_')
    return cleaned or "video"

def get_video_title(url: str) -> str:
    """Fetch the video title without downloading media."""
    result = run(["yt-dlp", "--get-title", url], capture=True)
    title = (result.stdout or "").strip()
    return title or "video"

# ---------- time parsing ----------
_ts_hms = re.compile(r"^\s*(\d{1,2}:)?\d{1,2}:\d{1,2}(?:\.\d+)?\s*$")  # 3:00 or 00:03:00
_ts_ms  = re.compile(r"^\s*(\d+)\s*m(?:in)?\s*(\d+(?:\.\d+)?)\s*s(?:ec(?:onds?)?)?\s*$", re.IGNORECASE)  # 3m0s / 3 min 0 seconds
_ts_suff= re.compile(r"^\s*(\d+(?:\.\d+)?)\s*s\s*$", re.IGNORECASE)  # 180s
_ts_plain = re.compile(r"^\s*\d+(?:\.\d+)?\s*$")  # 180 / 180.5
_ts_dot_m_s = re.compile(r"^\s*(\d+)\.(\d{1,2})\s*$")  # 9.40 => 9m 40s

def hhmmss_to_seconds(ts: str) -> float:
    ts = ts.strip()
    if _ts_hms.match(ts):
        parts = ts.split(":")
        parts = [p.strip() for p in parts]
        if len(parts) == 3:
            h, m, s = parts
        else:
            h, m, s = "0", parts[0], parts[1]
        return int(h) * 3600 + int(m) * 60 + float(s)
    if _ts_ms.match(ts):
        m, s = _ts_ms.match(ts).groups()
        return int(m) * 60 + float(s)
    if _ts_suff.match(ts):
        return float(_ts_suff.match(ts).group(1))
    if _ts_plain.match(ts):
        return float(ts)
    if _ts_dot_m_s.match(ts):
        m, s = _ts_dot_m_s.match(ts).groups()
        return int(m) * 60 + float(s)
    raise ValueError(f"Unrecognized timestamp format: {ts}")

def seconds_to_hhmmss_ms(x: float) -> str:
    whole = int(math.floor(x))
    frac = x - whole
    h = whole // 3600
    m = (whole % 3600) // 60
    s = (whole % 60) + frac
    return f"{h:02d}:{m:02d}:{s:06.3f}".rstrip('0').rstrip('.')

def extract_t_from_url(url: str) -> float | None:
    """
    Supports ?t= and &t= in forms like 8, 8s, 3m0s, 180, 180s.
    If absent, returns None.
    """
    try:
        q = parse_qs(urlparse(url).query)
        tvals = q.get("t") or q.get("start")
        if not tvals:
            return None
        raw = tvals[0]
        # Handle "3m0s", "180s", "8s", "180"
        m = re.match(r"^\s*(?:(\d+)m)?(\d+(?:\.\d+)?)s?\s*$", raw, re.IGNORECASE)
        if m:
            mm, ss = m.groups()
            return (int(mm) * 60 if mm else 0) + float(ss)
        return float(raw)
    except Exception:
        return None

# ---------- core actions ----------
def download_video(url: str) -> Path:
    """
    Try best *video-only* first (fastest for stills). If that fails (e.g., HTTP 416),
    fall back to merged best video+audio. Adds a few retry niceties.
    """
    out_tmpl = "video.%(ext)s"

    def _run_download(args):
        cmd = [
            "yt-dlp",
            "--no-continue",          # avoid resuming a broken partial
            "--retries", "5",
            "--retry-sleep", "2",
            "--no-part",
            "-o", out_tmpl,
        ] + args + [url]
        print("Running:", " ".join(cmd))
        return run(cmd, check=True)

    # 1) Try best video-only
    try:
        print("Downloading highest-quality *video-only* stream…")
        _run_download(["-f", "bestvideo"])
    except subprocess.CalledProcessError as e:
        print("Video-only failed; falling back to merged best video+audio …")
        # 2) Fallback: merged bestvideo+bestaudio (most reliable)
        # Force mp4 container for ffmpeg friendliness
        _run_download(["-f", "bestvideo*+bestaudio/best", "--merge-output-format", "mp4"])

    # Find the resulting file
    candidates = sorted(Path(".").glob("video.*"))
    if not candidates:
        raise SystemExit("Download succeeded but no output file was found.")
    print(f"Downloaded to: {candidates[0].resolve()}")
    return candidates[0]
def grab_frame(input_file: Path, ts: str, out_file: Path):
    # -ss AFTER -i for accurate frame seek
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-nostdin",
        "-i", str(input_file),
        "-ss", ts,
        "-frames:v", "1",
        "-y",
        str(out_file),
    ]
    run(cmd)

# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(description="Grab a burst of frames from a YouTube video (video-only).")
    parser.add_argument("--url", required=True, help="YouTube URL (supports ?t=8s, &t=180, etc.)")
    parser.add_argument("--start", help="Start timestamp; e.g. '3:00', '00:03:00', '180', '3m0s', '9.40'")
    parser.add_argument("--count", type=int, default=10, help="Number of frames (default: 10)")
    parser.add_argument("--step", type=float, default=0.1, help="Seconds between frames (default: 0.1)")
    parser.add_argument("--outdir", help="Output directory (default: sanitized video title)")
    parser.add_argument("--prefix", default=BASENAME_DEFAULT, help=f"Filename prefix (default: {BASENAME_DEFAULT})")
    args = parser.parse_args()

    ensure_tools()

    # Resolve base time (seconds)
    if args.start:
        base_seconds = hhmmss_to_seconds(args.start)
    else:
        t_from_url = extract_t_from_url(args.url)
        base_seconds = t_from_url if t_from_url is not None else 0.0

    # Output directory
    if args.outdir:
        outdir = Path(args.outdir)
    else:
        title = sanitize_for_path(get_video_title(args.url))
        outdir = Path(title)
    outdir.mkdir(parents=True, exist_ok=True)

    video_file = download_video(args.url)

    # Generate timestamps
    increments = [i * args.step for i in range(args.count)]
    print(f"Extracting {args.count} frames starting at {seconds_to_hhmmss_ms(base_seconds)} …")

    # Extract frames
    for idx, inc in enumerate(increments, 1):
        ts = seconds_to_hhmmss_ms(base_seconds + inc)
        safe_ts = ts.replace(":", "-")
        out = outdir / f"{args.prefix}{safe_ts}.png"
        grab_frame(video_file, ts, out)
        print(f"[{idx}/{args.count}] Saved {out}")

    print(f"Done. Frames in: {outdir.resolve()}")

if __name__ == "__main__":
    main()
