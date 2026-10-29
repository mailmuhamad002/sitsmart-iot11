# Panduan Dokumentasi Presentasi PPT - SitSmart IoT

Dokumen ini disusun khusus untuk mempermudah penyusunan **Slide Presentasi (PPT)** tugas besar mata kuliah Internet of Things, mengacu langsung pada rubrik penilaian pada **Slide 15**:
1. Ide & Orisinalitas (Bobot 20%)
2. Arsitektur: 2 edge, 2 sensor, satu jaringan (Bobot 15%)
3. Data Processing (min. 2 jenis) & Algoritma / AI (Bobot 20%)
4. Komunikasi ke Cloud (Bobot 15%)
5. Pengujian & Demo (Bobot 15%)
6. Dokumentasi & Kode di GitHub (Bobot 15%)

---

## 📑 Struktur Slide Presentasi yang Disarankan (10 - 12 Slide)

### Slide 1: Judul & Anggota Kelompok
- **Judul Proyek**: SitSmart IoT — Sistem Cerdas Pemantau Postur & Perilaku Sedentari Berbasis Multi-Sensor & Komunikasi 2-Arah
- **Mata Kuliah**: Internet of Things (IoT)
- **Nama Kelompok**: [Nama Kelompok / Kelas]
- **Anggota Kelompok**:
  1. [Nama Anggota 1] - [NIM] - *Peran: Edge & Sensor Programming*
  2. [Nama Anggota 2] - [NIM] - *Peran: Cloud Architecture & MQTT*
  3. [Nama Anggota 3] - [NIM] - *Peran: Data Processing & Algoritma AI*
  4. [Nama Anggota 4] - [NIM] - *Peran: Web Dashboard & Testing*
- **Tautan Repository GitHub**: `https://github.com/[username]/sitsmart-iot`

---

### Slide 2: Latar Belakang & Masalah
- **Masalah Nyata**:
  - Gaya hidup sedentari di kalangan mahasiswa dan pekerja kantoran (duduk statis > 8 jam/hari).
  - Kebiasaan postur membungkuk (*forward head posture / slouching*) dan miring ke satu sisi (*lateral lean*) memicu sakit leher, nyeri punggung bawah (*lower back pain*), dan kelainan tulang belakang.
  - Orang sering tidak sadar telah duduk diam berjam-jam tanpa peregangan atau jeda aktif.
- **Tujuan Solusi**:
  - Membangun asisten ergonomi real-time yang murah tanpa hardware mahal tambahan, memanfaatkan smartphone yang sudah dimiliki pengguna.

---

### Slide 3: Ide Solusi & Orisinalitas (Bobot 20%)
- **Konsep SitSmart IoT**:
  - Menggunakan **2 Smartphone Android/iOS** sebagai *Edge Devices*:
    - **Edge 1 (HP Badan)**: Disimpan di saku kemeja/dada atau diikat di punggung atas untuk mengukur orientasi kemiringan tulang belakang secara spasial 3D.
    - **Edge 2 (HP Kursi)**: Diletakkan mendatar di atas bantalan kursi untuk mengonfirmasi keberadaan fisik pengguna di tempat duduk.
- **Tabel Orisinalitas (Beda dengan Contoh Dosen: PocketGuard)**:
  | Aspek | PocketGuard (Contoh Dosen) | SitSmart IoT (Proyek Kami) |
  |-------|----------------------------|----------------------------|
  | **Tujuan** | Keamanan meja (anti-maling HP) | Kesehatan ergonomis & durasi duduk |
  | **Posisi Sensor** | Kedua HP ditaruh berdampingan di meja | 1 HP di badan pengguna + 1 HP di kursi |
  | **Sensor Dipakai** | Getaran accelerometer + rotasi | Gravitasi statis 3D + RMS dinamis + Giroskop |
  | **Logika Fusion** | HP A gerak & HP B diam = Maling | HP Badan condong + HP Kursi terisi = Bungkuk |
  | **Aktuasi 2-Arah** | HP B (pemilik) bergetar | HP Badan bergetar + suara beep menyuruh tegak |

---

### Slide 4: Arsitektur Sistem 2 Edge & Satu Jaringan (Bobot 15%)
- **Diagram 4 Kotak Standar IoT**:
  1. **Sensor + Edge**: 2 HP Android (Membaca sensor fisik & memproses fitur sinyal per 1 detik).
  2. **Jaringan**: WiFi / Hotspot lokal yang menghubungkan Laptop dan kedua HP.
  3. **Cloud**: Broker MQTT Publik HiveMQ (`broker.hivemq.com`) via port 1883 & 8884 (WebSocket).
  4. **Dashboard**: Web server lokal di Laptop (`0.0.0.0:8000`) yang dapat dibuka di laptop maupun dari smartphone di jaringan WiFi/hotspot yang sama.
