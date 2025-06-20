import os


class Config:
	_instance = None

	_sm_log_file = 'statemachine.log'

	def __new__(cls, *args, **kwargs):
		"""
		Singleton implementation for STateMachine Config.
		"""
		if not cls._instance:
			cls._instance = super(Config, cls).__new__(cls, *args, **kwargs)

		return cls._instance

	def __init__(self):
		"""Initialize data structure if it doesn't exist yet."""
		pass

	def sm_log_path(self):
		_path = os.path.join(os.getcwd(), 'log/')
		os.makedirs(_path, exist_ok=True)
		return os.path.join(_path, self._sm_log_file)

# Configuration Manager instance
sm_config = Config()
