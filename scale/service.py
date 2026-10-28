import time
from decimal import Decimal
from django.conf import settings
from scale.base import ScaleInterface, ScaleUnavailableError, UnstableWeightError
from scale.mock import MockScale

_scale_instance = None


def get_scale() -> ScaleInterface:
    """Returns the configured scale driver instance according to settings.SCALE_MODE."""
    global _scale_instance
    mode = getattr(settings, 'SCALE_MODE', 'mock')
    if mode == "mock":
        if _scale_instance is None or not isinstance(_scale_instance, MockScale):
            _scale_instance = MockScale()
        return _scale_instance
    raise NotImplementedError(
        f"SCALE_MODE={mode!r} is not implemented yet. Real serial hardware is scheduled for Phase 11."
    )


def reset_mock_scale(target_weight: Decimal = Decimal('0.000'), settling_duration: float = 0.3):
    """Helper for test suites and dev resetting."""
    global _scale_instance
    _scale_instance = MockScale(target_weight=target_weight, settling_duration=settling_duration)
    return _scale_instance


def get_stable_weight(scale: ScaleInterface = None, timeout: float = 3.0, poll_interval: float = 0.05) -> Decimal:
    """
    Polls the scale until a stable weight reading is acquired.
    Raises UnstableWeightError if the scale does not stabilize within timeout.
    Raises ScaleUnavailableError if the scale is disconnected.
    """
    if scale is None:
        scale = get_scale()

    start_time = time.time()
    while True:
        if scale.is_stable():
            return scale.get_weight()

        if (time.time() - start_time) >= timeout:
            raise UnstableWeightError(
                f"وزن در مدت {timeout} ثانیه تثبیت نشد. لطفاً از ثبات بار روی باسکول اطمینان حاصل کنید."
            )

        time.sleep(poll_interval)
