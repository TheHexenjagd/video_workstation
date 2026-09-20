# Lossless Multiplexing (Remux) & Version Selector

<p align="right">
  <b>English</b> | <a href="../es/remux_selector.md">Español</a>
</p>

The **Multiplexing (Remux)** module in Video Workstation (VW) is designed to process multi-track audio and subtitle streams, enabling the creation of multiple container versions cleanly, rapidly, and without any re-encoding or loss of visual fidelity in the primary video stream.

---

## What is Remuxing?
Remultiplexing or **remuxing** is the process of extracting existing data bitstreams (video, audio, subtitles) from an input container (such as `.mkv` or `.mp4`) and repacking them into a new container with a tailored track selection.

* **100% Lossless:** Because video streams are copied directly (`-c:v copy`), image quality remains pixel-perfect identical to the master source.
* **Ultra-Fast Throughput:** Bypassing CPU/GPU video re-encoding means operations finish in seconds per file, limited only by your storage drive's read/write speed.

---

## Dynamic Stream & Version Selector by Subgroups
When initiating batch processing or clicking **"Configurar subgrupos"** ("Configure subgroups"), VW inspects all queued files via **FFprobe** and clusters them by their stream and language signature (Subgroup 1, Subgroup 2, etc.):

1. **100% Unattended Upfront Configuration:**
   * **Before launching FFmpeg:** All target tracks and versions for each unique subgroup in the queue are defined upfront. This allows FFmpeg to run seamlessly from first to last file without halting or stalling unattended execution.
   * **Available Stream Inspection:** Displays stream indices, codecs, titles, and language metadata (e.g., `Spanish (spa)`, `English (eng)`).
2. **Multi-Version Pipeline:**
   * Select the target audio and subtitle combinations.
   * Click **"Add additional version"** to queue a new combination. You can define multiple version targets per source file (e.g., Dual Audio + Subtitles, LatAm Spanish only, English Only).
   * **Apply to Subgroup:** Each configured combination applies to all files sharing the same stream structure. If files with different stream layouts exist in the queue, the wizard configures each subgroup before processing starts.
   * **"Configurar subgrupos" Button:** Allows you to configure or inspect versions at any time directly from the main panel before starting the queue.

---

## Batch Verification & Pre-flight Diagnostics
Before launching large encoding jobs, click **"Verify queue"** to execute a deep stream compatibility analysis:

* **Language Integrity Check:** Validates whether every queued file satisfies the audio/subtitle language tags required by the active preset.
* **Statistical Alerts:** Flags files missing target streams and categorizes discrepancies.
* **Detailed Diagnostics Modal:** Upon completion, VW displays a comprehensive report:
  * **Compatible Files:** Cleared and ready for automated processing.
  * **Incompatible Files:** Missing specific streams. Allows you to safely retry, divert to the "Skipped / Errors" tab with detailed logs, or force processing.

---

## Hybrid Single-Click Hardsubbing
Standard workflows require switching to a dedicated re-encoding panel to hardcode subtitles. VW features a hybrid shortcut:

* **Automatic Detection:** Selecting **exactly one (1) audio stream** and **exactly one (1) subtitle stream** in the version selector automatically enables the **"Hardsub (Burn-in)"** button.
* **Unified Pipeline:** Clicking this option invokes the hardware-accelerated GPU encoder directly from the remux module, muxing the selected audio track and burning in subtitles in a single execution pass.
