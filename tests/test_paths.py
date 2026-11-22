"""Unit tests for dynamic output subfolder pattern resolution."""

import unittest

from video_workstation.media.paths import resolve_subfolder_pattern


class TestPathResolution(unittest.TestCase):
    def test_resolve_all_tokens(self):
        info = {
            "streams": [
                {"codec_type": "video", "codec_name": "hevc", "width": 1920, "height": 1080, "index": 0},
                {"codec_type": "audio", "codec_name": "flac", "index": 1, "tags": {"language": "jpn"}},
                {"codec_type": "audio", "codec_name": "aac", "index": 2, "tags": {"language": "spa"}},
                {"codec_type": "subtitle", "codec_name": "ass", "index": 3, "tags": {"language": "spa"}},
            ]
        }
        pattern = "{audio_langs}/{folder}/{resolution}_{codec_v}_{codec_a}_{sub_langs}_{label}_{name}"
        resolved = resolve_subfolder_pattern(
            pattern,
            "C:/Anime/Gantz/ep01.mkv",
            info,
            "JPN_subSPA",
            [1, 2],
            [3],
        )
        self.assertEqual(resolved, "JPN_SPA/Gantz/1080p_hevc_flac_SPA_JPN_subSPA_ep01")

    def test_resolve_without_info_uses_fallbacks(self):
        resolved = resolve_subfolder_pattern(
            "{audio_langs}/{resolution}/{name}",
            "C:/Videos/sample.mp4",
            None,
            "UND",
            [],
            [],
        )
        self.assertEqual(resolved, "UND/unknown/sample")


if __name__ == "__main__":
    unittest.main()
