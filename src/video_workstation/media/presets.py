"""GPU encoder preset normalization helpers."""

from video_workstation.constants import PRESETS_AMD, PRESETS_NVIDIA, PRESETS_QSV


def get_valid_preset(preset, gpu_accel):
    """Map a generic or vendor-specific preset name to a valid preset for `gpu_accel`."""
    if gpu_accel == "nvidia":
        if preset in PRESETS_NVIDIA:
            return preset
        mapping = {
            "veryfast": "p1",
            "faster": "p2",
            "hp": "p2",
            "llhp": "p2",
            "fast": "p3",
            "ll": "p3",
            "medium": "p4",
            "default": "p4",
            "balanced": "p4",
            "llhq": "p4",
            "slow": "p5",
            "slower": "p6",
            "hq": "p6",
            "bd": "p6",
            "quality": "p6",
            "veryslow": "p7",
            "lossless": "p7",
            "speed": "p1",
        }
        return mapping.get(preset, "p4")

    if gpu_accel == "intel":
        if preset in PRESETS_QSV:
            return preset
        mapping = {
            "p7": "veryslow",
            "p6": "slower",
            "p5": "slow",
            "p4": "medium",
            "p3": "fast",
            "p2": "faster",
            "p1": "veryfast",
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
            "p7": "quality",
            "p6": "quality",
            "p5": "quality",
            "p4": "balanced",
            "p3": "balanced",
            "p2": "speed",
            "p1": "speed",
            "lossless": "quality",
            "hq": "quality",
            "slow": "quality",
            "slower": "quality",
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
