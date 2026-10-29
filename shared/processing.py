"""Pengolahan data dan Algoritma Sensor Fusion SitSmart IoT.

Kategori Pengolahan Data:
  1. PROSES 1 (Edge Level - HP Badan & HP Kursi):
     - window_rms: Mengukur energi getaran dinamis tanpa pengaruh gravitasi statis.
     - mean_vector: Rata-rata komponen vektor [x, y, z] untuk estimasi orientasi gravitasi.
     - apply_ema: Exponential Moving Average (Low-Pass Filter) untuk meredam derau sensor.
     - integrate_rotation: Integrasi numerik laju rotasi giroskop ke akumulasi radian.

  2. PROSES 2 (Central Level - Laptop / Detector):
     - angle_between: Menghitung sudut 3D antara vektor gravitasi saat ini dengan acuan tegak.
     - decompose_tilt: Memisahkan sudut kemiringan menjadi pitch (depan/belakang) dan roll (samping).
     - calculate_ergonomic_score: Menghitung indeks kesehatan postur (0-100%).

  3. ALGORITMA (Multi-Sensor Spatio-Temporal Sensor Fusion State Machine):
     - Menggabungkan data dari HP Badan (Edge 1) dan HP Kursi (Edge 2).
     - Menentukan status: GOOD, SLOUCH, LATERAL_LEAN, BREAK, AWAY, COMMON_MOTION, CALIBRATE, OFFLINE, PAUSED.
     - Dilengkapi temporal hysteresis (anti-flutter) dan pelacakan durasi duduk.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence


# =====================================================================
# PROSES 1: EKSTRAKSI FITUR SINYAL & FILTERING (DI EDGE)
# =====================================================================

def window_rms(magnitudes: Sequence[float]) -> float:
    """Menghitung RMS deviasi getaran/gerak dari rata-rata (menghilangkan komponen gravitasi).
    
    HP diam: RMS ~ 0.01 - 0.08 m/s^2.
    HP bergerak/duduk gelisah: RMS ~ 0.25 - 0.60 m/s^2.
    HP berdiri/berjalan: RMS >= 1.20 m/s^2.
    """
    n = len(magnitudes)
    if n == 0:
        return 0.0
    mean_val = sum(magnitudes) / n
    variance = sum((m - mean_val) ** 2 for m in magnitudes) / n
    return math.sqrt(variance)


def mean_vector(vectors: Sequence[Sequence[float]]) -> list[float]:
    """Rata-rata komponen vektor [x, y, z] dalam satu jendela waktu."""
    n = len(vectors)
    if n == 0:
        return [0.0, 0.0, 0.0]
    return [sum(v[i] for v in vectors) / n for i in range(3)]


def apply_ema(current: Sequence[float], previous: Optional[Sequence[float]], alpha: float = 0.25) -> list[float]:
    """Low-pass filter berbasis Exponential Moving Average (EMA).
    
    Menyaring spike/noise instan sehingga orientasi gravitasi stabil.
    Formula: y[t] = alpha * x[t] + (1 - alpha) * y[t-1]
    """
    if previous is None:
        return [float(x) for x in current[:3]]
    alpha = max(0.01, min(1.0, alpha))
    return [
        float(alpha * current[i] + (1.0 - alpha) * previous[i])
        for i in range(min(3, len(current), len(previous)))
    ]


def integrate_rotation(rates: Sequence[tuple[float, float, float]], dt: float) -> float:
    """Integrasi numerik total rotasi angular (radian) dari giroskop over dt."""
    if not rates or dt <= 0:
        return 0.0
    tot = 0.0
    for gx, gy, gz in rates:
        tot += math.sqrt(gx * gx + gy * gy + gz * gz)
    return (tot / len(rates)) * dt


# =====================================================================
# PROSES 2: GEOMETRI SPASIAL & INDEKS ERGONOMI (DI DETECTOR)
# =====================================================================

def vector_magnitude(v: Sequence[float]) -> float:
    """Norma Euclidean 3D: sqrt(x^2 + y^2 + z^2)."""
    return math.sqrt(sum(x * x for x in v[:3]))


def angle_between(a: Sequence[float], b: Sequence[float]) -> float:
    """Menghitung sudut spasial 3D (derajat) antara dua vektor arah gravitasi.
    
    cos(theta) = (a . b) / (||a|| * ||b||)
    """
    na = vector_magnitude(a)
    nb = vector_magnitude(b)
    if na < 1e-6 or nb < 1e-6:
        return 0.0
    dot = sum(x * y for x, y in zip(a[:3], b[:3]))
    cos_theta = dot / (na * nb)
    clipped = max(-1.0, min(1.0, cos_theta))
    return math.degrees(math.acos(clipped))


def decompose_tilt(current: Sequence[float], baseline: Sequence[float]) -> dict:
    """Dekomposisi kemiringan menjadi sudut 3D total, pitch (depan/belakang), dan roll (samping)."""
    total_deg = angle_between(current, baseline)
    
    dx = current[0] - baseline[0] if len(current) > 0 and len(baseline) > 0 else 0.0
    dy = current[1] - baseline[1] if len(current) > 1 and len(baseline) > 1 else 0.0
    dz = current[2] - baseline[2] if len(current) > 2 and len(baseline) > 2 else 0.0
    
    # Estimasi sudut angular orientasi
    pitch_approx = math.degrees(math.atan2(dz, max(1e-3, abs(current[1])))) if len(current) > 2 else 0.0
    roll_approx = math.degrees(math.atan2(dx, max(1e-3, abs(current[1])))) if len(current) > 1 else 0.0
    
    return {
        "total_deg": round(total_deg, 1),
        "pitch_deg": round(pitch_approx, 1),
        "roll_deg": round(roll_approx, 1),
    }


def calculate_ergonomic_score(
    lean_deg: Optional[float],
    still_s: float,
    lean_threshold: float = 20.0,
    sit_limit: float = 1800.0,
) -> int:
    """Algoritma penentuan Indeks Kesehatan Postur (Ergonomic Health Score 0 - 100%).
    
    Memberikan penalti berdasarkan:
    1. Deviasi sudut dari tegak: sudut > 10 derajat mulai mengurangi skor.
    2. Lama waktu duduk statis: jika melebihi 50% dari batas durasi, skor menurun bertahap.
    """
    score = 100.0

    if lean_deg is not None:
        if lean_deg > 10.0:
            lean_excess = lean_deg - 10.0
            penalty_lean = min(50.0, (lean_excess / max(1.0, lean_threshold - 10.0)) * 35.0)
            score -= penalty_lean

    if sit_limit > 0:
        half_limit = sit_limit * 0.5
        if still_s > half_limit:
            time_excess = still_s - half_limit
            penalty_time = min(40.0, (time_excess / half_limit) * 40.0)
            score -= penalty_time

    return int(max(0, min(100, round(score))))


# =====================================================================
# ALGORITMA: SENSOR FUSION DECISION ENGINE
# =====================================================================

@dataclass
class Params:
    """Parameter ambang batas deteksi postur dan ergonomi."""
    lean_threshold_deg: float = 20.0     # Condong >= 20 deg = indikasi membungkuk
    lateral_threshold_deg: float = 20.0  # Miring samping >= 20 deg = sandaran satu sisi
    lean_hold_s: float = 5.0             # Durasi tahan condong sebelum memicu alert
    move_rms: float = 0.30               # RMS >= 0.30 dihitung ada gerakan mikro/peregangan
    walk_rms: float = 1.20               # RMS >= 1.20 terdeteksi gerakan berdiri/jalan
    still_rms: float = 0.18              # RMS <= 0.18 dianggap diam stabil
    away_hold_s: float = 3.0             # Durasi gerak HP badan sementara kursi diam -> AWAY
    sit_limit_s: float = 1800.0          # Batas waktu duduk tanpa berdiri (default 30 menit)
    break_reset_s: float = 60.0          # Berdiri >= 60 detik mereset timer akumulasi duduk
    stale_s: float = 5.0                 # Batas waktu telemetri tidak diterima -> OFFLINE


@dataclass
class Sample:
    """Representasi data telemetri yang diterima dari edge device."""
    t: float
    rms: float
    gravity: list[float]
    rot: float = 0.0


@dataclass
class PostureEngine:
    """Mesin keputusan Sensor Fusion untuk pemantauan postur 2-Edge."""
    params: Params = field(default_factory=Params)
    baseline: Optional[list[float]] = None
    monitoring: bool = True
    body: Optional[Sample] = None
    seat: Optional[Sample] = None

    _recent_gravity: list[list[float]] = field(default_factory=list)
    _slouch_since: Optional[float] = None
    _lateral_since: Optional[float] = None
    _away_since: Optional[float] = None
    _last_move: Optional[float] = None
    _sit_start: Optional[float] = None

    def feed(self, edge: int, sample: Sample) -> None:
        """Memasukkan data telemetri dari Edge 1 (Badan) atau Edge 2 (Kursi)."""
        if edge == 1:
            self.body = sample
            self._recent_gravity.append(sample.gravity)
            if len(self._recent_gravity) > 8:
                self._recent_gravity.pop(0)

            if self._last_move is None:
                self._last_move = sample.t
            if sample.rms >= self.params.move_rms:
                self._last_move = sample.t
        elif edge == 2:
            self.seat = sample

    def calibrate(self) -> bool:
        """Menyimpan postur tegak saat ini sebagai acuan kalibrasi (vektor baseline)."""
        if not self._recent_gravity:
            return False
        self.baseline = mean_vector(self._recent_gravity)
        self._slouch_since = None
        self._lateral_since = None
        return True

    def reset_timer(self, now: float) -> None:
        """Mereset timer duduk dan timer gerak."""
        self._last_move = now
        self._sit_start = now
        self._away_since = None

    def evaluate(self, now: float) -> dict:
        """Mengevaluasi kondisi sensor fusion saat ini dan menghasilkan keputusan."""
        p = self.params
        body_ok = self.body is not None and (now - self.body.t) <= p.stale_s
        seat_ok = self.seat is not None and (now - self.seat.t) <= p.stale_s

        lean = None
        tilt_decomp = None
        if body_ok and self.baseline is not None:
            tilt_decomp = decompose_tilt(self.body.gravity, self.baseline)
            lean = tilt_decomp["total_deg"]

        still_s = (now - self._last_move) if self._last_move is not None else 0.0
        sit_s = (now - self._sit_start) if self._sit_start is not None else 0.0

        def result(state: str, reason: str, risk: float) -> dict:
            score = calculate_ergonomic_score(lean, still_s, p.lean_threshold_deg, p.sit_limit_s)
            return {
                "state": state,
                "reason": reason,
                "risk": round(max(0.0, min(1.0, risk)), 2),
                "score": score,
                "lean_deg": lean,
                "pitch_deg": tilt_decomp["pitch_deg"] if tilt_decomp else None,
                "roll_deg": tilt_decomp["roll_deg"] if tilt_decomp else None,
                "still_s": round(still_s, 1),
                "sit_s": round(sit_s, 1),
                "monitoring": self.monitoring,
                "calibrated": self.baseline is not None,
            }

        # Status kontrol
        if not self.monitoring:
            return result("PAUSED", "Monitoring dijeda pengguna", 0.0)

        # Status konektivitas
        if not body_ok or not seat_ok:
            offline_list = []
            if not body_ok:
                offline_list.append("HP Badan (Edge 1)")
            if not seat_ok:
                offline_list.append("HP Kursi (Edge 2)")
            return result("OFFLINE", f"Menunggu data dari {' & '.join(offline_list)}", 0.0)

        # Status kalibrasi
        if self.baseline is None:
            return result("CALIBRATE", "Duduk tegak, lalu tekan tombol Kalibrasi", 0.0)

        body, seat = self.body, self.seat

        # Kondisi 1: Guncangan bersama (Common Motion) - misal meja tersenggol
        if body.rms >= p.walk_rms and seat.rms >= p.walk_rms:
            self._away_since = None
            return result("COMMON_MOTION", "Kedua HP mengalami guncangan bersama (diabaikan)", 0.0)

        # Kondisi 2: Pengguna berdiri dan berjalan (HP Badan aktif, HP Kursi diam)
        if body.rms >= p.walk_rms and seat.rms <= p.still_rms:
            if self._away_since is None:
                self._away_since = now
        else:
            # Jika baru kembali dari berdiri cukup lama (>= break_reset_s), reset timer duduk
            if self._away_since is not None and (now - self._away_since) >= p.break_reset_s:
                self._sit_start = now
                self._last_move = now
            self._away_since = None

        if self._away_since is not None and (now - self._away_since) >= p.away_hold_s:
            self._last_move = now
            if (now - self._away_since) >= p.break_reset_s:
                self._sit_start = None
            return result("AWAY", "Pengguna berdiri / meninggalkan kursi (istirahat aktif)", 0.0)

        if self._sit_start is None:
            self._sit_start = now

        # Kondisi 3: Evaluasi kemiringan postur (Membungkuk vs Miring Samping)
        if lean is not None and lean >= p.lean_threshold_deg:
            is_lateral = tilt_decomp and abs(tilt_decomp["roll_deg"]) > abs(tilt_decomp["pitch_deg"])
            if is_lateral:
                if self._lateral_since is None:
                    self._lateral_since = now
                held_lateral = now - self._lateral_since
                if held_lateral >= p.lean_hold_s:
                    risk = min(1.0, lean / (2.0 * p.lateral_threshold_deg))
                    return result(
                        "LATERAL_LEAN",
                        f"Badan miring ke samping {lean:.0f} derajat selama {held_lateral:.0f} detik",
                        risk
                    )
            else:
                self._lateral_since = None
                if self._slouch_since is None:
                    self._slouch_since = now
                held_slouch = now - self._slouch_since
                if held_slouch >= p.lean_hold_s:
                    risk = min(1.0, lean / (2.0 * p.lean_threshold_deg))
                    return result(
                        "SLOUCH",
                        f"Badan membungkuk condong {lean:.0f} derajat selama {held_slouch:.0f} detik",
                        risk
                    )
        else:
            self._slouch_since = None
            self._lateral_since = None

        # Kondisi 4: Waktu duduk terlalu lama tanpa bergerak (Sedentary / Break Alert)
        if still_s >= p.sit_limit_s:
            risk = min(1.0, still_s / (1.5 * p.sit_limit_s))
            mins = still_s / 60.0
            return result(
                "BREAK",
                f"Telah duduk diam selama {mins:.1f} menit, saatnya berdiri dan peregangan!",
                risk
            )

        # Kondisi 5: Duduk tegak dengan postur baik
        return result("GOOD", "Postur tegak dan ergonomis", 0.0)
