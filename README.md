# Video Workstation (VW)

<p align="center">
  <b>A desktop workstation in Python for batch video multiplexing, hardware-accelerated subtitle hardcoding, and comprehensive media metadata management.</b>
</p>

<p align="center">
  <b>English</b> | <a href="README.es.md">Español</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=flat&logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/GUI-Tkinter-blueviolet" alt="Tkinter">
  <img src="https://img.shields.io/badge/Multimedia-FFmpeg-007808?style=flat&logo=ffmpeg&logoColor=white" alt="FFmpeg">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat" alt="MIT License">
</p>

---

## Overview

Batch post-processing of media collections traditionally requires either complex command-line scripts or heavy, multi-layered video editors that consume excessive system resources and risk unintended transcoding passes.

**Video Workstation (VW)** is a high-performance desktop application engineered in Python and Tkinter designed to optimize and accelerate batch video post-processing workflows. It centralizes lossless stream multiplexing (remuxing), GPU-accelerated subtitle hardcoding, batch tag and metadata sanitization, regex-driven bulk file renaming, and media property-driven dynamic directory structuring into a clean, zero-dependency control center.

Built with an emphasis on performance, data integrity, and operator ergonomics, VW provides an intuitive desktop interface over FFmpeg and FFprobe without requiring third-party runtime package installations.

---

## Key Features

- **Lossless Multiplexing (Remux) & Version Selector:** Extracts and reassembles multiple audio and subtitle tracks without re-encoding the original video stream, preserving 100% of the visual fidelity at raw disk I/O speeds.
- **Hardware-Accelerated Subtitle Hardcoding (GPU Hardcode):** Deep integration with GPU hardware encoding pipelines (NVIDIA NVENC, Intel Quick Sync, and AMD AMF) and hardware-assisted decoding (D3D11VA, DXVA2) to burn subtitles at maximum rendering speeds.
- **In-Place Metadata Sanitization & Maintenance:** Comprehensive batch stripping of encoder tags, release group metadata, and title markers across internal streams (`-map_metadata -1`), alongside fast container-level subtitle track removal (`-sn`) with zero video or audio re-compression.
- **Regex Batch File Renamer:** Token-based rename builder with dynamic variables (`{name}`, `{num}`), configurable numeric padding, and an advanced regex engine to sanitize complex release patterns in media libraries.
- **Dynamic Output Path Constructor:** Automated organization into hierarchical subfolders based on technical media attributes inspected via FFprobe (`{resolution}`, `{codec_v}`, `{codec_a}`, `{audio_langs}`, `{sub_langs}`, `{folder}`, `{name}`).
- **Smart Binary Resolver:** Cascading automatic detection of `ffmpeg.exe` and `ffprobe.exe` across local `tools/` (100% portable mode), `%APPDATA%/VideoWorkstation/tools/`, or system environment `PATH`.
- **Zero External Runtime Dependencies:** Operates strictly on Python's Standard Library (`tkinter`, `subprocess`, `threading`, `queue`, `json`, `configparser`, `pathlib`).

---

## Architecture & Engineering Highlights

- **Non-Blocking Multithreaded UI:** Stream container inspection and resource-intensive FFmpeg encoding tasks run on background worker threads (`threading.Thread`), communicating with the main Tkinter UI event loop through thread-safe queues (`queue.Queue`) to guarantee a fluid, responsive 60 FPS user experience.
- **Strict Subprocess Lifecycle & Instant Abort:** Employs managed `subprocess.Popen` pipelines with instant termination routines. Canceling an ongoing batch immediately halts child FFmpeg/FFprobe processes at the operating system level, instantly releasing GPU encoder sessions and CPU cores without leaving zombie processes or memory leaks.
- **Safe In-Place Atomic Operations:** Destructive modifications targeting source files adhere to an atomic transaction pattern: operations write to isolated temporary files, verify strict `exit code 0` completion, and only then perform an atomic replacement of the original file. Any failure aborts the pipeline and purges temporary files, leaving the source intact.
- **Dynamic Hardware Probing:** Detects host GPU encoder capabilities on application startup (`h264_nvenc`, `h264_qsv`, `h264_amf`) and dynamically adapts GUI controls and available options according to the system's hardware.
- **Decoupled Settings Persistence:** Centralized and atomic management of user configuration in an INI file (`vw_config.ini`) located in the user's application data directory.
- **Automated Standalone Packaging:** Includes a dedicated `dist/build.py` script and `dist/build.bat` that validate the environment, detect virtual environments (`venv`), bundle with PyInstaller, embed Windows version metadata, and output a standalone binary `VW_v1.0.0.exe`.

---

## Documentation

Comprehensive step-by-step guides for each module are available in both English and Spanish:

