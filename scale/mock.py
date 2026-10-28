import time
import math
import random
import threading
from decimal import Decimal, ROUND_HALF_UP
from scale.base import ScaleInterface, ScaleUnavailableError, UnstableWeightError


class MockScale(ScaleInterface):
    """
    High-fidelity software scale simulator.
    Simulates settling time, jitter/noise, tare/zero calibration,
    and configurable hardware failure scenarios with thread safety.
    """

    def __init__(
        self,
        target_weight: Decimal = Decimal('0.000'),
        settling_duration: float = 0.3,
        jitter_amplitude: Decimal = Decimal('0.050'),
    ):
        self._lock = threading.Lock()
        self._connected = True
        self._target_weight = Decimal(str(target_weight))
        self._tare_offset = Decimal('0.000')
        self._settling_duration = settling_duration
        self._jitter_amplitude = Decimal(str(jitter_amplitude))
        self._settling_start_time = time.time()
        self._simulate_permanent_unstable = False
        self._simulate_disconnect = False

    def connect(self):
        with self._lock:
            self._connected = True
            self._simulate_disconnect = False

    def disconnect(self):
        with self._lock:
            self._connected = False

    def set_target_weight(self, weight, settling_duration: float = 0.3):
        """Places a new load on the scale, restarting the settling timer."""
        with self._lock:
            self._target_weight = Decimal(str(weight))
            self._settling_duration = settling_duration
            self._settling_start_time = time.time()

    def set_failure_scenario(self, disconnected: bool = False, permanent_unstable: bool = False):
        with self._lock:
            self._simulate_disconnect = disconnected
            if disconnected:
                self._connected = False
            self._simulate_permanent_unstable = permanent_unstable

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected and not self._simulate_disconnect

    def is_stable(self) -> bool:
        with self._lock:
            if not self._connected or self._simulate_disconnect:
                raise ScaleUnavailableError("ترازو در دسترس نیست یا ارتباط با پورت قطع شده است.")
            if self._simulate_permanent_unstable:
                return False
            elapsed = time.time() - self._settling_start_time
            return elapsed >= self._settling_duration

    def get_weight(self) -> Decimal:
        """
        Returns the current weight in kilograms with 3 decimal places.
        If the scale is currently settling or unstable, adds simulated jitter.
        """
        with self._lock:
            if not self._connected or self._simulate_disconnect:
                raise ScaleUnavailableError("خطا در برقراری ارتباط با ترازوی دیجیتال.")

            elapsed = time.time() - self._settling_start_time
            is_settled = (elapsed >= self._settling_duration) and not self._simulate_permanent_unstable

            if is_settled:
                gross = self._target_weight
            else:
                # Add sinusoidal/random settling noise around target
                noise_factor = (random.random() * 2.0 - 1.0)
                noise = self._jitter_amplitude * Decimal(str(noise_factor))
                gross = self._target_weight + noise
                if gross < Decimal('0.000'):
                    gross = Decimal('0.000')

            net = gross - self._tare_offset
            # Quantize to 3 decimal places (grams)
            return net.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

    def tare(self):
        """Tares the current gross weight, setting net to 0.000 kg."""
        with self._lock:
            if not self._connected or self._simulate_disconnect:
                raise ScaleUnavailableError("دستور پارسنگ ناموفق: ترازو در دسترس نیست.")
            self._tare_offset = self._target_weight

    def zero(self):
        """Clears tare offset, calibrating the scale to absolute zero."""
        with self._lock:
            if not self._connected or self._simulate_disconnect:
                raise ScaleUnavailableError("دستور صفر ناموفق: ترازو در دسترس نیست.")
            self._tare_offset = Decimal('0.000')
