class NoMoreEvents(RuntimeError):
    pass


class UnhandledEvent(Exception):
    pass


class MisconfiguredEventProducer(Exception):
    pass