- **Bagan Arsitektur Data Flow**:
  ```
  [HP 1: Badan]  --(Telemetry Uplink)--> [HiveMQ Cloud] <--(Telemetry Uplink)-- [HP 2: Kursi]
        ^                                       |
        |--(Alert Downlink: Getar/Suara)--------|
                                                v
                                     [Laptop Node 3: Detector]
                                      (Sensor Fusion + Score)
                                           ^         |
                         (Control Uplink)  |         v (Status Retained)
                                   [Web Dashboard Server :8000]
                                   (Satu Jaringan WiFi Pengguna)
  ```

---

### Slide 5: Sensor Fisik & Edge Device (Bobot 15%)
- **Spesifikasi Sensor di Setiap HP**:
  1. **Tri-axial Accelerometer ($m/s^2$)**: Mengukur gaya gravitasi statis bumi ($9.81\ m/s^2$) dan getaran dinamis pengguna.
  2. **Tri-axial Gyroscope ($rad/s$)**: Mengukur kecepatan sudut perubahan orientasi tubuh saat berganti posisi duduk.
- **Fleksibilitas Implementasi Edge**:
  - **Opsi Termux (Python CLI)**: Membaca sensor native Android menggunakan `termux-sensor` dan aktuasi getar via `termux-vibrate`.
  - **Opsi Web Edge (PWA / Mobile Browser)**: Membaca `DeviceMotionEvent` HTML5 di browser Chrome Android atau Safari iOS tanpa instalasi aplikasi.

---

### Slide 6: Data Processing (Min. 2 Jenis) (Bobot 20%)
- **PROSES 1: Level Edge (HP Badan & HP Kursi)**
  1. *Exponential Moving Average (EMA) Low-Pass Filter*:
     $$\vec{g}_t = \alpha \vec{a}_t + (1 - \alpha) \vec{g}_{t-1}$$
     Menyaring spike getaran sesaat sehingga vektor gravitasi murni $\vec{g} = [g_x, g_y, g_z]$ stabil.
  2. *Windowed Root Mean Square (RMS) Getaran Dinamis*:
     $$\text{RMS} = \sqrt{\frac{1}{N}\sum_{i=1}^{N}(m_i - \bar{m})^2}$$
     Memisahkan energi gerak dinamis tanpa pengaruh gravitasi. HP diam $\approx 0.02\ m/s^2$, berjalan $\ge 1.2\ m/s^2$.
  3. *Integrasi Numerik Giroskop*: Akumulasi sudut rotasi $\Delta \theta = \int \|\vec{\omega}\| dt$.

- **PROSES 2: Level Central (Laptop Detector)**
  1. *3D Spatial Vector Cosine Distance*:
     $$\cos(\theta) = \frac{\vec{g}_{\text{body}} \cdot \vec{g}_{\text{ref}}}{\|\vec{g}_{\text{body}}\| \|\vec{g}_{\text{ref}}\|}, \quad \theta = \arccos(\cos\theta)$$
     Menghitung sudut deviasi kemiringan tulang punggung terhadap posisi tegak hasil kalibrasi.
  2. *Dekomposisi Sudut 3D (Pitch & Roll)*:
     Membedakan antara membungkuk ke depan (*pitch*) atau miring bersandar ke lengan kursi (*roll*).
  3. *Pelacakan Waktu Duduk Statis*: Akumulasi durasi tanpa pergerakan kursi/badan.

---

### Slide 7: Algoritma AI & Sensor Fusion (Bobot 20%)
- **Multi-Sensor Spatio-Temporal State Machine**:
  - Matriks Keputusan Sensor Fusion:
    | Kondisi HP Badan (Edge 1) | Kondisi HP Kursi (Edge 2) | Waktu Tahan | Status Akhir | Tindakan Sistem |
    |---------------------------|---------------------------|-------------|--------------|-----------------|
    | $\theta < 20^\circ$ (Tegak) | Diam (Terisi) | Kontinu | **`GOOD`** | Postur ideal, skor 100% |
    | $\theta \ge 20^\circ$ (Condong depan) | Diam (Terisi) | $\ge 5$ detik | **`SLOUCH`** | Alert ke HP 1 (Getar + Beep) |
    | $\theta \ge 20^\circ$ (Miring samping) | Diam (Terisi) | $\ge 5$ detik | **`LATERAL_LEAN`** | Alert miring ke HP 1 |
    | Diam statis | Diam statis | $\ge 30$ menit | **`BREAK`** | Peringatan berdiri & peregangan |
    | RMS $\ge 1.2$ (Jalan) | RMS $\le 0.18$ (Kursi kosong) | $\ge 3$ detik | **`AWAY`** | Istirahat aktif, timer reset jika $\ge 60$ dtk |
    | RMS $\ge 1.2$ (Guncang) | RMS $\ge 1.2$ (Guncang) | Sesaat | **`COMMON_MOTION`**| Guncangan meja (diabaikan) |
