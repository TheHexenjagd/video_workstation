"""Unit tests for cross-platform FFmpeg downloader and binary naming helpers."""

from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

from video_workstation.utils.binaries import get_binary_filename
from video_workstation.utils.downloader import (
    _extract_binaries_from_zip,
    get_ffmpeg_download_sources,
)


class TestDownloader(unittest.TestCase):
    def test_get_binary_filename_matches_platform(self):
        expected_suffix = ".exe" if sys.platform == "win32" else ""
        self.assertEqual(get_binary_filename("ffmpeg"), f"ffmpeg{expected_suffix}")
        self.assertEqual(get_binary_filename("ffprobe"), f"ffprobe{expected_suffix}")

    def test_get_ffmpeg_download_sources_returns_valid_tuple(self):
        archive_type, urls = get_ffmpeg_download_sources()
        self.assertIn(archive_type, ("zip_single", "zip_pair", "tar_xz"))
        self.assertTrue(all(url.startswith("https://") for url in urls))

    def test_extract_binaries_from_zip_extracts_only_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            zip_file = tmp_path / "pkg.zip"
            out_dir = tmp_path / "out"
            out_dir.mkdir()

            with zipfile.ZipFile(zip_file, "w") as zf:
                zf.writestr("ffmpeg-build/bin/ffmpeg.exe", b"ffmpeg-bin")
                zf.writestr("ffmpeg-build/bin/ffprobe.exe", b"ffprobe-bin")
                zf.writestr("ffmpeg-build/README.txt", b"ignore")

            _extract_binaries_from_zip(str(zip_file), {"ffmpeg.exe", "ffprobe.exe"}, str(out_dir))
            self.assertTrue((out_dir / "ffmpeg.exe").is_file())
            self.assertTrue((out_dir / "ffprobe.exe").is_file())
            self.assertFalse((out_dir / "README.txt").exists())


if __name__ == "__main__":
    unittest.main()
