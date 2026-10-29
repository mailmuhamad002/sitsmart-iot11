# SitSmart IoT — Sistem Pemantau Postur Duduk & Perilaku Sedentari Cerdas
### *Praktek Multicommunication 2-Arah dan Multi-Sensor (Mata Kuliah Internet of Things)*

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![MQTT Protocol](https://img.shields.io/badge/MQTT-HiveMQ%20Cloud-orange.svg)](https://www.hivemq.com/)
[![Devices](https://img.shields.io/badge/Architecture-2%20Edge%20%2B%201%20Server-green.svg)]()
[![Tests](https://img.shields.io/badge/Unit%20Tests-17%2F17%20Passed-brightgreen.svg)]()

---

## 📌 1. Latar Belakang & Ide Proyek

Duduk terlalu lama dengan postur membungkuk (*slouching / forward head posture*) atau miring ke salah satu sisi (*lateral lean*) adalah penyebab utama ketegangan otot leher, nyeri punggung bawah (*lower back pain*), dan penurunan produktivitas.

**SitSmart IoT** adalah solusi ergonomi digital cerdas yang memanfaatkan **2 Smartphone** sebagai perangkat *Edge* fisik:
1. **Edge 1 (HP Badan)**: Disimpan di saku kemeja/dada atau diikat di punggung untuk mengukur orientasi kemiringan tulang belakang 3D dan menerima perintah getaran balik jika postur buruk.
2. **Edge 2 (HP Kursi)**: Diletakkan mendatar di atas dudukan kursi untuk memverifikasi apakah pengguna sedang menduduki kursi atau telah berdiri dan meninggalkan kursi.
3. **Node 3 (Laptop - Detector & Dashboard)**: Menggabungkan data dari kedua HP lewat cloud, menjalankan algoritma Sensor Fusion & kalkulasi Indeks Ergonomi, menyajikan dashboard real-time di jaringan lokal (WiFi/hotspot yang sama), dan mengirimkan perintah kendali serta peringatan (*alert*) ke HP.

> 💡 **Orisinalitas (Sesuai Ketentuan Slide 16)**: Proyek ini **BUKAN** PocketGuard (anti-maling meja). SitSmart berfokus pada kesehatan ergonomi dan durasi sedentari dengan algoritma klasifikasi kemiringan spasial 3D, sensor fusion dua node independen, dan aktuasi getaran dua arah.

---

## ✅ 2. Pemenuhan 7 Ketentuan Tugas (Slide 14 & 15)

| No | Ketentuan Tugas (Slide 14) | Implementasi di SitSmart IoT | Status |
|:--:|:---|:---|:---:|
| **1** | **Berkelompok (3 – 4 orang)** | Struktur repository siap pakai untuk kolaborasi kelompok, dilengkapi `PRESENTATION_GUIDE.md` untuk bahan penyusunan slide presentasi PPT. | ✅ **Terpenuhi** |
| **2** | **Minimal 2 Edge Device & 2 Sensor** | • **2 Edge Device**: HP 1 (Badan) dan HP 2 (Kursi).<br>• **2 Sensor Fisik di tiap HP**: **Accelerometer** (percepatan $m/s^2$) + **Gyroscope** (kecepatan putar $rad/s$). | ✅ **Terpenuhi** |
| **3** | **Minimal 2 Jenis Data Processing** | • **Proses 1 (di Edge)**: Low-pass filter EMA gravitasi, Windowed dynamic RMS getaran, dan integrasi numerik giroskop.<br>• **Proses 2 (di Detector)**: 3D Cosine Angle Distance, dekomposisi Pitch/Roll, dan pelacakan durasi duduk statis. | ✅ **Terpenuhi** |
| **4** | **Algoritma AI / Algoritma Lain** | **Multi-Sensor Spatio-Temporal Sensor Fusion Decision Engine** yang dilengkapi *temporal hysteresis* (anti-flutter) dan kalkulasi kontinu **Indeks Kesehatan Ergonomi (Ergonomic Health Score 0–100%)**. | ✅ **Terpenuhi** |
| **5** | **Minimal 1 Protokol Cloud (2-Arah)** | **MQTT Cloud (HiveMQ)** via TCP (Port 1883) & WebSocket TLS (Port 8884).<br>• **Uplink**: Telemetri sensor HP $\to$ Cloud $\to$ Laptop.<br>• **Downlink**: Laptop/Dashboard $\to$ Cloud $\to$ HP 1 bergetar (`termux-vibrate` / Web Audio) & tombol Kalibrasi. | ✅ **Terpenuhi** |
| **6** | **Dashboard 1 Jaringan dengan Pengguna** | Web server lokal dijalankan pada host `0.0.0.0:8000` di laptop, sehingga dapat diakses langsung oleh pengguna di laptop (`http://localhost:8000`) maupun dari smartphone pada hotspot/WiFi yang sama (`http://<IP_LAPTOP>:8000`). | ✅ **Terpenuhi** |
| **7** | **Ide Orisinal (Beda dari Kelompok Lain)** | Ide asli pemantauan ergonomi postur kerja, bukan PocketGuard (anti-maling meja). | ✅ **Terpenuhi** |

---

## 🏗️ 3. Arsitektur Sistem & Komunikasi 2-Arah

```
+-----------------------------------------------------------------------------------+
|                            JARINGAN CLOUD & LOKAL                                 |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [EDGE 1: HP BADAN]                     [EDGE 2: HP KURSI]                        |
|  - Accelerometer + Gyro                 - Accelerometer + Gyro                    |
|  - PROSES 1 (RMS, EMA, Rot)             - PROSES 1 (RMS, EMA, Rot)                |
|  - Sub: sitsmart/.../alerts             - Menentukan ada/tidaknya orang           |
|        |                                      |                                   |
|        | (telemetry)                          | (telemetry)                       |
|        v                                      v                                   |
|  +------------------------------------------------------+                         |
|  |             MQTT CLOUD BROKER (HiveMQ)               |                         |
|  |     broker.hivemq.com (Port 1883 & Port 8884 TLS)    |                         |
|  +------------------------------------------------------+                         |
|        ^                 |                  |                                     |
|        | (downlink alert)| (telemetry)      | (downlink control)                  |
|        v                 v                  v                                     |
|  +------------------------------------------------------+                         |
|  |         NODE 3: LAPTOP DETECTOR (detector.py)        |                         |
|  |  - PROSES 2: 3D Cosine Angle & Ergonomic Score       |                         |
|  |  - ALGORITMA: Spatio-Temporal Sensor Fusion          |                         |
|  |  - Web Server Dashboard (Port 8000)                  |                         |
|  +------------------------------------------------------+                         |
|                          |                                                        |
|                          | HTTP / WebSocket                                       |
|                          v                                                        |
|  +------------------------------------------------------+                         |
|  |              WEB DASHBOARD (dashboard/)              |                         |
|  |  - Grafik real-time sudut condong & getaran          |                         |
|  |  - Status GOOD, SLOUCH, LATERAL_LEAN, BREAK, AWAY    |                         |
|  |  - Tombol Kendali: Kalibrasi, Jeda, Reset, Uji Getar |                         |
|  +------------------------------------------------------+                         |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

### Topik MQTT yang Digunakan:
| Topik MQTT | Arah Aliran | Payload JSON | Keterangan |
|:---|:---:|:---|:---|
| `sitsmart/<PID>/edge/1/telemetry` | HP Badan $\to$ Cloud $\to$ Laptop | `{"rms": 0.04, "gravity": [0,9.8,0], "rot": 0.01}` | Telemetri postur badan tiap 1 detik |
| `sitsmart/<PID>/edge/2/telemetry` | HP Kursi $\to$ Cloud $\to$ Laptop | `{"rms": 0.03, "gravity": [0,0,9.8], "rot": 0.01}` | Telemetri bantalan kursi tiap 1 detik |
| `sitsmart/<PID>/status` | Laptop $\to$ Dashboard | `{"state": "GOOD", "score": 98, "lean_deg": 4.2}` | Status postur berkala (Retained = True) |
| `sitsmart/<PID>/alerts` | Laptop $\to$ HP Badan & Dash | `{"type": "SLOUCH", "risk": 0.85, "reason": "..."}` | **Peringatan 2-Arah**: Memicu getar di HP Badan |
| `sitsmart/<PID>/control` | Dashboard $\to$ Laptop | `{"cmd": "calibrate" \| "reset_timer" \| ...}` | **Kendali 2-Arah**: Mengatur parameter sistem |

---

## 🧠 4. Pengolahan Data & Algoritma

### A. PROSES 1 — Level Edge (Dihitung di setiap HP)
1. **Exponential Moving Average (EMA) Low-Pass Filter**:
   $$\vec{g}_t = \alpha \vec{a}_t + (1 - \alpha) \vec{g}_{t-1} \quad (\alpha = 0.3)$$
   Menghilangkan noise getaran frekuensi tinggi sehingga arah gravitasi bumi stabil.
2. **Windowed Dynamic Root Mean Square (RMS)**:
   $$\text{RMS} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} (\|\vec{a}_i\| - \mu)^2}$$
   Mengukur intensitas gerak dinamis pengguna tanpa terganggu besaran gravitasi statis ($9.81\ m/s^2$).
3. **Integrasi Rotasi Giroskop**:
   $$\Delta \theta = \int_{0}^{\Delta t} \sqrt{\omega_x^2 + \omega_y^2 + \omega_z^2}\, dt$$
   Menghitung akumulasi perubahan sudut rotasi tubuh.

### B. PROSES 2 — Level Central (Dihitung di Laptop Detector)
1. **3D Spatial Vector Cosine Distance**:
   $$\cos(\theta) = \frac{\vec{g}_{\text{body}} \cdot \vec{g}_{\text{baseline}}}{\|\vec{g}_{\text{body}}\| \|\vec{g}_{\text{baseline}}\|}, \quad \theta = \arccos(\text{clip}(\cos\theta, -1, 1))$$
   Mengukur sudut kemiringan absolut tulang belakang terhadap posisi tegak yang telah dikalibrasi.
2. **Dekomposisi Sudut (Pitch & Roll)**:
   Membedakan membungkuk ke depan (*pitch*) atau miring bersandar ke sisi samping (*roll*).
3. **Akumulasi Waktu Duduk Statis ($still\_s$)**:
   Menghitung durasi tanpa perubahan posisi atau pergerakan.

### C. ALGORITMA — Multi-Sensor Spatio-Temporal Sensor Fusion
Mesin status (*State Machine*) menggabungkan sinyal dari kedua HP secara simultan:
- **`GOOD`**: Pengguna duduk tegak ($\theta < 20^\circ$) dengan postur baik.
- **`SLOUCH`**: Badan condong ke depan $\ge 20^\circ$ selama $\ge 5$ detik $\to$ HP 1 bergetar.
- **`LATERAL_LEAN`**: Badan miring ke samping $\ge 20^\circ$ selama $\ge 5$ detik $\to$ HP 1 bergetar.
- **`BREAK`**: Tidak ada pergerakan selama $\ge 30$ menit $\to$ HP 1 dan dashboard memberi alarm peregangan.
- **`AWAY`**: HP Badan mendeteksi berjalan ($\text{RMS} \ge 1.2$), sementara HP Kursi diam ($\text{RMS} \le 0.18$) $\to$ status berubah menjadi istirahat aktif. Jika pergi $\ge 60$ detik, timer duduk direset ke nol.
- **`COMMON_MOTION`**: Kedua HP mendeteksi guncangan tinggi bersamaan (misal meja terbentur) $\to$ alarm diabaikan untuk mencegah *false alarm*.
- **`Indeks Kesehatan Ergonomi (0–100%)`**: Algoritma skor kontinu yang memberikan penalti proporsional terhadap deviasi sudut kemiringan dan durasi duduk tanpa istirahat.

---

## 📁 5. Struktur Folder Proyek

```
sitsmart-iot/
├── .env.example             <- Template konfigurasi MQTT dan ambang batas
├── .env                     <- Konfigurasi aktif (PROJECT_ID, MQTT host, batas sudut)
├── requirements.txt         <- Dependensi Python (paho-mqtt)
├── detector.py              <- NODE 3: Backend Detector & Web Server Dashboard
├── edge.py                  <- Core Edge Client Python (Termux / Simulator)
├── edge_badan.py            <- Shortcut peluncur HP 1 (Badan)
├── edge_kursi.py            <- Shortcut peluncur HP 2 (Kursi)
├── run_detector.bat         <- Script 1-klik jalankan detector di Windows
├── run_simulator.bat        <- Script 1-klik jalankan simulator di Windows
├── PRESENTATION_GUIDE.md    <- Panduan lengkap penyusunan slide PPT sesuai rubrik
├── README.md                <- Dokumentasi utama proyek
│
├── dashboard/
│   └── index.html           <- Antarmuka web dashboard (SVG chart live, kontrol 2-arah)
│
├── web-edge/
│   ├── index.html           <- Web Edge Client (PWA tanpa Termux, iOS Safari & Android)
│   └── index1.html          <- Salinan kompatibilitas file web edge
│
├── scripts/
│   └── simulate.py          <- Simulator skenario interaktif untuk pengujian/demo
│
├── shared/
│   ├── __init__.py
│   └── processing.py        <- Modul murni Python: Proses 1, Proses 2 & Algoritma Fusion
│
└── tests/
    └── test_processing.py   <- 17 Unit test otomatis untuk verifikasi algoritma
```

---

## 🚀 6. Panduan Menjalankan Sistem

### Langkah 1: Persiapan di Laptop (Node 3)
1. Buka terminal / Command Prompt / PowerShell:
   ```bash
   cd c:\Users\ACER\Documents\IoT\sitsmart-iot
   py -m pip install -r requirements.txt
   ```
2. Pastikan file `.env` memiliki `PROJECT_ID` yang unik, misalnya:
   ```ini
   PROJECT_ID=sitsmart_kelompok_07
   MQTT_HOST=broker.hivemq.com
   MQTT_PORT=1883
   LEAN_THRESHOLD_DEG=20.0
   SIT_LIMIT_S=1800.0
   ```
3. Jalankan Detector:
   ```bash
   py detector.py
   # atau klik dua kali file run_detector.bat
   ```
4. Buka browser di laptop: **`http://localhost:8000`**.
   *(Jika ingin membuka dari HP di jaringan WiFi yang sama, gunakan alamat `http://<IP_LAPTOP>:8000`)*.

---

### Langkah 2: Menjalankan 2 Edge Device (Pilih Salah Satu Metode)

#### 📱 METODE A: Menggunakan Browser HP (Paling Praktis / Tanpa Install)
1. Letakkan folder `web-edge/` pada hosting HTTPS (misalnya gratis di **Netlify Drop**, **GitHub Pages**, atau **Vercel**). Browser memerlukan HTTPS untuk mengaktifkan sensor gerak.
2. Buka URL tersebut di **kedua HP**:
   - **HP A (Badan)**: Pilih peran `Edge 1 · HP Badan`. Masukkan saku dada atau tempelkan di punggung.
   - **HP B (Kursi)**: Pilih peran `Edge 2 · HP Kursi`. Taruh mendatar di atas bantalan kursi.
3. Samakan `PROJECT_ID` dengan yang ada di `.env` laptop (misal `sitsmart_kelompok_07`).
4. Tekan tombol **Mulai Membaca Sensor** dan beri izin sensor gerak (*DeviceMotion*).

---

#### 📲 METODE B: Menggunakan Termux di Android (Sesuai Slide 25–31)
1. Install **Termux** dan **Termux:API** dari F-Droid di kedua HP.
2. Di dalam Termux kedua HP, jalankan:
   ```bash
   pkg update
   pkg install python git termux-api
   pip install paho-mqtt
   ```
3. Copy folder `sitsmart-iot` ke Termux, lalu jalankan:
   - Di **HP A (Badan)**:
     ```bash
     python edge_badan.py
     ```
   - Di **HP B (Kursi)**:
     ```bash
     python edge_kursi.py
     ```
4. HP 1 (Badan) akan otomatis mendengarkan topik alert dan memicu `termux-vibrate` saat postur membungkuk terdeteksi.

---

#### 💻 METODE C: Simulator Interaktif (Untuk Pengujian & Rehearsal Presentasi)
Jika ingin menguji seluruh alur sistem tanpa memerlukan 2 HP fisik:
1. Di terminal baru, jalankan:
   ```bash
   py scripts/simulate.py
   # atau klik dua kali file run_simulator.bat
   ```
2. Tekan angka di keyboard untuk mengubah kondisi postur secara live:
   - `1` : Duduk Tegak Normal (`GOOD`)
   - `2` : Membungkuk ke Depan (`SLOUCH` $\to$ Memicu Alarm)
   - `3` : Miring ke Samping (`LATERAL_LEAN`)
   - `4` : Berdiri & Pergi (`AWAY`)
   - `5` : Guncang Meja Bersama (`COMMON_MOTION`)

---

## 🧪 7. Prosedur Uji Coba Demo (Demo Script)

Ikuti urutan langkah berikut saat melakukan demonstrasi atau perekaman video:
1. **Kalibrasi Awal**:
   - Duduk tegak ergonomis menghadap meja.
   - Buka dashboard di `http://localhost:8000`, klik tombol **Kalibrasi Postur Tegak**.
   - Indikator berubah menjadi `Terkalibrasi Tegak`, status menjadi **`POSTUR TEGAK (BAIK)`**, sudut condong $\approx 0^\circ$, dan Skor Ergonomi = $100\%$.
2. **Uji Kasus Membungkuk (SLOUCH)**:
   - Bungkukkan badan ke depan (sudut $\ge 20^\circ$) selama $> 5$ detik.
   - Status di dashboard berubah merah: **`MEMBUNGKUK!`**, skor ergonomi menurun, dan HP 1 (Badan) seketika bergetar dan membunyikan peringatan suara.
3. **Uji Pemulihan (Recovery)**:
   - Tegakkan kembali badan Anda.
   - Dalam 1 detik, status pulih ke **`POSTUR TEGAK (BAIK)`** dan getaran alarm berhenti.
4. **Uji Meninggalkan Kursi (AWAY)**:
   - Berdirilah dan berjalan beberapa langkah (HP Badan aktif bergerak, HP Kursi diam di kursi).
   - Dashboard menampilkan status biru: **`ISTIRAHAT AKTIF (AWAY)`**.
5. **Uji Guncangan Meja (COMMON_MOTION)**:
   - Ketuk atau gebrak meja dengan cukup keras.
   - Status menjadi kuning: **`GUNCANGAN BERSAMA`**, membuktikan sistem cerdas memfilter false alarm.
6. **Uji Komunikasi 2-Arah**:
   - Klik tombol ungu **Uji Getar 2-Arah ke HP** di dashboard.
   - Perintah dikirim via MQTT Cloud ke HP 1, membuktikan aktuasi dua arah berjalan sempurna.

---

## 🔬 8. Menjalankan Unit Test Otomatis

Proyek dilengkapi dengan 17 unit test yang mencakup pengujian filter EMA, integrasi giroskop, dekomposisi sudut spasial, skor ergonomi, dan seluruh transisi state machine:

```bash
py -m unittest discover -s tests
```

Output:
```
.................
----------------------------------------------------------------------
Ran 17 tests in 0.002s

OK
```

---

## 👥 9. Tim Pengembang & Identitas Tugas
- **Mata Kuliah**: Internet of Things (IoT)
- **Topik**: Praktek Multicommunication 2-Arah dan Multi-Sensor
- **Tautan PPT & Panduan Presentasi**: Lihat file [PRESENTATION_GUIDE.md](file:///c:/Users/ACER/Documents/IoT/sitsmart-iot/PRESENTATION_GUIDE.md)
- **Lisensi**: MIT License
