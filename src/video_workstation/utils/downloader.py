"""Cross-platform automatic FFmpeg and FFprobe downloader."""

import os
import platform
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

from video_workstation.utils.binaries import get_binary_filename


def get_ffmpeg_download_sources():
    """Return `(archive_type, urls)` for the current OS and architecture."""
    machine = platform.machine().lower()
    if sys.platform == "win32":
        return "zip_single", ["https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"]
    if sys.platform == "darwin":
        return "zip_pair", [
            "https://evermeet.cx/ffmpeg/getrelease/zip",
            "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip",
        ]
    arch = "arm64" if ("arm" in machine or "aarch64" in machine) else "amd64"
    return "tar_xz", [f"https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-{arch}-static.tar.xz"]


def _download_file(url, dest_path, progress_cb=None):
    req = urllib.request.Request(url, headers={"User-Agent": "VideoWorkstation/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        downloaded = 0
        with open(dest_path, "wb") as out_file:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if progress_cb:
                    progress_cb(downloaded, total)


def _extract_binaries_from_zip(zip_path, targets, dest_dir):
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            name = os.path.basename(member.filename)
            if name in targets:
                out_path = os.path.join(dest_dir, name)
                with zf.open(member) as src, open(out_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                if sys.platform != "win32":
                    os.chmod(out_path, os.stat(out_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _extract_binaries_from_tar(tar_path, targets, dest_dir):
    with tarfile.open(tar_path, "r:*") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            name = os.path.basename(member.name)
            if name in targets:
                src = tf.extractfile(member)
                if src is None:
                    continue
                out_path = os.path.join(dest_dir, name)
                with src, open(out_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                os.chmod(out_path, os.stat(out_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def download_ffmpeg_tools(dest_dir, status_cb=None, progress_cb=None):
    """
    Download and extract `ffmpeg` and `ffprobe` binaries into `dest_dir`.
    Returns `(ffmpeg_path, ffprobe_path)`.
    """
    os.makedirs(dest_dir, exist_ok=True)
    ffmpeg_name = get_binary_filename("ffmpeg")
    ffprobe_name = get_binary_filename("ffprobe")
    targets = {ffmpeg_name, ffprobe_name}

    archive_type, urls = get_ffmpeg_download_sources()
    with tempfile.TemporaryDirectory() as tmp_dir:
        for idx, url in enumerate(urls, 1):
            if status_cb:
                status_cb(f"Descargando paquete {idx}/{len(urls)}...")
            ext = ".tar.xz" if archive_type == "tar_xz" else ".zip"
            archive_path = os.path.join(tmp_dir, f"ffmpeg_pkg_{idx}{ext}")
            _download_file(url, archive_path, progress_cb=progress_cb)

            if status_cb:
                status_cb("Extrayendo binarios...")
            if archive_type == "tar_xz":
                _extract_binaries_from_tar(archive_path, targets, dest_dir)
            else:
                _extract_binaries_from_zip(archive_path, targets, dest_dir)

    ffmpeg_path = os.path.join(dest_dir, ffmpeg_name)
    ffprobe_path = os.path.join(dest_dir, ffprobe_name)
    if not (os.path.isfile(ffmpeg_path) and os.path.isfile(ffprobe_path)):
        raise FileNotFoundError("No se encontraron ffmpeg y ffprobe tras extraer el paquete descargado.")
    return ffmpeg_path, ffprobe_path
