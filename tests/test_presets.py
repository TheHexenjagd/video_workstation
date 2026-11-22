"""Unit tests for GPU preset normalization."""

import unittest

from video_workstation.media.presets import get_valid_preset


class TestPresets(unittest.TestCase):
    def test_nvidia_preset_mapping(self):
        self.assertEqual(get_valid_preset("p4", "nvidia"), "p4")
        self.assertEqual(get_valid_preset("medium", "nvidia"), "p4")
        self.assertEqual(get_valid_preset("veryfast", "nvidia"), "p1")
        self.assertEqual(get_valid_preset("unknown", "nvidia"), "p4")

    def test_intel_and_amd_preset_mapping(self):
        self.assertEqual(get_valid_preset("hq", "intel"), "slow")
        self.assertEqual(get_valid_preset("p6", "intel"), "slower")
        self.assertEqual(get_valid_preset("medium", "amd"), "balanced")
        self.assertEqual(get_valid_preset("p5", "amd"), "quality")
        self.assertEqual(get_valid_preset("unknown", "amd"), "balanced")


if __name__ == "__main__":
    unittest.main()
