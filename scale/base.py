class ScaleError(Exception):
    pass


class ScaleUnavailableError(ScaleError):
    pass


class UnstableWeightError(ScaleError):
    pass


class ScaleInterface:
    def connect(self):
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError

    def get_weight(self):
        raise NotImplementedError

    def is_stable(self):
        raise NotImplementedError

    def tare(self):
        raise NotImplementedError

    def zero(self):
        raise NotImplementedError
