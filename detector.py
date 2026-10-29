"""NODE 3: Detector SitSmart IoT (Central Aggregator & Local Server).

Tugas Node 3:
  1. Berlangganan (Subscribe) telemetri dari 2 HP Edge melalui MQTT Cloud.
  2. Menjalankan pengolahan data tingkat 2 & algoritma Sensor Fusion (shared/processing.py).
  3. Mempublikasikan status berkala (retained) dan alert 2-arah ke MQTT Cloud.
  4. Menerima instruksi kendali dua arah (control) dari dashboard atau perangkat edge.
  5. Menyajikan antarmuka Dashboard Web pada port 8000 di jaringan lokal (WiFi/hotspot).
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[ERROR] Paho MQTT belum terpasang. Jalankan: pip install -r requirements.txt")
    sys.exit(1)

from shared.processing import Params, PostureEngine, Sample

ROOT = Path(__file__).resolve().parent


def get_local_ip() -> str:
    """Mendeteksi IP address laptop pada interface jaringan lokal (WiFi / Hotspot)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # Tidak benar-benar mengirim data, hanya untuk resolusi interface rute lokal
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def load_env(path: Path) -> None:
    """Membaca konfigurasi file .env tanpa perlu dependensi pihak ketiga."""
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            os.environ.setdefault(k, v)


# Muat environment (.env atau .env.example)
if (ROOT / ".env").exists():
    load_env(ROOT / ".env")
elif (ROOT / ".env.example").exists():
    load_env(ROOT / ".env.example")
elif (ROOT / ".env.example.txt").exists():
    load_env(ROOT / ".env.example.txt")

PROJECT_ID = os.getenv("PROJECT_ID", "sitsmart_kelompok_07")
MQTT_HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_WS_URL = os.getenv("MQTT_WS_URL", "wss://broker.hivemq.com:8884/mqtt")
SERVER_PORT = int(os.getenv("PORT", "8000"))

BASE_TOPIC = f"sitsmart/{PROJECT_ID}"
T_TELEMETRY = f"{BASE_TOPIC}/edge/+/telemetry"
T_STATUS = f"{BASE_TOPIC}/status"
T_ALERTS = f"{BASE_TOPIC}/alerts"
T_CONTROL = f"{BASE_TOPIC}/control"
ALERT_REPEAT_S = 8.0

params = Params(
    lean_threshold_deg=float(os.getenv("LEAN_THRESHOLD_DEG", "20.0")),
    lateral_threshold_deg=float(os.getenv("LATERAL_THRESHOLD_DEG", "20.0")),
    lean_hold_s=float(os.getenv("LEAN_HOLD_S", "5.0")),
    sit_limit_s=float(os.getenv("SIT_LIMIT_S", "1800.0")),
)
engine = PostureEngine(params)
lock = threading.Lock()
state_tracker = {
    "last_state": None,
    "last_alert_time": 0.0,
    "total_slouch_events": 0,
    "total_alerts": 0,
}


def on_connect(client, userdata, flags, reason_code, properties=None):
    """Callback saat berhasil terhubung ke MQTT Broker."""
    print(f"[MQTT] Terhubung ke broker {MQTT_HOST}:{MQTT_PORT} (Code: {reason_code})")
    client.subscribe([(T_TELEMETRY, 0), (T_CONTROL, 0)])
    print(f"[MQTT] Berlangganan topik:")
    print(f"       + {T_TELEMETRY}")
    print(f"       + {T_CONTROL}")


def on_message(client, userdata, msg):
    """Callback saat pesan MQTT diterima dari Edge atau Dashboard."""
    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return

    now = time.time()
    with lock:
        if msg.topic == T_CONTROL:
            handle_control(client, data, now)
            return

        # Topik telemetri: sitsmart/<PROJECT_ID>/edge/<ID>/telemetry
        parts = msg.topic.split("/")
        try:
            edge_id = int(parts[3])
            sample = Sample(
                t=now,
                rms=float(data["rms"]),
                gravity=[float(x) for x in data["gravity"]][:3],
                rot=float(data.get("rot", 0.0)),
            )
        except (IndexError, KeyError, ValueError, TypeError):
            return

        engine.feed(edge_id, sample)


def handle_control(client: mqtt.Client, data: dict, now: float) -> None:
    """Memproses perintah kendali dua arah dari Dashboard."""
    cmd = data.get("cmd")
    print(f"[CONTROL] Perintah diterima: {cmd}")

    if cmd == "calibrate":
        ok = engine.calibrate()
        status_msg = "Kalibrasi berhasil!" if ok else "Kalibrasi gagal (Belum ada data HP Badan)"
        print(f"[CONTROL] {status_msg}")
        ack = {"cmd": "calibrate", "status": "ok" if ok else "fail", "message": status_msg}
        client.publish(f"{BASE_TOPIC}/control/ack", json.dumps(ack), qos=0)

    elif cmd == "monitor_on":
        engine.monitoring = True
        print("[CONTROL] Monitoring diaktifkan")

    elif cmd == "monitor_off":
        engine.monitoring = False
        print("[CONTROL] Monitoring dijeda")

    elif cmd == "reset_timer":
        engine.reset_timer(now)
        print("[CONTROL] Timer duduk direset ke 0 detik")

    elif cmd == "test_alert":
        # Menguji jalur 2 arah: membunyikan/menggetarkan HP 1
        test_alert = {
            "ts": int(now * 1000),
            "type": "SLOUCH",
            "risk": 1.0,
            "score": 50,
            "reason": "[TEST] Uji Coba Komunikasi 2-Arah Dashboard -> HP!",
        }
        client.publish(T_ALERTS, json.dumps(test_alert), qos=0)
        print("[CONTROL] Mengirim test alert ke HP 1 (Topik: sitsmart/alerts)")


