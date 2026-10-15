# Audio & Subtitle Removal Tool (ASRT)

<p align="center">
  <b>A desktop workstation in Python for lossless audio and subtitle track removal, stream inspection, and multi-version batch remuxing.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.x-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.x">
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=flat&logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/GUI-Tkinter-blueviolet" alt="Tkinter">
  <img src="https://img.shields.io/badge/Multimedia-FFmpeg-007808?style=flat&logo=ffmpeg&logoColor=white" alt="FFmpeg">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat" alt="MIT License">
</p>

---

## Overview

Managing media collections with extraneous audio tracks or foreign subtitle streams often requires stripping unwanted streams without compromising video fidelity or wasting time on unnecessary video re-encoding passes.

**Audio & Subtitle Removal Tool (ASRT)** is a desktop application engineered in Python and Tkinter for lightning-fast, lossless stream demuxing and remuxing. Built on top of FFmpeg and FFprobe, ASRT allows users to inspect embedded audio/subtitle tracks and selectively discard or re-order streams while copying the original video stream (`-c:v copy`) at raw disk I/O speeds.

ASRT served as one of the two foundational predecessor projects that were later unified into **Video Processing Tool (VPT)** and ultimately evolved into **Video Workstation (VW)**.

---

## Key Features

- **Lossless Stream Multiplexing:** Strips unwanted audio and subtitle streams without touching the video bitstream, preserving 100% of original visual quality at maximum disk speed.
- **Multi-Version Combination Remuxing:** Configure and generate multiple track combinations from a single source file in one batch pass.
- **Deep Stream Analysis:** Displays complete stream metadata including language codes, audio channels, bitrates, sample rates, and subtitle codecs.
- **Batch Condition Verification:** Scans folders and series collections to verify track consistency, missing languages, and stream alignments across episodes.
- **Batch Queue Management:** Process single files or recursive directory structures with a unified configuration applied across matching files.
- **Persistent Preferences:** Automatically saves user configurations and FFmpeg paths in `%APPDATA%/Galleon/ASRT`.

---

## Architecture & Engineering Highlights

- **Non-Blocking Multithreaded GUI:** Asynchronous execution model ensures smooth UI responsiveness during FFprobe stream inspection and batch operations.
- **Smart Stream Mapping:** Constructs optimized FFmpeg `-map` parameters dynamically based on user track selections.
- **Long Path Support:** Formatted for Windows UNC extended path handling (`\\?\`) to reliably support deeply nested directory hierarchies (>260 characters).

---

## Project Structure

```text
audioselector/
├── audiosubs.py                    # Standalone application entry point and GUI (Tkinter)
├── README.md                       # Project documentation
└── .git/                           # Git repository
```

---

## Installation & Setup

### Prerequisites

- **Operating System:** Windows 10 / 11 (64-bit).
- **Python:** Version 3.x with Tkinter.
- **FFmpeg & FFprobe:** Required for media analysis and remuxing. Automatically detected in `%APPDATA%/Galleon/bin` or system `PATH`.

### Quick Start

1. Clone or open the repository:
   ```bash
   cd audioselector
   ```

2. Launch the application:
   ```bash
   python audiosubs.py
   ```

---

## Configuration

User preferences and runtime configurations are automatically persisted at `%APPDATA%/Galleon/ASRT`:

- **Binary paths:** Discovery and configuration for `ffmpeg.exe` and `ffprobe.exe`.
- **Processing parameters:** Default output directory, recursive folder scanning, and original file backup toggle.

---

## Author

Project designed and developed by:

<table align="center">
  <tr>
    <td align="center" width="260px">
      <a href="https://github.com/TheHexenjagd">
        <img src="https://github.com/TheHexenjagd.png" width="110px;" alt="Gabriel Giraldo Herrera"/><br />
        <sub><b>Gabriel Giraldo Herrera</b></sub>
      </a><br />
      <a href="https://github.com/TheHexenjagd"><code>@TheHexenjagd</code></a><br />
      <small>Creator & Lead Developer</small>
    </td>
  </tr>
</table>

---

## License

This project is licensed under the **MIT License**.
