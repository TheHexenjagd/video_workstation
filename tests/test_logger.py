"""Unit tests for DailyLogger single-file-per-day persistence."""

from pathlib import Path
import tempfile
import unittest

from video_workstation.utils.logger import DailyLogger


class TestDailyLogger(unittest.TestCase):
    def test_appends_to_single_daily_file_with_separators(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = DailyLogger(tmp)
            logger.write("Session 1", separator=True)
            logger.write("Line one")
            logger.write("Session 2", separator=True)
            logger.write("Line two")

            log_files = list(Path(tmp).glob("*.log"))
            self.assertEqual(len(log_files), 1)
            content = log_files[0].read_text(encoding="utf-8")
            self.assertIn("SESIÓN:", content)
            self.assertEqual(content.count("SESIÓN:"), 2)
            self.assertIn("Line one", content)
            self.assertIn("Line two", content)


if __name__ == "__main__":
    unittest.main()
