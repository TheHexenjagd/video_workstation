# GPU Acceleration & Subtitle Hardcoding (Burn-in)

<p align="right">
  <b>English</b> | <a href="../es/hardcode_gpu.md">Español</a>
</p>

The **Hardcode** module in Video Workstation (VW) permanently burns subtitle streams into the primary video stream (a process widely known as *burn-in* or *hardsub*). To prevent excessive CPU utilization and long render bottlenecks, VW provides hardware-accelerated video encoding and decoding via dedicated graphics processing units (GPUs).

---

## Hardware-Accelerated Video Encoders (GPU)
VW detects and integrates three major hardware video encoding architectures:

### 1. NVIDIA NVENC (`h264_nvenc`)
* **Hardware:** NVIDIA GeForce, Quadro, and Tesla GPUs.
* **Features:** High encoding throughput and rate-distortion efficiency with minimal CPU overhead.
* **Target Codec:** `h264_nvenc` for universally compatible H.264 video.

### 2. Intel Quick Sync Video (`h264_qsv`)
* **Hardware:** Intel Core processors with integrated graphics (HD/UHD Graphics) or discrete Intel Arc GPUs.
* **Features:** Dedicated fixed-function media processing silicon integrated into Intel CPUs.
* **Target Codec:** `h264_qsv`.

### 3. AMD Advanced Media Framework (`h264_amf`)
* **Hardware:** AMD Radeon and Radeon Pro GPUs.
* **Features:** Hardware-assisted video compression for AMD architectures.
* **Target Codec:** `h264_amf`.

> [!NOTE]
> On startup, VW executes non-blocking background probing routines (`_iniciar_deteccion_gpus`) to verify live hardware encoder availability. Unavailable encoders are dynamically tagged as **(Unavailable)** in the UI to prevent execution failures.

---

## Hardware-Accelerated Decoding
In addition to accelerated encoding, VW offloads source video decoding to the GPU:

* **Software (CPU):** Decodes using the host processor. The safest baseline if hardware decoding causes visual artifacts.
* **D3D11VA:** Direct3D 11 Video Acceleration. Recommended for modern Windows 10 and 11 systems.
* **DXVA2:** DirectX Video Acceleration 2. Maximizes backward compatibility across legacy Windows hardware.

---

## Performance Presets

Each encoder pipeline offers calibrated presets to balance encoding speed against rate-distortion visual fidelity:

### NVIDIA NVENC Presets
| Preset | Technical Name | Description | Speed | Quality |
|---|---|---|---|---|
| **Lossless** | `lossless` | Mathematically lossless encoding (very high bitrate) | ⚡☆☆ | ★★★★★ |
| **HQ** | `hq` | High visual quality focus | ⚡☆☆ | ★★★★☆ |
| **Slow (HQ)** | `slow` | Superior rate-distortion compression | ⚡☆☆ | ★★★★☆ |
| **BD** | `bd` | Tuned for Blu-ray compliance specifications | ⚡☆☆ | ★★★★☆ |
| **Default** | `default` | Balanced speed/quality profile | ⚡⚡☆ | ★★★☆ |
| **Medium** | `medium` | Standard balance profile | ⚡⚡☆ | ★★★☆ |
| **LLHQ** | `llhq` | Low latency with quality optimization | ⚡⚡☆ | ★★★☆ |
| **Fast** | `fast` | Faster encode pass, standard compression | ⚡⚡⚡ | ★★☆☆ |
| **LL** | `ll` | Low latency mode | ⚡⚡⚡ | ★★☆☆ |
| **LLHP** | `llhp` | Low latency high performance | ⚡⚡⚡ | ★★☆☆ |
| **HP** | `hp` | Maximum throughput (high performance) | ⚡⚡⚡⚡ | ★★☆☆ |

### Intel Quick Sync (QSV) Presets
| Preset | Technical Name | Description | Speed | Quality |
|---|---|---|---|---|
| **Very Slow** | `veryslow` | Maximum visual fidelity | ⚡☆☆ | ★★★★★ |
| **Slow** | `slow` | Enhanced quality target | ⚡☆☆ | ★★★★☆ |
| **Medium** | `medium` | Balanced quality and encoding speed | ⚡⚡☆ | ★★★☆ |
| **Fast** | `fast` | Fast, efficient compression | ⚡⚡⚡ | ★★★☆ |
| **Faster** | `faster` | Emphasizes export speed | ⚡⚡⚡ | ★★☆☆ |
| **Very Fast** | `veryfast` | Maximum encoding throughput | ⚡⚡⚡⚡ | ★★☆☆ |

### AMD AMF Presets
| Preset | Technical Name | Description | Speed | Quality |
|---|---|---|---|---|
| **Quality** | `quality` | High visual fidelity target | ⚡☆☆ | ★★★★★ |
| **Balanced** | `balanced` | Balanced compromise between speed and quality | ⚡⚡☆ | ★★★☆ |
| **Speed** | `speed` | Fast render pass | ⚡⚡⚡⚡ | ★★☆☆ |

---

## High Dynamic Range (HDR) Color Warning
When processing files containing HDR color metadata (e.g., HDR10, Dolby Vision), FFprobe flags the color profile. VW prompts a safety notice:
> *Source video contains HDR metadata. Hardcoding subtitles without tone mapping may result in washed-out SDR colors.*
