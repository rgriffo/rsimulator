import logging
from .. import rlogging
from .statemachine import sm_config

class RGlobal:
	_instance = None
	variables = dict()
	logger = rlogging.RLogger(f"RGlobal", log_level=logging.INFO, file_name=sm_config.sm_log_path())


	def __new__(cls, *args, **kwargs):
		if not cls._instance:
			logging.setLoggerClass(rlogging.RLogger)
			cls._instance = super(RGlobal, cls).__new__(cls, *args, **kwargs)
		return cls._instance


	def add_global_variable(self, name, value):
		if self.variables.get(name):
			return
		self.variables[name] = value

	def get_global_variable(self, name):
		return self.variables.get(name)

	def update_global_variable(self, name, value):
		if not self.variables.get(name):
			return False
		self.variables[name] = value
		return True

def get_global_manager():
	return RGlobal()