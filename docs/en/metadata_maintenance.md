# In-Place Metadata Maintenance & Sanitization

<p align="right">
  <b>English</b> | <a href="../es/mantenimiento_metadata.md">Español</a>
</p>

The **Maintenance** module in Video Workstation (VW) provides high-speed utilities to clean and sanitize media files directly in the queue. Unlike re-encoding or multi-version multiplexing pipelines, these operations apply non-destructive, stream-level modifications directly inside the source container.

---

## 1. Metadata Sanitization (Tag Stripping)
Media containers (particularly `.mkv` and `.mp4`) frequently accumulate unnecessary metadata embedded during authoring: global file titles, ripper tags, conversion software banners, and encoder settings strings on every audio or video stream.

### How It Works
* **Exhaustive Tag Purge:** Strips global metadata tags and per-stream metadata (video, audio, and subtitle tracks) via atomic FFmpeg operations:
  ```bash
  ffmpeg -i "input.mkv" -map 0 -c copy -map_metadata -1 -map_metadata:s:v -1 -map_metadata:s:a -1 -map_metadata:s:s -1 "temp_output.mkv"
  ```
* **Zero Re-encoding:** Audio, video, and subtitle bitstreams are copied bit-for-bit (`-c copy`), completing operations at raw disk read/write bandwidth.
* **Pristine Output:** Strips private tags, tracking watermarks, and unnecessary encoder strings while preserving structural container health.

---

## 2. Subtitle Track Stripping
Useful when internal subtitle tracks are corrupt, misaligned, or cause incompatibility issues with hardware players.

### How It Works
* **Stream Discarding:** Remuxes the file retaining only audio and video tracks while explicitly omitting all subtitle tracks (`-sn` flag):
  ```bash
  ffmpeg -i "input.mkv" -map 0 -c copy -sn "temp_output.mkv"
  ```
* **Instant In-Place Execution:** Completed without video or audio transcoding.

---

## Atomic Transaction Safety Model
Because these maintenance routines target files loaded in the primary queue, VW enforces strict atomic transaction safeguards:

1. **Isolated Scratch Buffers:** VW never overwrites active input files directly. Operations write into temporary sibling files (`.tmp` with unique process identifiers) inside the target directory.
2. **Strict Exit Code Verification:** Only upon receiving a validated `exit code 0` from FFmpeg does VW replace the original file with the sanitized version.
3. **Graceful Fault Tolerance & Interruption Handling:**
   * Aborted or failed jobs instantly purge orphaned temporary files.
   * Original source files remain untouched.
   * Failed items are automatically moved to the **"Skipped / Errors"** tab accompanied by raw process error logs for debugging.
