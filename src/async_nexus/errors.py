class NoMoreEvents(RuntimeError):
    pass


class UnhandledEvent(Exception):
    pass


class MisconfiguredEventProducer(Exception):
    pass


class MultipleStart(Exception):
    pass


class BadCall(Exception):
    pass


class LoopAlreadyStarted(BadCall):
    pass


class LoopStopped(BadCall):
    pass


class InvalidLoopState(BadCall):
    pass