def publish_loop(client: mqtt.Client) -> None:
    """Loop periodik 1 detik: evaluasi status dan kirim telemetri/alert ke MQTT."""
    while True:
        time.sleep(1.0)
        now = time.time()
        with lock:
            status = engine.evaluate(now)
            body, seat = engine.body, engine.seat

            status["ts"] = int(now * 1000)
            status["body"] = None if body is None else {
                "rms": round(body.rms, 3),
                "rot": round(body.rot, 3),
                "gravity": [round(x, 2) for x in body.gravity],
                "age_s": round(now - body.t, 1),
            }
            status["seat"] = None if seat is None else {
                "rms": round(seat.rms, 3),
                "rot": round(seat.rot, 3),
                "gravity": [round(x, 2) for x in seat.gravity],
                "age_s": round(now - seat.t, 1),
            }
            status["total_slouch"] = state_tracker["total_slouch_events"]

        # Publikasikan status terkini untuk Dashboard (retained = true)
        client.publish(T_STATUS, json.dumps(status), qos=0, retain=True)

        state = status["state"]
        # Trigger alert jika kondisi buruk terdeteksi (SLOUCH, LATERAL_LEAN, BREAK)
        if state in ("SLOUCH", "LATERAL_LEAN", "BREAK"):
            is_new_state = state != state_tracker["last_state"]
            time_since_last = now - state_tracker["last_alert_time"]

            if is_new_state:
                if state in ("SLOUCH", "LATERAL_LEAN"):
                    state_tracker["total_slouch_events"] += 1

            if is_new_state or time_since_last >= ALERT_REPEAT_S:
                alert = {
                    "ts": status["ts"],
                    "type": state,
                    "risk": status["risk"],
                    "score": status.get("score", 100),
                    "reason": status["reason"],
                }
                # Kirim alert 2 arah ke broker -> diterima oleh Dashboard & HP Badan
                client.publish(T_ALERTS, json.dumps(alert), qos=0)
                state_tracker["last_alert_time"] = now
                state_tracker["total_alerts"] += 1
                print(f"[ALERT KE HP] {state} (Skor: {status.get('score')}%) -> {status['reason']}")
        elif state != state_tracker["last_state"]:
            print(f"[STATUS] {state} -> {status['reason']} (Skor: {status.get('score', 100)}%)")

        state_tracker["last_state"] = state


class DashboardHandler(SimpleHTTPRequestHandler):
    """Handler server web lokal untuk menyajikan file dashboard dan config."""
    def do_GET(self):
        clean_path = self.path.split("?")[0]
        if clean_path == "/config.json":
            payload = json.dumps({
                "project_id": PROJECT_ID,
                "ws_url": MQTT_WS_URL,
                "lean_threshold_deg": params.lean_threshold_deg,
                "lateral_threshold_deg": params.lateral_threshold_deg,
                "sit_limit_s": params.sit_limit_s,
                "local_ip": get_local_ip(),
                "server_port": SERVER_PORT,
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def log_message(self, *args):
        pass  # Mencegah spam log akses file statis di terminal


def main() -> None:
    local_ip = get_local_ip()
    print("=" * 60)
    print(" SitSmart IoT - Node 3: Detector & Dashboard Server")
    print("=" * 60)
    print(f" * PROJECT_ID : {PROJECT_ID}")
    print(f" * MQTT Broker: {MQTT_HOST}:{MQTT_PORT}")
    print(f" * WebSocket  : {MQTT_WS_URL}")
    print(f" * Ambang bungkuk: >= {params.lean_threshold_deg} derajat (tahan {params.lean_hold_s} dtk)")
    print(f" * Batas duduk   : {params.sit_limit_s} detik")
    print("-" * 60)

    # Inisialisasi MQTT Client (Callback API v2)
    client_id = f"sitsmart-detector-{PROJECT_ID}-{int(time.time())}"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=45)
    except Exception as e:
        print(f"[ERROR] Gagal menyambung ke MQTT broker {MQTT_HOST}:{MQTT_PORT} -> {e}")
        print("Pastikan laptop terhubung ke internet.")
        sys.exit(1)

    client.loop_start()

    # Jalankan background thread evaluasi status
    thread = threading.Thread(target=publish_loop, args=(client,), daemon=True)
    thread.start()

    # Jalankan HTTP Server pada 0.0.0.0 agar bisa diakses seluruh perangkat 1 jaringan
    dashboard_dir = str(ROOT / "dashboard")
    handler = partial(DashboardHandler, directory=dashboard_dir)
    server = ThreadingHTTPServer(("0.0.0.0", SERVER_PORT), handler)

    print(f"[DASHBOARD WEB SERVER]")
    print(f" -> Akses Lokal Laptop  : http://localhost:{SERVER_PORT}")
    print(f" -> Akses Jaringan Sama : http://{local_ip}:{SERVER_PORT}")
    print("=" * 60)
    print("Tekan Ctrl+C untuk menghentikan program.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nMenghentikan detector dan dashboard...")
    finally:
        client.loop_stop()
        server.server_close()
        print("Selesai.")


if __name__ == "__main__":
    main()
