import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.processing import (  # noqa: E402
    Params,
    PostureEngine,
    Sample,
    angle_between,
    apply_ema,
    calculate_ergonomic_score,
    decompose_tilt,
    integrate_rotation,
    mean_vector,
    window_rms,
)

UPRIGHT = [0.0, 9.8, 0.0]
LEANING_FORWARD = [0.0, 8.0, 5.6]   # ~35 derajat ke depan (pitch)
LEANING_SIDEWAYS = [5.6, 8.0, 0.0]  # ~35 derajat ke samping (roll)


def feed_both(eng, t, body_rms=0.05, seat_rms=0.03, grav=UPRIGHT):
    eng.feed(1, Sample(t, body_rms, list(grav)))
    eng.feed(2, Sample(t, seat_rms, [0.0, 0.0, 9.8]))


class ProcessingTests(unittest.TestCase):
    def test_rms_still_vs_moving(self):
        self.assertLess(window_rms([9.8, 9.81, 9.79, 9.8]), 0.05)
        self.assertGreater(window_rms([9.8, 12.0, 7.5, 11.0]), 1.0)
        self.assertEqual(window_rms([]), 0.0)

    def test_mean_vector(self):
        self.assertEqual(mean_vector([[1, 2, 3], [3, 4, 5]]), [2.0, 3.0, 4.0])

    def test_apply_ema(self):
        raw1 = [0.0, 10.0, 0.0]
        ema1 = apply_ema(raw1, None, alpha=0.5)
        self.assertEqual(ema1, [0.0, 10.0, 0.0])
        
        raw2 = [0.0, 8.0, 0.0]
        ema2 = apply_ema(raw2, ema1, alpha=0.5)
        self.assertEqual(ema2, [0.0, 9.0, 0.0])

    def test_integrate_rotation(self):
        rates = [(0.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        rad = integrate_rotation(rates, dt=1.0)
        self.assertAlmostEqual(rad, 1.0, places=3)

    def test_angle(self):
        self.assertAlmostEqual(angle_between(UPRIGHT, UPRIGHT), 0.0, places=3)
        self.assertAlmostEqual(angle_between([1, 0, 0], [0, 1, 0]), 90.0, places=3)
        self.assertGreater(angle_between(UPRIGHT, LEANING_FORWARD), 30)

    def test_decompose_tilt(self):
        res = decompose_tilt(LEANING_FORWARD, UPRIGHT)
        self.assertGreater(res["total_deg"], 30)
        self.assertGreater(abs(res["pitch_deg"]), abs(res["roll_deg"]))

        res_side = decompose_tilt(LEANING_SIDEWAYS, UPRIGHT)
        self.assertGreater(res_side["total_deg"], 30)
        self.assertGreater(abs(res_side["roll_deg"]), abs(res_side["pitch_deg"]))

    def test_ergonomic_score(self):
        # Postur tegak sempurna
        score_perfect = calculate_ergonomic_score(0.0, 100.0)
        self.assertEqual(score_perfect, 100)

        # Postur membungkuk parah
        score_bad = calculate_ergonomic_score(35.0, 100.0)
        self.assertLess(score_bad, 70)


class EngineTests(unittest.TestCase):
    def make(self):
        eng = PostureEngine(Params(lean_hold_s=5, sit_limit_s=60, break_reset_s=10, away_hold_s=2))
        feed_both(eng, 0)
        eng.calibrate()
        return eng

    def test_offline_and_calibrate(self):
        eng = PostureEngine()
        self.assertEqual(eng.evaluate(0)["state"], "OFFLINE")
        feed_both(eng, 0)
        self.assertEqual(eng.evaluate(0.5)["state"], "CALIBRATE")
        eng.calibrate()
        self.assertEqual(eng.evaluate(0.5)["state"], "GOOD")

    def test_slouch_forward_needs_hold_time(self):
        eng = self.make()
        feed_both(eng, 1, grav=LEANING_FORWARD)
        self.assertEqual(eng.evaluate(1)["state"], "GOOD")  # baru mulai condong
        feed_both(eng, 4, grav=LEANING_FORWARD)
        self.assertEqual(eng.evaluate(4)["state"], "GOOD")
        feed_both(eng, 7, grav=LEANING_FORWARD)
        res = eng.evaluate(7)
        self.assertEqual(res["state"], "SLOUCH")
        self.assertGreater(res["lean_deg"], 30)

    def test_lateral_lean_sideways(self):
        eng = self.make()
        feed_both(eng, 1, grav=LEANING_SIDEWAYS)
        self.assertEqual(eng.evaluate(1)["state"], "GOOD")
        feed_both(eng, 7, grav=LEANING_SIDEWAYS)
        res = eng.evaluate(7)
        self.assertEqual(res["state"], "LATERAL_LEAN")
        self.assertGreater(res["lean_deg"], 30)

    def test_slouch_recovers(self):
        eng = self.make()
        for t in (1, 4, 7):
            feed_both(eng, t, grav=LEANING_FORWARD)
            eng.evaluate(t)
        feed_both(eng, 8, grav=UPRIGHT)
        self.assertEqual(eng.evaluate(8)["state"], "GOOD")

    def test_break_after_long_stillness(self):
        eng = self.make()
        for t in range(1, 70, 3):
            feed_both(eng, t)
            res = eng.evaluate(t)
        self.assertEqual(res["state"], "BREAK")

    def test_movement_resets_still_timer(self):
        eng = self.make()
        for t in range(1, 50, 3):
            feed_both(eng, t)
            eng.evaluate(t)
        feed_both(eng, 50, body_rms=0.6)  # peregangan/gerakan mikro
        feed_both(eng, 62)
        self.assertEqual(eng.evaluate(62)["state"], "GOOD")

    def test_away_when_body_moves_and_seat_still(self):
        eng = self.make()
        feed_both(eng, 1, body_rms=2.0, seat_rms=0.02)
        eng.evaluate(1)
        feed_both(eng, 4, body_rms=2.0, seat_rms=0.02)
        self.assertEqual(eng.evaluate(4)["state"], "AWAY")

    def test_common_motion(self):
        eng = self.make()
        feed_both(eng, 1, body_rms=2.0, seat_rms=2.0)
        self.assertEqual(eng.evaluate(1)["state"], "COMMON_MOTION")

    def test_stale_edge_goes_offline(self):
        eng = self.make()
        self.assertEqual(eng.evaluate(30)["state"], "OFFLINE")

    def test_pause(self):
        eng = self.make()
        eng.monitoring = False
        self.assertEqual(eng.evaluate(1)["state"], "PAUSED")


if __name__ == "__main__":
    unittest.main()