- **Multiplexing & Version Selector:** [English (docs/en/remux_selector.md)](docs/en/remux_selector.md) | [Español (docs/es/remux_selector.md)](docs/es/remux_selector.md)
- **GPU-Accelerated Hardcoding:** [English (docs/en/gpu_hardcode.md)](docs/en/gpu_hardcode.md) | [Español (docs/es/hardcode_gpu.md)](docs/es/hardcode_gpu.md)
- **Metadata Maintenance:** [English (docs/en/metadata_maintenance.md)](docs/en/metadata_maintenance.md) | [Español (docs/es/mantenimiento_metadata.md)](docs/es/mantenimiento_metadata.md)
- **Batch Renamer:** [English (docs/en/batch_renamer.md)](docs/en/batch_renamer.md) | [Español (docs/es/renombrador.md)](docs/es/renombrador.md)
- **Dynamic Output Paths:** [English (docs/en/dynamic_paths.md)](docs/en/dynamic_paths.md) | [Español (docs/es/rutas_dinamicas.md)](docs/es/rutas_dinamicas.md)

---

## Project Structure

```text
video_workstation/
├── dist/
│   ├── build.bat                   # Automated Windows executable builder
│   └── build.py                    # PyInstaller packaging and build script
├── docs/
│   ├── en/
│   │   ├── batch_renamer.md        # English guide: Regex batch renamer
│   │   ├── dynamic_paths.md        # English guide: Dynamic output paths
│   │   ├── gpu_hardcode.md         # English guide: GPU-accelerated hardcoding
│   │   ├── metadata_maintenance.md # English guide: In-place metadata maintenance
│   │   └── remux_selector.md       # English guide: Multiplexing and version selector
│   └── es/
│       ├── hardcode_gpu.md         # Spanish guide: GPU-accelerated hardcoding
│       ├── mantenimiento_metadata.md # Spanish guide: In-place metadata maintenance
│       ├── remux_selector.md       # Spanish guide: Multiplexing and version selector
│       ├── renombrador.md          # Spanish guide: Regex batch renamer
│       └── rutas_dinamicas.md      # Spanish guide: Dynamic output paths
├── tools/
│   └── README.txt                  # Directory and instructions for portable binaries
├── vw.py                           # Application entry point and desktop GUI (Tkinter)
├── LICENSE                         # MIT License terms
├── README.md                       # Main documentation (English)
└── README.es.md                    # Documentation in Spanish
```

---

## Installation & Setup

### Prerequisites

- **Operating System:** Windows 10 / 11 (64-bit).
- **Python:** Version 3.12 or higher.
- **FFmpeg & FFprobe:** Required for stream inspection and processing. Can be provided in three ways:
  1. **Portable Mode (Recommended):** Download and place `ffmpeg.exe` and `ffprobe.exe` into the local `tools/` folder.
  2. **User Directory:** Located at `%APPDATA%/VideoWorkstation/tools/`.
  3. **System PATH:** Automatically detected if installed globally in Windows.

### Quick Start (Running from Source)

1. Clone the repository:
   ```bash
   git clone https://github.com/TheHexenjagd/VW.git
   cd VW
   ```

2. (Optional) Place `ffmpeg.exe` and `ffprobe.exe` inside the `tools/` directory.

3. Launch the application:
   ```bash
   python vw.py
   ```

---

## Standalone Windows Executable (.exe)

The project includes an automated builder to compile a completely portable binary with zero external runtime dependencies (no Python installation required on the target machine):

- Double-click `dist/build.bat` or run from your terminal:
  ```bash
  python dist/build.py
  ```

The builder will verify compilation tools, auto-detect any local `venv`, embed Windows version metadata, clean temporary build caches, and output `dist/VW_v1.0.0.exe`.

---

## Configuration

User preferences and runtime configurations are automatically persisted at `%APPDATA%/VideoWorkstation/vw_config.ini`:

- **Binary paths:** Discovery and explicit paths for `ffmpeg.exe` and `ffprobe.exe`.
- **Hardware acceleration:** Preferred GPU encoder (`nvidia`, `intel`, `amd`) and hardware decoder framework (`Software`, `d3d11va`, `dxva2`).
- **Processing parameters:** Dynamic output folder rules, language suffix tags, recursive scanning, and quality presets.

---

## Authors & Development Team

Project developed and maintained by:

<table align="center">
  <tr>
    <td align="center" width="260px">
      <a href="https://github.com/TheHexenjagd">
        <img src="https://github.com/TheHexenjagd.png" width="110px;" alt="Gabriel Giraldo Herrera"/><br />
        <sub><b>Gabriel Giraldo Herrera</b></sub>
      </a><br />
      <a href="https://github.com/TheHexenjagd"><code>@TheHexenjagd</code></a><br />
      <small>Co-Creator & Developer</small>
    </td>
    <td align="center" width="260px">
      <a href="https://github.com/Gatozo">
        <img src="https://github.com/Gatozo.png" width="110px;" alt="Jorge Iván Nieto Triviño"/><br />
        <sub><b>Jorge Iván Nieto Triviño</b></sub>
      </a><br />
      <a href="https://github.com/Gatozo"><code>@Gatozo</code></a><br />
      <small>Co-Creator & Developer</small>
    </td>
  </tr>
</table>

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
