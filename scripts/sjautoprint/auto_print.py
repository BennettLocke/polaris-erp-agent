#!/usr/bin/env python3
"""Stable entry point for the sjAutoPrint Windows service."""

from pathlib import Path
import sys


CURRENT_DIR = Path(__file__).resolve().parent
for candidate in (CURRENT_DIR, CURRENT_DIR.parent):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

from local_print_agent import main  # noqa: E402


if __name__ == "__main__":
    main()
