"""Edge Device SitSmart IoT (Berjalan di HP Android lewat Termux atau di Laptop).

Mendukung 2 peran:
  - Edge 1 : HP Badan (mengukur kemiringan postur & menerima alert getar)
  - Edge 2 : HP Kursi (mengukur keberadaan pengguna di kursi)

Menjalankan PROSES 1 (Edge Level):
  - Membaca Accelerometer (m/s^2) & Gyroscope (rad/s)
  - Exponential Moving Average (EMA) untuk stabilisasi gravitasi
  - Window RMS deviasi getaran gerak dinamis
  - Integrasi total rotasi
  - Mengirim telemetri ke cloud setiap 1 detik

Multicommunication 2 Arah:
  - Edge 1 berlangganan topik alerts (sitsmart/<PID>/alerts)
  - Memicu getaran (termux-vibrate) dan notifikasi saat postur buruk terdeteksi!
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[ERROR] Paho MQTT belum terpasang. Jalankan: pip install paho-mqtt")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from shared.processing import apply_ema, mean_vector, window_rms


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


# Muat environment
for env_name in [".env", ".env.example", ".env.example.txt"]:
    if (ROOT / env_name).exists():
        load_env(ROOT / env_name)
        break

PROJECT_ID = os.getenv("PROJECT_ID", "sitsmart_kelompok_07")
MQTT_HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Deteksi apakah command termux-sensor tersedia
HAS_TERMUX = shutil.which("termux-sensor") is not None


class SensorReader:
    """Membaca sensor fisik via Termux API atau simulator realistis jika di PC."""
    def __init__(self, edge_id: int, force_simulator: bool = False):
        self.edge_id = edge_id
        self.is_termux = HAS_TERMUX and not force_simulator
        self.accel_sensor_name = None
        self.gyro_sensor_name = None

        if self.is_termux:
            self._discover_termux_sensors()
        else:
            print("[INFO] Mode: Simulator Sensor Fisik (berjalan di PC/Laptop)")

    def _discover_termux_sensors(self):
        """Mencari nama sensor accelerometer dan gyroscope di Termux Android."""
        try:
            res = subprocess.run(
                ["termux-sensor", "-l"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            raw = json.loads(res.stdout)
            sensors = raw.get("sensors", [])
            for s in sensors:
                name_lower = s.lower()
                if "accel" in name_lower and not self.accel_sensor_name:
                    self.accel_sensor_name = s
                elif "gyro" in name_lower and not self.gyro_sensor_name:
                    self.gyro_sensor_name = s

            print(f"[TERMUX SENSOR] Accelerometer: {self.accel_sensor_name}")
            print(f"[TERMUX SENSOR] Gyroscope    : {self.gyro_sensor_name}")
        except Exception as e:
            print(f"[WARN] Gagal mencari sensor termux: {e}, beralih ke simulasi.")
            self.is_termux = False

    def read_sample(self, posture_scenario: str = "tegak") -> tuple[list[float], list[float]]:
        """Mengembalikan tuple (accel_vector_3d, gyro_vector_3d)."""
        if self.is_termux and self.accel_sensor_name:
            try:
                sensors_to_read = f"{self.accel_sensor_name}"
                if self.gyro_sensor_name:
                    sensors_to_read += f",{self.gyro_sensor_name}"

                res = subprocess.run(
                    ["termux-sensor", "-s", sensors_to_read, "-n", "1"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=True,
                )
                data = json.loads(res.stdout)
                acc_vals = data.get(self.accel_sensor_name, {}).get("values", [0.0, 9.8, 0.0])[:3]
                gyro_vals = [0.0, 0.0, 0.0]
                if self.gyro_sensor_name and self.gyro_sensor_name in data:
                    gyro_vals = data[self.gyro_sensor_name].get("values", [0.0, 0.0, 0.0])[:3]
                return [float(x) for x in acc_vals], [float(x) for x in gyro_vals]
            except Exception:
                pass

        # Fallback simulator bila tanpa Termux
        noise = [random.gauss(0, 0.03) for _ in range(3)]
        if self.edge_id == 1:
            # HP Badan
            if posture_scenario == "bungkuk":
                # Condong ke depan ~35 derajat
                acc = [0.0 + noise[0], 8.0 + noise[1], 5.6 + noise[2]]
            elif posture_scenario == "miring":
                # Condong ke samping
                acc = [5.6 + noise[0], 8.0 + noise[1], 0.0 + noise[2]]
            elif posture_scenario == "pergi":
                # Bergerak dinamis (jalan)
                acc = [random.uniform(-4, 4), 9.8 + random.uniform(-5, 5), random.uniform(-4, 4)]
            else:
                # Tegak normal
                acc = [0.0 + noise[0], 9.8 + noise[1], 0.0 + noise[2]]
        else:
            # HP Kursi (posisi datar di jok kursi)
            if posture_scenario == "guncang":
                acc = [random.uniform(-3, 3), random.uniform(-3, 3), 9.8 + random.uniform(-4, 4)]
            else:
                acc = [0.0 + noise[0], 0.0 + noise[1], 9.8 + noise[2]]

        gyro = [random.gauss(0, 0.02) for _ in range(3)]
        return acc, gyro


def trigger_vibrate_alarm(reason: str):
    """Memicu getaran dan notifikasi di HP Badan (Multicommunication 2 Arah)."""
    print(f"\a\n{'!' * 50}\n[ALARM DITERIMA DARI CLOUD] -> {reason}\n{'!' * 50}")
    if shutil.which("termux-vibrate"):
        try:
            subprocess.run(["termux-vibrate", "-d", "1200"], check=False)
        except Exception:
            pass
    if shutil.which("termux-notification"):
        try:
            subprocess.run([
                "termux-notification",
                "--title", "SitSmart IoT Alert!",
                "--content", reason,
                "--priority", "high"
            ], check=False)
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="SitSmart IoT - Edge Client")
    parser.add_argument("--edge", type=int, choices=[1, 2], default=1,
                        help="1 = HP Badan, 2 = HP Kursi")
    parser.add_argument("--project-id", type=str, default=PROJECT_ID,
                        help="Project ID unik kelompok")
    parser.add_argument("--source", type=str, choices=["auto", "termux", "simulator"], default="auto",
                        help="Sumber pembacaan sensor")
    parser.add_argument("--scenario", type=str, default="tegak",
                        choices=["tegak", "bungkuk", "miring", "pergi", "guncang"],
                        help="Skenario default jika menggunakan simulator")
    args = parser.parse_args()

    edge_name = "HP Badan (Postur)" if args.edge == 1 else "HP Kursi (Keberadaan)"
    t_pub = f"sitsmart/{args.project_id}/edge/{args.edge}/telemetry"
    t_alerts = f"sitsmart/{args.project_id}/alerts"

    print("=" * 60)
    print(f" SitSmart IoT - Node Edge {args.edge}: {edge_name}")
    print("=" * 60)
    print(f" * PROJECT_ID : {args.project_id}")
    print(f" * Broker MQTT: {MQTT_HOST}:{MQTT_PORT}")
    print(f" * Topik Kirim: {t_pub}")
    if args.edge == 1:
        print(f" * Topik Alert: {t_alerts} (Akan bergetar jika postur buruk)")
    print("-" * 60)

    reader = SensorReader(args.edge, force_simulator=(args.source == "simulator"))

    # Setup MQTT Client
    client_id = f"sitsmart-edge{args.edge}-{int(time.time())}-{random.randint(100, 999)}"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)

    def on_connect(c, userdata, flags, rc, props=None):
        print(f"[MQTT] Terhubung ke broker cloud ({rc})")
        if args.edge == 1:
            c.subscribe(t_alerts, qos=0)
            print(f"[MQTT 2-ARAH] Berlangganan topik alert: {t_alerts}")

    def on_message(c, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            reason = payload.get("reason", "Perbaiki postur duduk Anda!")
            trigger_vibrate_alarm(reason)
        except Exception:
            pass

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    except Exception as e:
        print(f"[ERROR] Gagal terhubung ke MQTT: {e}")
        sys.exit(1)

    client.loop_start()

    # Variabel pemrosesan PROSES 1 (Edge)
    window_accel_mags = []
    window_accel_vecs = []
    filtered_gravity = None
    accumulated_rot = 0.0
    seq = 0

    print("[RUNNING] Mengukur sensor fisik dan memproses data per 1 detik...")
    print("Tekan Ctrl+C untuk berhenti.\n")

    try:
        while True:
            t_start = time.time()
            # Ambil beberapa sampel dalam 1 detik untuk menghitung RMS dan EMA
            for _ in range(5):
                acc, gyro = reader.read_sample(args.scenario)
                mag = math.sqrt(acc[0] ** 2 + acc[1] ** 2 + acc[2] ** 2)
                window_accel_mags.append(mag)
                window_accel_vecs.append(acc)

                # EMA Low-pass filter untuk memisahkan vektor gravitasi statis
                filtered_gravity = apply_ema(acc, filtered_gravity, alpha=0.3)

                # Akumulasi rotasi giroskop
                rot_rate = math.sqrt(gyro[0] ** 2 + gyro[1] ** 2 + gyro[2] ** 2)
                accumulated_rot += rot_rate * 0.2
                time.sleep(0.18)

            # Hitung PROSES 1 di Edge
            rms_motion = window_rms(window_accel_mags)
            grav = filtered_gravity if filtered_gravity else mean_vector(window_accel_vecs)
            rot_val = accumulated_rot

            # Reset window untuk detik berikutnya
            window_accel_mags.clear()
            window_accel_vecs.clear()
            accumulated_rot = 0.0
            seq += 1

            telemetry = {
                "edge": args.edge,
                "seq": seq,
                "ts": int(time.time() * 1000),
                "rms": round(rms_motion, 4),
                "gravity": [round(x, 3) for x in grav],
                "rot": round(rot_val, 4),
            }

            # Kirim telemetri terproses ke MQTT Cloud
            client.publish(t_pub, json.dumps(telemetry), qos=0)
            sys.stdout.write(
                f"\r[Terkirim #{seq:04d}] RMS: {rms_motion:.3f} m/s^2 | Gravitasi: {[round(x,1) for x in grav]} | Rot: {rot_val:.3f} rad"
            )
            sys.stdout.flush()

            # Selaraskan jeda 1 detik
            elapsed = time.time() - t_start
            if elapsed < 1.0:
                time.sleep(1.0 - elapsed)

    except KeyboardInterrupt:
        print("\n[EDGE] Dihentikan oleh pengguna.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
