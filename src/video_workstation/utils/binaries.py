"""Cross-platform path and binary resolution helpers."""

import os
from pathlib import Path
import shutil
import sys


def get_default_videos_dir():
    """Return the user's default Videos directory across Windows, macOS, and Linux."""
    if sys.platform == "win32":
        try:
            import ctypes
            import ctypes.wintypes

            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 0x000E, None, 0, buf) == 0 and buf.value:
                os.makedirs(buf.value, exist_ok=True)
                return os.path.abspath(buf.value)
        except Exception:
            pass
        win_path = os.path.join(str(Path.home()), "Videos")
        try:
            os.makedirs(win_path, exist_ok=True)
        except Exception:
            pass
        return os.path.abspath(win_path)

    if sys.platform == "darwin":
        movies_dir = os.path.join(str(Path.home()), "Movies")
        if os.path.isdir(movies_dir):
            return os.path.abspath(movies_dir)
        videos_dir = os.path.join(str(Path.home()), "Videos")
        if os.path.isdir(videos_dir):
            return os.path.abspath(videos_dir)
        try:
            os.makedirs(movies_dir, exist_ok=True)
        except Exception:
            pass
        return os.path.abspath(movies_dir)

    xdg_videos = os.getenv("XDG_VIDEOS_DIR")
    if xdg_videos and os.path.isdir(xdg_videos):
        return os.path.abspath(xdg_videos)

    xdg_config = os.getenv("XDG_CONFIG_HOME", os.path.join(str(Path.home()), ".config"))
    user_dirs_file = os.path.join(xdg_config, "user-dirs.dirs")
    if os.path.isfile(user_dirs_file):
        try:
            with open(user_dirs_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("XDG_VIDEOS_DIR="):
                        val = line.split("=", 1)[1].strip('"\'')
                        val = val.replace("$HOME", str(Path.home()))
                        if os.path.isdir(val):
                            return os.path.abspath(val)
        except Exception:
            pass

    videos_dir = os.path.join(str(Path.home()), "Videos")
    try:
        os.makedirs(videos_dir, exist_ok=True)
    except Exception:
        pass
    return os.path.abspath(videos_dir)


def get_binary_filename(base_name):
    """Return the platform-appropriate executable filename (`<name>.exe` on Windows)."""
    return f"{base_name}.exe" if sys.platform == "win32" else base_name


def resolve_binary_path(binary_name, tools_dir):
    """
    Resolve an external binary path in priority order:
    1. Dedicated application tools directory (`<CONFIG_DIR>/tools/<binary_name>`)
    2. Operating system PATH (`shutil.which`)
    3. Default fallback inside `tools_dir`
    """
    app_tools_path = os.path.join(tools_dir, binary_name)
    if os.path.isfile(app_tools_path):
        return app_tools_path

    base_name = os.path.splitext(binary_name)[0]
    in_path = shutil.which(binary_name) or shutil.which(base_name)
    if in_path and os.path.isfile(in_path):
        return os.path.abspath(in_path)

    return app_tools_path
