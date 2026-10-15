# HardCode Subtitle Tool (HST)

<p align="center">
  <b>A desktop utility in Python for GPU-accelerated and CPU video subtitle burning, batch processing, and media metadata management.</b>
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

Embedding subtitles permanently into video streams (hardsubbing) is essential when targeting playback devices, hardware players, or web platforms lacking support for soft subtitle tracks or complex typography styling (ASS/SSA).

**HardCode Subtitle Tool (HST)** is a high-performance desktop application engineered in Python and Tkinter designed to automate and accelerate batch subtitle hardcoding. It provides a specialized control panel over FFmpeg with native hardware acceleration support for NVIDIA NVENC (`h264_nvenc`) and Intel QuickSync Video (`h264_qsv`), automated extraction of embedded subtitle streams, and batch container metadata stripping.

HST served as one of the two foundational predecessor projects that were later unified into **Video Processing Tool (VPT)** and ultimately evolved into **Video Workstation (VW)**.

---

## Key Features

- **Hardware-Accelerated Subtitle Burning:** High-efficiency video encoding powered by NVIDIA NVENC (`h264_nvenc`) and Intel Quick Sync (`h264_qsv`), with seamless automatic fallback to CPU (`libx264`).
- **Batch Processing Queue:** Queue multiple media files with recursive subfolder scanning and concurrent status monitoring.
- **Embedded Track Extraction:** Automatically extracts embedded subtitle streams (SRT, ASS) to temporary workspaces before executing the burning pipeline.
- **Quality & Performance Presets:** Dynamic preset configuration tailored to detected GPU vendor capabilities (performance, balanced, quality).
- **Metadata Sanitization:** In-place stripping of personal tags, track titles, and global container metadata without re-encoding video streams.
- **Persistent Preferences:** Automatically saves user configurations and FFmpeg paths in `%APPDATA%/Galleon/HST`.

---

## Architecture & Engineering Highlights

- **Multithreaded Processing Pipeline:** Dedicated background worker threads handle video probing and FFmpeg subprocess execution without freezing the Tkinter GUI.
- **Long Path Support:** Formatted for Windows UNC extended path handling (`\\?\`) to reliably support deeply nested directory hierarchies (>260 characters).
- **Dynamic GPU Probing:** Automatic discovery and validation of host GPU encoding capabilities at startup.

---

## Project Structure

```text
hardcodetool/
├── hardcode.py                     # Standalone application entry point and GUI (Tkinter)
├── README.md                       # Project documentation
└── .git/                           # Git repository
```

---

## Installation & Setup

### Prerequisites

- **Operating System:** Windows 10 / 11 (64-bit).
- **Python:** Version 3.x with Tkinter.
- **FFmpeg & FFprobe:** Required for media analysis and encoding. Automatically detected in `%APPDATA%/Galleon/bin` or system `PATH`.

### Quick Start

1. Clone or open the repository:
   ```bash
   cd hardcodetool
   ```

2. Launch the application:
   ```bash
   python hardcode.py
   ```

---

## Configuration

User preferences and runtime configurations are automatically persisted at `%APPDATA%/Galleon/HST`:

- **Binary paths:** Discovery and configuration for `ffmpeg.exe` and `ffprobe.exe`.
- **Hardware acceleration:** Preferred GPU encoder (`nvidia`, `intel`) and encoding quality presets.
- **Queue options:** Recursive folder scanning and output destination directory.

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
