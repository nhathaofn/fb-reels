#!/usr/bin/env python3
"""Entrypoint khởi chạy ứng dụng Facebook Reels & Article Extractor (Desktop App)."""

import sys
from pathlib import Path

# Đảm bảo đường dẫn gốc tương đối được nhận diện chính xác
if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys.executable).resolve().parent
else:
    ROOT_DIR = Path(__file__).resolve().parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.ui.desktop_app import DesktopApp


def main():
    app = DesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
