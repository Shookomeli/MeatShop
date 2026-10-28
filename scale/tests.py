import time
import threading
from decimal import Decimal
from django.test import TestCase
from scale.base import ScaleUnavailableError, UnstableWeightError
from scale.mock import MockScale
from scale.service import get_stable_weight, get_scale, reset_mock_scale


class MockScaleTestCase(TestCase):
    def test_mock_scale_settling_and_stability(self):
        scale = MockScale(target_weight=Decimal("25.500"), settling_duration=0.15)
        # Immediately upon creation/placement, scale is settling (unstable)
        self.assertFalse(scale.is_stable())

        # Wait for settling duration
        time.sleep(0.18)
        self.assertTrue(scale.is_stable())
        self.assertEqual(scale.get_weight(), Decimal("25.500"))

    def test_mock_scale_tare_and_zero(self):
        scale = MockScale(target_weight=Decimal("15.200"), settling_duration=0.05)
        time.sleep(0.06)
        self.assertEqual(scale.get_weight(), Decimal("15.200"))

        # Tare the 15.200 kg load
        scale.tare()
        self.assertEqual(scale.get_weight(), Decimal("0.000"))

        # Add more load: total gross 25.200 kg -> net should be 10.000 kg
        scale.set_target_weight(Decimal("25.200"), settling_duration=0.05)
        time.sleep(0.06)
        self.assertEqual(scale.get_weight(), Decimal("10.000"))

        # Zero the scale -> restores full gross weight 25.200 kg
        scale.zero()
        self.assertEqual(scale.get_weight(), Decimal("25.200"))

    def test_mock_scale_disconnect_raises_error(self):
        scale = MockScale(target_weight=Decimal("10.000"))
        scale.disconnect()
        self.assertFalse(scale.is_connected())

        with self.assertRaises(ScaleUnavailableError):
            scale.get_weight()

        with self.assertRaises(ScaleUnavailableError):
            scale.is_stable()

        # Reconnect
        scale.connect()
        self.assertTrue(scale.is_connected())

    def test_get_stable_weight_success(self):
        scale = MockScale(target_weight=Decimal("42.750"), settling_duration=0.10)
        weight = get_stable_weight(scale=scale, timeout=1.0, poll_interval=0.03)
        self.assertEqual(weight, Decimal("42.750"))

    def test_get_stable_weight_timeout_raises_unstable_error(self):
        scale = MockScale(target_weight=Decimal("30.000"))
        scale.set_failure_scenario(permanent_unstable=True)

        with self.assertRaises(UnstableWeightError):
            get_stable_weight(scale=scale, timeout=0.15, poll_interval=0.03)

    def test_mock_scale_thread_safety(self):
        scale = MockScale(target_weight=Decimal("50.000"), settling_duration=0.05)
        errors = []

        def worker(worker_id):
            try:
                for i in range(20):
                    target = Decimal(f"{worker_id * 10 + i}.500")
                    scale.set_target_weight(target, settling_duration=0.02)
                    _ = scale.is_stable()
                    _ = scale.get_weight()
                    if i % 5 == 0:
                        scale.tare()
                    elif i % 7 == 0:
                        scale.zero()
                    time.sleep(0.005)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Thread safety errors encountered: {errors}")
