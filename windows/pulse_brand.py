"""Approved brand assets in source mode and the PyInstaller extraction directory."""
from pathlib import Path
import sys


def asset(name):
    base = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
    return base / 'brand' / name
