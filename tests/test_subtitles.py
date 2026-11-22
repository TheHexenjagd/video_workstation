"""Unit tests for external subtitle discovery and UTF-8 normalization."""

import os
from pathlib import Path
import tempfile
import unittest

from video_workstation.media.subtitles import (
    ensure_external_subtitle_utf8,
    find_external_subtitles,
)


class TestSubtitles(unittest.TestCase):
    def test_find_external_subtitles_matches_languages_and_forced(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            video = base / "Movie.mkv"
            video.write_bytes(b"")
            (base / "Movie.es.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHola\n", encoding="utf-8")
            (base / "Movie.en.forced.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n", encoding="utf-8")
            (base / "Other.es.srt").write_text("ignored", encoding="utf-8")

            subs = find_external_subtitles(video)
            self.assertEqual(len(subs), 2)
            self.assertEqual(subs[0]["lang_code"], "eng")
            self.assertIn("Forzados", subs[0]["lang_label"])
            self.assertEqual(subs[1]["lang_code"], "spa")

    def test_ensure_external_subtitle_utf8_converts_cp1252(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp1252_file = Path(tmp) / "sub_ansi.srt"
            cp1252_file.write_bytes("1\n00:00:01,000 --> 00:00:02,000\nCanción ñandú\n".encode("cp1252"))

            actual_path, temp_path = ensure_external_subtitle_utf8(str(cp1252_file))
            try:
                self.assertIsNotNone(temp_path)
                self.assertEqual(actual_path, temp_path)
                content = Path(actual_path).read_text(encoding="utf-8")
                self.assertIn("Canción ñandú", content)
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)

    def test_ensure_external_subtitle_utf8_keeps_utf8_without_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            utf8_file = Path(tmp) / "sub_utf8.srt"
            utf8_file.write_text("1\n00:00:01,000 --> 00:00:02,000\nÁrbol\n", encoding="utf-8")

            actual_path, temp_path = ensure_external_subtitle_utf8(str(utf8_file))
            self.assertIsNone(temp_path)
            self.assertEqual(actual_path, str(utf8_file))


if __name__ == "__main__":
    unittest.main()
