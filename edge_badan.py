"""Shortcut untuk menjalankan Edge 1 (HP Badan).

Membaca sensor accelerometer + gyroscope di HP Badan,
menghitung RMS & kemiringan, serta menerima getaran alert dari cloud saat membungkuk.
"""
import sys
from pathlib import Path

# Sisipkan root directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from edge import main

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--edge", "1"] + sys.argv[1:]
    main()
