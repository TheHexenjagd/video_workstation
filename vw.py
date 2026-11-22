"""Video Workstation (VW) entry point."""

import os
import sys

_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.isdir(_SRC_DIR) and _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from video_workstation import VERSION  # noqa: E402, F401
from video_workstation.ui.app import main  # noqa: E402

if __name__ == "__main__":
    main()