- **Algoritma Indeks Kesehatan Ergonomi (Ergonomic Health Score 0-100%)**:
  Menghitung penalti dinamis berbobot berdasarkan derajat keparahan condong dan durasi duduk tanpa jeda.

---

### Slide 8: Komunikasi Cloud & Multicommunication 2-Arah (Bobot 15%)
- **Protokol**: MQTT v5 / v3.1.1 (TCP Port 1883 & WebSocket Port 8884 TLS).
- **Struktur Topik MQTT**:
  | Topik | Arah Aliran | Payload | Fungsi |
  |-------|-------------|---------|--------|
  | `sitsmart/<PID>/edge/1/telemetry` | HP 1 $\to$ Cloud $\to$ Laptop | `{rms, rot, gravity}` | Telemetri getaran & postur badan |
  | `sitsmart/<PID>/edge/2/telemetry` | HP 2 $\to$ Cloud $\to$ Laptop | `{rms, rot, gravity}` | Telemetri keberadaan di kursi |
  | `sitsmart/<PID>/status` | Laptop $\to$ Dashboard | `{state, score, lean, ...}` | Update status live (Retained = True) |
  | `sitsmart/<PID>/alerts` | Laptop $\to$ HP 1 & Dashboard | `{type, risk, reason}` | **Downlink Alert**: Menggetarkan HP 1 |
  | `sitsmart/<PID>/control` | Dashboard $\to$ Laptop | `{cmd: calibrate\|reset...}` | **Downlink Control**: Remote Kalibrasi |

---

### Slide 9: Tampilan Web Dashboard & Fitur Interaktif
- **Tampilan Real-Time**:
  - Status Postur Besar (Badge warna: Hijau, Kuning, Merah).
  - Gauge Indeks Kesehatan Ergonomi (0 - 100%).
  - Kartu Metrik Edge 1 (Badan) dan Edge 2 (Kursi) dengan status Online/Offline.
  - Grafik SVG Live Kemiringan Sudut Tulang Belakang (0-60°) dengan Garis Ambang Batas 20°.
  - Riwayat tabel peringatan alert.
- **Tombol Kendali 2-Arah**:
  - Tombol **Kalibrasi**: Mengunci postur tegak tubuh saat ini sebagai acuan nol.
  - Tombol **Jeda Monitoring**: Menunda sistem saat ingin berbaring atau istirahat.
  - Tombol **Reset Timer Duduk**: Mengulang hitungan waktu duduk dari awal.
  - Tombol **Uji Getar 2-Arah**: Menguji sinyal getar ke HP 1 secara instan untuk demonstrasi kepada dosen.

---

### Slide 10: Pengujian, Hasil Demo & Skenario Kasus Uji (Bobot 15%)
- **Skenario Pengujian yang Dijalankan**:
  1. *Uji Kalibrasi*: Duduk tegak $\to$ tekan kalibrasi $\to$ status berubah dari `CALIBRATE` ke `GOOD` (Sudut $\approx 0^\circ$).
  2. *Uji Slouch*: Membungkuk $30^\circ$ selama 5 detik $\to$ status berubah menjadi `SLOUCH` $\to$ HP 1 bergetar seketika.
  3. *Uji Recovery*: Kembali menegakkan badan $\to$ status langsung pulih ke `GOOD` dan getaran berhenti.
  4. *Uji Berdiri (Away)*: Pengguna berdiri dan berjalan $\to$ HP 1 mendeteksi RMS $> 1.2$, kursi diam $\to$ status `AWAY`.
  5. *Uji Guncangan Meja*: Meja dipukul/digebrak $\to$ kedua HP mendeteksi RMS $> 1.2$ bersamaan $\to$ `COMMON_MOTION` (tidak memicu false alarm).
  6. *Uji Unit Test Otomatis*: 17 skenario test case di Python lulus 100% (`OK`).

---

### Slide 11: Kesimpulan & Keunggulan
- **Kesimpulan**:
  - Berhasil menerapkan komunikasi dua arah (*Multicommunication 2-Arah*) dan *Multi-Sensor* (Accelerometer + Gyroscope pada 2 Edge Device).
  - Mengimplementasikan 2 proses pengolahan data (sinyal edge + geometri 3D spasial) dan algoritma Sensor Fusion dengan Indeks Kesehatan Ergonomi.
  - Sistem sangat aplikatif, hemat biaya, dan memberikan dampak nyata bagi kesehatan kerja/belajar sehari-hari.
- **Dokumentasi & Demo**:
  - Link Video Demo: `[Link YouTube / Google Drive Demo]`
  - Link Source Code GitHub: `[Link GitHub]`
