# yt-frame-burst

A Python command-line tool to download a YouTube video **once** and grab a burst of high-resolution frames starting at a given timestamp.

Perfect for extracting stills for analysis, reference, or creative work.

---

## Features
- Accepts YouTube URLs directly.
- Flexible timestamp parsing (`00:03:00`, `3:00`, `180`, `3m0s`, `9.40`, etc.).
- Automatically detects start time from `?t=` in URLs if no `--start` is provided.
- Burst mode: capture multiple frames a fixed number of seconds apart.
- Downloads video **only once** (video-only stream for speed), then extracts frames locally.
- Auto-names output folder from the YouTube title (sanitized), or you can specify `--outdir`.
- Requires only Python, `yt-dlp`, and `ffmpeg`.

---

## Installation

### 1. Clone the repo
```bash
git clone https://github.com/YOURUSERNAME/yt-frame-burst.git
cd yt-frame-burst
```

### 2. Install Python dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt`:
```
yt-dlp>=2025.1.15
```

### 3. Install ffmpeg
- **macOS**:  
  ```bash
  brew install ffmpeg
  ```
- **Ubuntu/Debian**:  
  ```bash
  sudo apt-get install ffmpeg
  ```
- **Windows**:  
  [Download from ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

---

## Usage

### Basic burst extraction
Grab 10 frames, 0.1s apart, starting at 9:40:
```bash
python3 grab_burst.py \
  --url "https://www.youtube.com/watch?v=oZOGrNVrd78" \
  --start "00:09:40"
```

### Override output directory
```bash
python3 grab_burst.py \
  --url "https://www.youtube.com/watch?v=EbkUkpWq_pM&t=8s" \
  --start "3:00" \
  --outdir "El_corazón_delator"
```

### Use `t=` from the URL automatically
```bash
python3 grab_burst.py --url "https://www.youtube.com/watch?v=JEbi_PapBsY&t=39s"
```

---

## Output
Frames will be saved in the chosen directory (or auto-named from the video title) with filenames like:
```
frame_00-09-40.png
frame_00-09-40.1.png
...
```

---

## Disclaimer
This tool uses [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) to download videos from YouTube.  
Downloading YouTube content may violate YouTube’s [Terms of Service](https://www.youtube.com/static?template=terms).  
**Use this tool only for personal, non-commercial purposes and only with content you have rights to download and extract.**  
The authors of this project are not responsible for misuse of the software.

---

## License
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
