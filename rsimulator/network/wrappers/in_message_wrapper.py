from collections import deque
from threading import Lock
import time

from ...utils import enums
from ...conf.network import network_config as config

class InMessageWrapper:
	direction = enums.MessageDirectionType.IN

	def __init__(self, **kwargs):
		self.parent_node = kwargs.get('parent_node')
		self.name = kwargs.get('name')
		self._counter = 0
		self._last_time = -1
		self._last_messages = deque(maxlen=config.MAX_LENGTH_IN_MESSAGES_DEQUE)
		self._lock = Lock()

	def init(self):
		pass

	@property
	def lock(self):
		return self._lock

	@property
	def counter(self):
		return self._counter

	@property
	def last_time(self):
		return self._last_time

	def increment(self):
		self._counter += 1
		self._last_time = time.time()

	def reset(self):
		self._counter = 0

	def last(self, number=None):
		if self.counter == 0:
			return []
		if not number:
			return self._last_messages[-1]
		return list(self._last_messages)[-min(number, len(self._last_messages)):]

	def append(self, message, deserialize=False):
		self._last_messages.append(message)
		if deserialize:
			return message.deserialize()


class SpecInMessageWrapper(InMessageWrapper):

	def __init__(self, **kwargs):
		super(SpecInMessageWrapper, self).__init__(**kwargs)


class ZMQInMessageWrapper(InMessageWrapper):

	def __init__(self, **kwargs):
		super(ZMQInMessageWrapper, self).__init__(**kwargs)


def get_in_message_wrapper(protocol: enums.ProtocolType):
	return InMessageWrapper if protocol is enums.ProtocolType.TCP else \
		InMessageWrapper if protocol is enums.ProtocolType.UDP else \
		SpecInMessageWrapper if protocol is enums.ProtocolType.SPEC_TCP else \
		SpecInMessageWrapper if protocol is enums.ProtocolType.SPEC_UDP else \
		ZMQInMessageWrapper if protocol is enums.ProtocolType.ZMQ else None
