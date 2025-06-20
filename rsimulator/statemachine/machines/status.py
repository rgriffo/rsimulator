from threading import Lock

from rsimulator.statemachine import StateMachine
from rsimulator.network import get_network

states = ['connected', 'not_connected']

transitions = [
	dict(
		trigger='disconnect',
		source='connected',
		dest='not_connected',
	),
	dict(
		trigger='connect',
		source='not_connected',
		dest='connected',
	)
]

class StatusSM(StateMachine):

	def __init__(self):
		super().__init__()
		self.lock = Lock()
		self._first_connection = True
		self._max_delay = 5
		# properties
		self._elapsed = 10

	@property
	def elapsed(self):
		with self.lock:
			return self._elapsed

	@elapsed.setter
	def elapsed(self, value):
		with self.lock:
			if value != self._elapsed:
				self.elapsed_changed(value)
			self._elapsed = value

	def elapsed_changed(self, value):
		if value > self._max_delay and self.state == 'connected':
			self.disconnect()
		elif value <= self._max_delay and self.state == 'not_connected':
			self.connect()

	def increment(self, value):
		self.elapsed += value

	def on_enter_connected(self):
		return
	def on_enter_not_connected(self):
		return


	def loop(self):
		# loop
		pass
