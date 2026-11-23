"""Unit tests for UI widget helpers such as center_window."""

import unittest

from video_workstation.ui.widgets import center_window


class _FakeParent:
    def __init__(self, x=200, y=100, w=1280, h=800, mapped=True):
        self._x = x
        self._y = y
        self._w = w
        self._h = h
        self._mapped = mapped

    def winfo_ismapped(self):
        return self._mapped

    def winfo_width(self):
        return self._w

    def winfo_height(self):
        return self._h

    def winfo_rootx(self):
        return self._x

    def winfo_rooty(self):
        return self._y


class _FakeWindow:
    def __init__(self, sw=1920, sh=1080):
        self._sw = sw
        self._sh = sh
        self.geo = ""

    def update_idletasks(self):
        pass

    def winfo_width(self):
        return 0

    def winfo_height(self):
        return 0

    def winfo_reqwidth(self):
        return 400

    def winfo_reqheight(self):
        return 300

    def winfo_screenwidth(self):
        return self._sw

    def winfo_screenheight(self):
        return self._sh

    def geometry(self, geo):
        self.geo = geo


class TestCenterWindow(unittest.TestCase):
    def test_center_on_screen_without_parent(self):
        win = _FakeWindow(1920, 1080)
        center_window(win, 750, 660)
        expected_x = (1920 - 750) // 2
        expected_y = (1080 - 48 - (660 + 56)) // 2
        self.assertEqual(win.geo, f"750x660+{expected_x}+{expected_y}")

    def test_center_over_parent_window(self):
        win = _FakeWindow(1920, 1080)
        parent = _FakeParent(x=200, y=100, w=1280, h=800)
        center_window(win, 750, 660, parent=parent)
        expected_x = 200 + (1280 - 750) // 2
        expected_y = 100 + (800 - 660) // 2
        self.assertEqual(win.geo, f"750x660+{expected_x}+{expected_y}")

    def test_clamping_to_screen_bounds(self):
        win = _FakeWindow(800, 600)
        parent = _FakeParent(x=500, y=400, w=600, h=500)
        center_window(win, 700, 500, parent=parent)
        # Should clamp so x + w <= 800 and y + h <= 600 - 48
        self.assertIn("700x500+", win.geo)
        coords = win.geo.split("+")[1:]
        x, y = int(coords[0]), int(coords[1])
        self.assertGreaterEqual(x, 0)
        self.assertLessEqual(x + 700, 800)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(y + 500, 600 - 48)


if __name__ == "__main__":
    unittest.main()
