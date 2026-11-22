"""FFprobe stream inspection and track-matching helpers."""


def is_hdr_video(info):
    """Return True if the primary video stream uses HDR transfer or BT.2020 primaries."""
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            return (
                stream.get("color_transfer") in ("smpte2084", "arib-std-b67")
                or stream.get("color_primaries") == "bt2020"
            )
    return False


def get_track_identifier(stream):
    """Build a stable identifier string for an audio or subtitle stream."""
    tags = stream.get("tags") or {}
    if stream.get("is_external"):
        return f"{tags.get('language', 'und')}|{tags.get('title', '')}|external_subrip"
    return f"{tags.get('language', 'und')}|{tags.get('title', '')}|{stream.get('codec_name', 'unknown')}"


def find_track_by_identifier(streams, identifier, codec_type):
    """Find the best matching stream index for a saved track identifier."""
    if identifier in (None, "NINGUNO"):
        return None

    parts = identifier.split("|")
    if len(parts) >= 3:
        target_lang = parts[0]
        target_codec = parts[-1]
        target_title = "|".join(parts[1:-1])
    elif len(parts) == 2:
        target_lang, target_codec = parts
        target_title = ""
    else:
        target_lang = parts[0] if parts else ""
        target_title = ""
        target_codec = ""

    if target_codec == "external_subrip" or "[EXT]" in target_title:
        for stream in streams:
            if stream.get("codec_type") != codec_type or not stream.get("is_external"):
                continue
            tags = stream.get("tags") or {}
            if tags.get("language", "und") == target_lang and tags.get("title", "") == target_title:
                return stream["index"]
        for stream in streams:
            if stream.get("codec_type") != codec_type or not stream.get("is_external"):
                continue
            tags = stream.get("tags") or {}
            if tags.get("language", "und") == target_lang:
                return stream["index"]
        for stream in streams:
            if stream.get("codec_type") == codec_type and stream.get("is_external"):
                return stream["index"]

    for stream in streams:
        if stream.get("codec_type") != codec_type or stream.get("is_external"):
            continue
        tags = stream.get("tags") or {}
        if (
            tags.get("language", "und") == target_lang
            and tags.get("title", "") == target_title
            and stream.get("codec_name", "unknown") == target_codec
        ):
            return stream["index"]

    for stream in streams:
        if stream.get("codec_type") != codec_type or stream.get("is_external"):
            continue
        tags = stream.get("tags") or {}
        if tags.get("language", "und") == target_lang and tags.get("title", "") == target_title:
            return stream["index"]

    for stream in streams:
        if stream.get("codec_type") != codec_type or stream.get("is_external"):
            continue
        tags = stream.get("tags") or {}
        if tags.get("language", "und") == target_lang:
            return stream["index"]

    for stream in streams:
        if stream.get("codec_type") == codec_type and not stream.get("is_external"):
            return stream["index"]

    return None
