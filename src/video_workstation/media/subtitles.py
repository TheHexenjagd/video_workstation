"""External subtitle discovery and UTF-8 encoding normalization."""

import os
from pathlib import Path
import tempfile

from video_workstation.constants import SUBTITLE_LANGUAGE_MAP


def find_external_subtitles(video_path):
    """
    Search for `.srt` subtitle files in the same directory matching `video_path`.
    Supports `{video}.srt`, `{video}.es.srt`, `{video}.spa.srt`, `{video} - {lang}.srt`, etc.
    """
    try:
        raw_path = str(video_path)
        if raw_path.startswith("\\\\?\\"):
            raw_path = raw_path[4:]
        path = Path(raw_path)
        parent_dir = path.parent
        if not parent_dir.exists() or not parent_dir.is_dir():
            return []

        stem = path.stem
        subtitles = []
        for item in sorted(parent_dir.iterdir(), key=lambda x: x.name):
            if not item.is_file() or item.suffix.lower() != ".srt":
                continue
            item_stem = item.stem
            matched = False
            lang_code = "und"
            lang_label = "Externo"

            if item_stem.lower() == stem.lower():
                matched = True
            elif item_stem.lower().startswith(stem.lower()):
                next_char = item_stem[len(stem)]
                if next_char in (".", "_", "-", " ", "["):
                    matched = True
                    remainder = item_stem[len(stem) :].strip(" ._-")
                    parts = remainder.lower().split(".")
                    lang_part = parts[0].strip(" ._-")
                    is_forced = "forced" in remainder.lower() or "forzado" in remainder.lower()

                    if lang_part in SUBTITLE_LANGUAGE_MAP:
                        lang_code, lang_label = SUBTITLE_LANGUAGE_MAP[lang_part]
                    elif len(lang_part) in (2, 3) and lang_part.isalpha():
                        lang_code = lang_part.lower()
                        lang_label = lang_part.upper()
                    else:
                        lang_code = "und"
                        lang_label = lang_part.capitalize() if lang_part else "Externo"

                    if is_forced:
                        lang_label += " (Forzados)"

            if matched:
                subtitles.append(
                    {
                        "path": str(item.resolve()),
                        "filename": item.name,
                        "lang_code": lang_code,
                        "lang_label": lang_label,
                    }
                )
        return subtitles
    except Exception:
        return []


def ensure_external_subtitle_utf8(filepath):
    """
    Verify that an external subtitle file is valid UTF-8.
    Returns `(filepath, None)` if already UTF-8, or converts legacy encodings
    (CP1252/Latin-1/UTF-16) into a temporary UTF-8 `.srt` and returns `(temp_path, temp_path)`.
    """
    if not filepath or not os.path.isfile(filepath):
        return filepath, None

    try:
        with open(filepath, "rb") as file_obj:
            raw = file_obj.read()

        if not raw:
            return filepath, None

        if raw.startswith(b"\xef\xbb\xbf"):
            return filepath, None

        try:
            raw.decode("utf-8")
            return filepath, None
        except UnicodeDecodeError:
            pass

        text = None
        if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            try:
                text = raw.decode("utf-16", errors="replace")
            except Exception:
                pass

        if text is None:
            encodings = ["cp1252", "latin1", "iso-8859-1", "iso-8859-15", "cp1250", "cp1251"]
            for enc in encodings:
                try:
                    text = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue

        if text is None:
            text = raw.decode("cp1252", errors="replace")

        with tempfile.NamedTemporaryFile("w", suffix=".srt", delete=False, encoding="utf-8") as temp_file:
            temp_file.write(text)
            temp_path = temp_file.name

        return temp_path, temp_path

    except Exception:
        return filepath, None
