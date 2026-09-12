# Regex Batch File Renamer

<p align="right">
  <b>English</b> | <a href="../es/renombrador.md">Español</a>
</p>

The **Batch Renamer** integrated into Video Workstation (VW) enables rapid, programmatic re-organization and sanitization of file queues using structured token patterns and regular expressions (Regex).

---

## Renamer Interface
To access the renamer, load at least one file into the main VW queue and click **"Rename"** in the *Maintenance* section. The tool opens a dedicated two-column modal:

1. **Left Panel (Rules & Configuration):** Configure token formulas, sequential numbering schemes, and regex replacement rules.
2. **Right Panel (Real-Time Diff Preview):** A live two-column table displaying **Original Filename** side-by-side with the computed **New Filename**. Changes update instantaneously as you type, ensuring zero unintended renames.

---

## 1. Token Pattern Configuration
The renamer utilizes core placeholders to assemble the base filename:

* **`{name}`**: The original filename (excluding path and extension).
* **`{num}`**: An incremental sequential integer counter.

### Sequence Options (`{num}`)
* **Start:** Defines the starting index (e.g., if a season batch begins at episode 13, set to `13`).
* **Padding Digits:** Controls zero-padding to ensure uniform lexical sorting across file managers:
  * Digits = `2`: `01`, `02`, `03`...
  * Digits = `3`: `001`, `002`, `003`...

---

## 2. Regular Expression (Regex) Matching & Sanitization
Toggle **"Use Regex"** to execute multi-stage pattern extraction and string sanitization on `{name}` prior to final pattern assembly.

### Practical Regex Recipes

#### A. Strip Release Group Tags and Brackets (e.g., `[ReleaseGroup] Video.mp4` ➡️ `Video.mp4`)
* **Match:** `\[.*?\]`
* **Replace:** *(leave empty)*

#### B. Extract Episode Indices from Verbose Titles (e.g., `Chapter 156 - The Return` ➡️ `156 The Return.mp4`)
* **Match:** `Chapter (\d+) - (.*)`
* **Replace:** `\1 \2` (references capture group `\1` for the number and `\2` for the title)

#### C. Collapse Multiple Consecutive Whitespace
* **Match:** `\s+`
* **Replace:** ` ` (single space)

---

## 3. Renaming Presets
VW includes built-in quick presets covering common media library workflows:

1. **Simple Numbering:** Renames files strictly by sequential counter (`01.mp4`, `02.mp4`...).
2. **Numbering + Name:** Appends sequential counter before the original title (`01 - Title.mp4`...).
3. **Extract Chapter:** Cleans verbose chapter strings for anime and episodic content.
4. **Extract Episode Coordinates:** Standardizes seasonal formats (e.g., `01x03` or `s01e01`).
5. **Strip Tags & Brackets:** Cleans brackets `[...]` and parentheses `(...)`.

### Custom Preset Storage
Save custom formulas for recurring ingestion workflows:
* Define patterns and regex parameters.
* Click **"Save preset"**, provide a descriptive label, and save. Presets persist in VW's configuration store.
