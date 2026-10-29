"""Simulator Telemetri Edge SitSmart IoT (Untuk Pengujian & Demo).

Mengirim telemetri sintetis 2-Edge langsung ke MQTT Cloud, memungkinkan
pengujian lengkap Detector dan Dashboard tanpa memerlukan 2 HP fisik.

Pemakaian:
  python scripts/simulate.py              -> Masuk ke mode interaktif (ubah skenario live)
  python scripts/simulate.py tegak        -> Simulasi postur tegak normal
  python scripts/simulate.py bungkuk      -> Simulasi membungkuk ke depan (SLOUCH)
  python scripts/simulate.py miring       -> Simulasi miring ke samping (LATERAL_LEAN)
  python scripts/simulate.py pergi        -> Simulasi berdiri & berjalan (AWAY)
  python scripts/simulate.py guncang      -> Simulasi guncangan meja (COMMON_MOTION)
"""
from __future__ import annotations

import json
import os
import random
import sys
import threading
import time
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[ERROR] Paho MQTT belum terpasang. Jalankan: pip install paho-mqtt")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


for env_file in [".env", ".env.example", ".env.example.txt"]:
    if (ROOT / env_file).exists():
        load_env(ROOT / env_file)
        break

PROJECT_ID = os.getenv("PROJECT_ID", "sitsmart_kelompok_07")
MQTT_HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Preset skenario: (body_cfg, seat_cfg)
SCENARIOS = {
    "tegak": {
        "name": "Duduk Tegak Baik",
        "body": {"rms": 0.04, "gravity": [0.0, 9.8, 0.0], "rot": 0.01},
        "seat": {"rms": 0.03, "gravity": [0.0, 0.0, 9.8], "rot": 0.01},
    },
    "bungkuk": {
        "name": "Membungkuk ke Depan (> 20 deg)",
        "body": {"rms": 0.05, "gravity": [0.0, 8.0, 5.6], "rot": 0.02},
        "seat": {"rms": 0.03, "gravity": [0.0, 0.0, 9.8], "rot": 0.01},
    },
    "miring": {
        "name": "Miring ke Samping (> 20 deg)",
        "body": {"rms": 0.05, "gravity": [5.6, 8.0, 0.0], "rot": 0.02},
        "seat": {"rms": 0.03, "gravity": [0.0, 0.0, 9.8], "rot": 0.01},
    },
    "pergi": {
        "name": "Berdiri & Berjalan (AWAY)",
        "body": {"rms": 2.10, "gravity": [1.5, 9.2, 2.0], "rot": 0.85},
        "seat": {"rms": 0.02, "gravity": [0.0, 0.0, 9.8], "rot": 0.01},
    },
    "guncang": {
        "name": "Meja Digebrak (COMMON_MOTION)",
        "body": {"rms": 1.85, "gravity": [0.0, 9.8, 0.0], "rot": 0.65},
        "seat": {"rms": 1.95, "gravity": [0.0, 0.0, 9.8], "rot": 0.70},
    },
}

current_scenario = "tegak"
running = True


def input_listener():
    global current_scenario, running
    print("\n[KONTROL LIVE] Tekan angka untuk beralih skenario kapan saja:")
    print("  1 = Tegak Normal")
    print("  2 = Membungkuk ke Depan (SLOUCH)")
    print("  3 = Miring ke Samping (LATERAL_LEAN)")
    print("  4 = Berdiri & Berjalan (AWAY)")
    print("  5 = Guncang Meja (COMMON_MOTION)")
    print("  q = Keluar\n")

    key_map = {"1": "tegak", "2": "bungkuk", "3": "miring", "4": "pergi", "5": "guncang"}
    while running:
        try:
            line = sys.stdin.readline().strip().lower()
            if not line:
                continue
            if line in ("q", "quit", "exit"):
                running = False
                break
            if line in key_map:
                current_scenario = key_map[line]
                print(f"\n>>> [SKENARIO AKTIF]: {SCENARIOS[current_scenario]['name']}")
            elif line in SCENARIOS:
                current_scenario = line
                print(f"\n>>> [SKENARIO AKTIF]: {SCENARIOS[current_scenario]['name']}")
            else:
                print("Pilihan tidak dikenal. Masukkan 1-5 atau 'q'.")
        except Exception:
            break


def main():
    global current_scenario, running
    arg_scenario = sys.argv[1].lower() if len(sys.argv) > 1 else None

    interactive = arg_scenario is None or arg_scenario == "interactive"
    if arg_scenario and arg_scenario in SCENARIOS:
        current_scenario = arg_scenario

    client_id = f"sitsmart-sim-{int(time.time())}"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)

    print("=" * 60)
    print(" SitSmart IoT - Simulator Telemetri 2-Edge")
    print("=" * 60)
    print(f" * PROJECT_ID : {PROJECT_ID}")
    print(f" * MQTT Broker: {MQTT_HOST}:{MQTT_PORT}")
    print(f" * Skenario Awal: {SCENARIOS[current_scenario]['name']}")
    print("-" * 60)

    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    except Exception as e:
        print(f"[ERROR] Gagal menyambung ke MQTT: {e}")
        sys.exit(1)

    client.loop_start()

    if interactive:
        t = threading.Thread(target=input_listener, daemon=True)
        t.start()

    seq = 0
    try:
        while running:
            seq += 1
            sc = SCENARIOS[current_scenario]
            now_ms = int(time.time() * 1000)

            for edge_id, edge_cfg in ((1, sc["body"]), (2, sc["seat"])):
                # Tambahkan sedikit fluktuasi acak Gaussian (noise sensor alami)
                noise_rms = max(0.01, edge_cfg["rms"] + random.gauss(0, 0.01))
                noise_grav = [round(g + random.gauss(0, 0.05), 3) for g in edge_cfg["gravity"]]
                noise_rot = max(0.0, edge_cfg["rot"] + random.gauss(0, 0.01))

                payload = {
                    "edge": edge_id,
                    "seq": seq,
                    "ts": now_ms,
                    "rms": round(noise_rms, 4),
                    "rot": round(noise_rot, 4),
                    "gravity": noise_grav,
                }
                topic = f"sitsmart/{PROJECT_ID}/edge/{edge_id}/telemetry"
                client.publish(topic, json.dumps(payload), qos=0)

            if not interactive:
                sys.stdout.write(f"\r[Simulasi #{seq:04d}] Skenario: {sc['name']} -> dikirim ke MQTT")
                sys.stdout.flush()

            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        running = False
        client.loop_stop()
        client.disconnect()
        print("\nSimulator selesai.")


if __name__ == "__main__":
    main()
