# Chevelle

> **The Muscle Car of CD Burning.**

A high-performance TUI (Terminal User Interface) for mastering and burning Audio CDs on Linux. **Chevelle** abstracts the complexity of `ffmpeg` and `wodim` into a modern, robust, and navigable visual dashboard.

## What It Does

* **Modern Visual Dashboard:** Rich terminal interface built with [Textual](https://textual.textualize.io/), featuring full mouse support.
* **Smart Mastering:** Automatically calculates track durations and splits large collections across multiple discs (CD 1, CD 2...) respecting the 80-minute limit.
* **Gapless Mode:** Defaults to *Disk-At-Once* (DAO) to ensure continuous audio playback without artificial 2-second gaps.
* **Linux Native:** Optimized for direct operation with local optical drives (`/dev/sr0`).

## Installation & Usage

### 1. System Requirements

Chevelle relies on system tools for audio processing and burning. On Debian/Ubuntu-based distributions, you can install them via:
```bash
sudo apt update
sudo apt install ffmpeg wodim
```

### 2. Python Environment

It is highly recommended to run the app inside a Python virtual environment to avoid conflicts:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Running the App

With the virtual environment active, navigate to the `src` directory and execute the module:
```bash
cd src
python -m chevelle
```

## License
This project is licensed under the GPL-3.0 License - see the [LICENSE](LICENSE)  file for details.

