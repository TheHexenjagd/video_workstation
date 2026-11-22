"""Dynamic output subfolder pattern resolution."""

from pathlib import Path


def resolve_subfolder_pattern(pattern, filepath, info, label, audio_indices, sub_indices):
    """Resolve dynamic `{token}` placeholders in `pattern` using FFprobe stream metadata."""
    video_stem = Path(filepath).stem
    parent_folder = Path(filepath).parent.name or "input_folder"
    pattern = (pattern or "").strip()

    if info is None:
        mapping = {
            "{name}": video_stem,
            "{folder}": parent_folder,
            "{label}": label,
            "{audio_langs}": "UND",
            "{sub_langs}": "NONE",
            "{codec_v}": "unknown",
            "{codec_a}": "unknown",
            "{resolution}": "unknown",
        }
        for placeholder, value in mapping.items():
            pattern = pattern.replace(placeholder, str(value))
        return pattern

    video_stream = next((s for s in info["streams"] if s.get("codec_type") == "video"), {})
    codec_v = video_stream.get("codec_name", "unknown")

    try:
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
    except (ValueError, TypeError):
        width = 0
        height = 0

    if height >= 2160 or width >= 3840:
        resolution = "2160p"
    elif height >= 1080 or width >= 1920:
        resolution = "1080p"
    elif height >= 720 or width >= 1280:
        resolution = "720p"
    elif height >= 480 or width >= 854:
        resolution = "480p"
    elif height > 0:
        resolution = f"{height}p"
    else:
        resolution = "unknown"

    audio_streams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    if audio_indices:
        selected_audios = [s for s in audio_streams if s.get("index") in audio_indices]
    else:
        selected_audios = audio_streams[:1] if audio_streams else []

    codec_a = selected_audios[0].get("codec_name", "unknown") if selected_audios else "none"

    audio_langs = []
    for stream in (selected_audios if audio_indices else audio_streams):
        lang = stream.get("tags", {}).get("language", "und").upper()
        if lang not in audio_langs:
            audio_langs.append(lang)
    audio_langs_str = "_".join(audio_langs) if audio_langs else "UND"

    subtitle_streams = [s for s in info["streams"] if s.get("codec_type") == "subtitle"]
    if sub_indices:
        sub_indices_int = [int(x) for x in sub_indices if x is not None]
        selected_subs = [s for s in subtitle_streams if int(s.get("index", -1)) in sub_indices_int]
    else:
        selected_subs = []

    sub_langs = []
    for stream in selected_subs:
        lang = stream.get("tags", {}).get("language", "und").upper()
        if lang not in sub_langs:
            sub_langs.append(lang)
    sub_langs_str = "_".join(sub_langs) if sub_langs else "NONE"

    mapping = {
        "{name}": video_stem,
        "{folder}": parent_folder,
        "{label}": label,
        "{audio_langs}": audio_langs_str,
        "{sub_langs}": sub_langs_str,
        "{codec_v}": codec_v,
        "{codec_a}": codec_a,
        "{resolution}": resolution,
    }

    for placeholder, value in mapping.items():
        pattern = pattern.replace(placeholder, str(value))

    return pattern
