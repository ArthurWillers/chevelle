# Chevelle

> **The Muscle Car of CD Burning.**

A high-performance TUI (Terminal User Interface) for mastering and burning Audio CDs on Linux. **Chevelle** abstracts the complexity of `ffmpeg` and `wodim` into a modern, robust, and navigable visual dashboard.

## What It Does

* **Modern Visual Dashboard:** Rich terminal interface built with [Textual](https://textual.textualize.io/), featuring full mouse support.
* **Smart Mastering:** Automatically calculates track durations and splits large collections across multiple discs (CD 1, CD 2...) respecting the 80-minute limit.
* **Gapless Mode:** Defaults to *Disk-At-Once* (DAO) to ensure continuous audio playback without artificial 2-second gaps.
* **Linux Native:** Optimized for direct operation with local optical drives (`/dev/sr0`).

## License

This project is free software licensed under the **GNU General Public License v3.0 (GPLv3)**.
