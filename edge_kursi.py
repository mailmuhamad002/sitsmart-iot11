"""Shortcut untuk menjalankan Edge 2 (HP Kursi).

Membaca sensor accelerometer + gyroscope di HP Kursi,
menghitung RMS getaran bantalan kursi untuk mendeteksi apakah pengguna sedang duduk atau berdiri.
"""
import sys
from pathlib import Path

# Sisipkan root directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from edge import main

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--edge", "2"] + sys.argv[1:]
    main()
