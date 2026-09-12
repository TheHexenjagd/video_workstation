# Dynamic Output Path Constructor

<p align="right">
  <b>English</b> | <a href="../es/rutas_dinamicas.md">Español</a>
</p>

When processing extensive batches of video files, manual file organization can quickly become cumbersome. Video Workstation (VW) features an intelligent **Dynamic Output Path Constructor** that parses media attributes on-the-fly and generates organized directory hierarchies automatically.

---

## Dynamic Subfolders Concept
Under the **Processing Options** panel in the main window, you will find the **"2. Subfolder: Create"** toggle.

* **Disabled:** Processed outputs are saved directly inside the designated destination folder.
* **Enabled:** VW dynamically generates a targeted subfolder path for each video based on an expressive token template.

---

## Available Token Placeholders
Construct folder hierarchies using dynamic tokens enclosed in curly brackets `{}`. During batch execution, VW replaces each placeholder with actual metadata extracted by FFprobe:

| Placeholder | Attribute Mapped | Output Sample |
|---|---|---|
| **`{name}`** | Base name of source file (without extension) | `Movie_2026` |
| **`{folder}`** | Parent folder name of source file | `Season 01` |
| **`{label}`** | Stream combination identifier tag | `SPA_subENG_hardsub` |
| **`{audio_langs}`**| Combined language tags of active audio tracks | `SPA_ENG` |
| **`{sub_langs}`** | Combined language tags of active subtitle tracks | `ENG` |
| **`{codec_v}`** | Video stream codec identifier | `h264` or `hevc` |
| **`{codec_a}`** | Codec of first selected audio stream | `aac`, `ac3`, or `dts` |
| **`{resolution}`** | Classified resolution standard | `1080p`, `2160p`, or `720p` |

---

## Interactive Constructor Modal
Clicking **"Configure"** adjacent to the Subfolder toggle opens the constructor dialog:

1. **Token Palette Buttons:** Flat macro buttons (`[Name]`, `[Parent Folder]`, `[Resolution]`, etc.) insert corresponding tokens directly at your cursor.
2. **Real-Time Preview:** A live simulated output path dynamically reflects changes as you assemble the token pattern.
3. **Preset Manager:** Save frequently used folder formulas (e.g., `{folder}/{resolution}/{codec_v}`) to the persistent preset store for rapid recall.

---

## Practical Template Examples

### Example A: Segregate by Resolution & Video Codec
* **Template:** `{resolution}/{codec_v}`
* **Resulting Path:** `C:/Output/1080p/h264/Processed_Video.mp4`
* *Separates 4K/UHD and 1080p assets into distinct codec-organized directories.*

### Example B: Preserve Episodic & Multi-Version Hierarchies
* **Template:** `{folder}/{name}/{label}`
* **Resulting Path:** `C:/Output/Season 01/Episode 01/SPA_subENG/Episode 01_SPA_subENG.mp4`
* *Organizes multi-version releases into clean dedicated episode subfolders.*

### Example C: Group by Audio Language Combinations
* **Template:** `Audios_{audio_langs}`
* **Resulting Path:** `C:/Output/Audios_SPA_ENG/Movie.mp4`
