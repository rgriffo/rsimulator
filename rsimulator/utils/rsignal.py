import logging


class SignalSlot:
    _instance = None
    _listeners = dict()

    def __init__(self):
        """Initialize data structure if it doesn't exist yet."""
        pass

    def __new__(cls, *args, **kwargs):
        """
        Singleton implementation for RSignal.
        Ensures that only one instance of RSignal is created.
        """
        if not cls._instance:
            cls._instance = super(SignalSlot, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    @property
    def listeners(self):
        return self._listeners

    # Note: signal = (node_name, message_name)       # message received
    #       signal = {node_name}_connected           # node connected      (ZMQ or TCP)

    def connect(self, signal, slot):
        """Link a slot to a signal"""
        self._listeners.setdefault(signal, list())
        self._listeners[signal].append(slot)

    def emit(self, signal, *args, **kwargs):
        """Emit signal to the connected slots"""
        responses = list()
        if signal not in self._listeners:
            return responses
        for listener in self._listeners[signal]:
            response = listener(*args, **kwargs)
            responses.append(response or dict())
        return responses


signal_instance = SignalSlot()
