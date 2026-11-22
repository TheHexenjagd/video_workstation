"""Unit tests for FFprobe metadata and track matching helpers."""

import unittest

from video_workstation.media.ffprobe import (
    find_track_by_identifier,
    get_track_identifier,
    is_hdr_video,
)


class TestFFprobeHelpers(unittest.TestCase):
    def test_is_hdr_video_sdr_10bit_returns_false(self):
        info = {
            "streams": [
                {
                    "codec_type": "video",
                    "pix_fmt": "yuv420p10le",
                    "color_transfer": "bt709",
                    "color_primaries": "bt709",
                }
            ]
        }
        self.assertFalse(is_hdr_video(info))

    def test_is_hdr_video_pq_and_bt2020_return_true(self):
        self.assertTrue(
            is_hdr_video({"streams": [{"codec_type": "video", "color_transfer": "smpte2084"}]})
        )
        self.assertTrue(
            is_hdr_video({"streams": [{"codec_type": "video", "color_primaries": "bt2020"}]})
        )

    def test_track_identifier_and_lookup(self):
        streams = [
            {"index": 1, "codec_type": "audio", "codec_name": "aac", "tags": {"language": "jpn", "title": "Main"}},
            {"index": 2, "codec_type": "audio", "codec_name": "ac3", "tags": {"language": "spa", "title": "Latino"}},
            {"index": 3, "codec_type": "subtitle", "is_external": True, "tags": {"language": "spa", "title": "[EXT] Español"}},
        ]
        audio_id = get_track_identifier(streams[1])
        self.assertEqual(audio_id, "spa|Latino|ac3")
        self.assertEqual(find_track_by_identifier(streams, audio_id, "audio"), 2)

        ext_id = get_track_identifier(streams[2])
        self.assertEqual(ext_id, "spa|[EXT] Español|external_subrip")
        self.assertEqual(find_track_by_identifier(streams, ext_id, "subtitle"), 3)
        self.assertIsNone(find_track_by_identifier(streams, "NINGUNO", "subtitle"))


if __name__ == "__main__":
    unittest.main()
