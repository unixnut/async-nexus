class NoMoreEvents(RuntimeError):
    pass


class UnhandledEvent(Exception):
    pass


class BadCall(Exception):
    pass


class MisconfiguredEventProducer(BadCall):
    pass


class MisconfiguredEventConsumer(BadCall):
    pass


class MultipleStart(Exception):
    pass


class LoopAlreadyStarted(BadCall):
    pass


class LoopStopped(BadCall):
    pass


class InvalidLoopState(BadCall):
    pass
