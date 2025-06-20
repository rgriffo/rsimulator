import threading
import time
from transitions import Machine
import logging

from .. import rlogging
from .. import sm_config

class StateMachine:
	interval = 1
	logger = rlogging.RLogger(f"RSMManager", log_level=logging.INFO, file_name=sm_config.sm_log_path())

	def __init__(self):
		pass

	def on_enter(self):
		self.logger.info('Entering a new state!')

	def loop(self):
		self.logger.info('Absract Loop called.. Reimplement loop() function!')


class StateMachineWorker(threading.Thread):
	# Lo scopo di questa classe è creare un thread
	# dedicato per ogni singola state machine
	# Il thread esegue un loop che tiene traccia
	# dell'evoluzione dei parametri e la gestione degli eventi

	def __init__(self, machine, loop, interval=1.0):
		super().__init__(name=machine.__class__.__name__)
		self.machine = machine
		self.loop = loop
		self.interval = interval
		self._stop_event = threading.Event()

	def run(self):
		while not self._stop_event.is_set():
			self.loop()
			time.sleep(self.interval)

	def stop(self):
		self._stop_event.set()


class RStateMachineManager:
	_instance = None
	_machines = dict()  # name: StateMachineWorker

	logger = rlogging.RLogger(f"RSMManager", log_level=logging.INFO, file_name=sm_config.sm_log_path())

	def __new__(cls, *args, **kwargs):
		"""
		Singleton implementation for RStateMachineManager.
		Ensures that only one instance of RNetwork is created.
		"""
		if not cls._instance:
			logging.setLoggerClass(rlogging.RLogger)
			cls._instance = super(RStateMachineManager, cls).__new__(cls, *args, **kwargs)
		return cls._instance

	def __init__(self):
		pass

	def get_property(self, name, p):
		return getattr(self.get_machine(name).model, p)

	def set_property(self, name, p, value):
		setattr(self.get_machine(name).model, p, value)

	def add_machine(self, name, machine, loop, interval=1.0):
		if name in self._machines:
			raise ValueError(f"Machine '{name}' already exists in manager!")
		worker = StateMachineWorker(machine, loop, interval)
		self._machines[name] = worker

	def start(self):
		for name, worker in self._machines.items():
			worker.start()
			self.logger.info(f'{name} started.')

	def stop(self):
		for worker in self._machines.values():
			worker.stop()
		for name, worker in self._machines.items():
			worker.join()
			self.logger.info(f'{name} stopped.')

	def get_machine(self, name):
		worker = self._machines.get(name)
		if worker is None:
			raise ValueError(f"Machine '{name}' not found in manager.")
		return worker.machine

	def remove_machine(self, name):
		if name in self._machines:
			worker = self._machines[name]
			worker.stop()
			worker.join()
			del self._machines[name]
		else:
			raise ValueError(f"Machine '{name}' not found in manager.")



def create_machine(name, model, states, transitions, initial):
	machine = Machine(
		model=model,
		states=states,
		transitions=transitions,
		initial=initial
	)

	RStateMachineManager().add_machine(name, machine, model.loop, model.interval)

def get_sm_manager() -> RStateMachineManager:
	return RStateMachineManager()

