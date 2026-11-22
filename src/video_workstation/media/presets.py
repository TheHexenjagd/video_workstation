"""GPU encoder preset normalization helpers."""

from video_workstation.constants import PRESETS_AMD, PRESETS_NVIDIA, PRESETS_QSV


def get_valid_preset(preset, gpu_accel):
    """Map a generic or vendor-specific preset name to a valid preset for `gpu_accel`."""
    if gpu_accel == "nvidia":
        if preset in PRESETS_NVIDIA:
            return preset
        mapping = {
            "veryfast": "hp",
            "faster": "fast",
            "fast": "fast",
            "medium": "medium",
            "slow": "slow",
            "veryslow": "hq",
            "speed": "hp",
            "balanced": "medium",
            "quality": "hq",
        }
        return mapping.get(preset, "default")

    if gpu_accel == "intel":
        if preset in PRESETS_QSV:
            return preset
        mapping = {
            "default": "medium",
            "slow": "slow",
            "medium": "medium",
            "fast": "fast",
            "hp": "veryfast",
            "hq": "slow",
            "bd": "slow",
            "ll": "fast",
            "llhq": "medium",
            "llhp": "faster",
            "lossless": "veryslow",
            "speed": "veryfast",
            "balanced": "medium",
            "quality": "slow",
        }
        return mapping.get(preset, "medium")

    if gpu_accel == "amd":
        if preset in PRESETS_AMD:
            return preset
        mapping = {
            "lossless": "quality",
            "hq": "quality",
            "slow": "quality",
            "bd": "quality",
            "default": "balanced",
            "medium": "balanced",
            "llhq": "balanced",
            "fast": "speed",
            "ll": "speed",
            "llhp": "speed",
            "hp": "speed",
            "veryslow": "quality",
            "faster": "speed",
            "veryfast": "speed",
        }
        return mapping.get(preset, "balanced")

    return preset
