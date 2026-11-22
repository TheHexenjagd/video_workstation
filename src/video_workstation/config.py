"""Application configuration paths and default INI values."""

import os
from pathlib import Path

from video_workstation.utils.binaries import (
    get_binary_filename,
    get_default_videos_dir,
    resolve_binary_path,
)

_appdata_env = os.getenv("APPDATA")
if _appdata_env:
    CONFIG_DIR = os.path.join(_appdata_env, "Team Galleon", "Video Workstation")
else:
    _xdg_cfg = os.getenv("XDG_CONFIG_HOME", os.path.join(str(Path.home()), ".config"))
    CONFIG_DIR = os.path.join(_xdg_cfg, "Team Galleon", "Video Workstation")

os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, "vw_config.ini")
QUEUE_FILE = os.path.join(CONFIG_DIR, "vw_queue.ini")

TOOLS_DIR = os.path.join(CONFIG_DIR, "tools")
os.makedirs(TOOLS_DIR, exist_ok=True)

LOGS_DIR = os.path.join(CONFIG_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "Paths": {
        "ffmpeg": resolve_binary_path(get_binary_filename("ffmpeg"), TOOLS_DIR),
        "ffprobe": resolve_binary_path(get_binary_filename("ffprobe"), TOOLS_DIR),
        "output_dir": get_default_videos_dir(),
    },
    "Options": {
        "buscar_recursivo": "True",
        "crear_subcarpeta": "False",
        "nombre_subcarpeta": "",
        "usar_nvidia": "True",
        "gpu_acel": "nvidia",
        "decod_hw": "Software",
        "preset": "medium",
        "eliminar_metadatos": "False",
        "buscar_subtitulos_externos": "True",
        "tema": "light",
    },
}
