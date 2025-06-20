import logging
from .. import rlogging
from .. import sm_config
from .. import enums

class RRequirementManager:
	_instance = None
	_requirements = dict()
	logger = rlogging.RLogger(f"RSMManager", log_level=logging.INFO, file_name=sm_config.sm_log_path())

	# EACH REQUIREMENT CAN HAVE 3 STATES: PENDING, PASS, FAIL

	def __new__(cls, *args, **kwargs):
		if not cls._instance:
			logging.setLoggerClass(rlogging.RLogger)
			cls._instance = super(RRequirementManager, cls).__new__(cls, *args, **kwargs)
		return cls._instance


	def add_requirement(self, name):
		if self._requirements.get(name):
			return
		self._requirements[name]= enums.RequirementStateType.PENDING

	def get_state(self, name):
		return self._requirements.get(name)

	def reset(self, name):
		if not self._requirements.get(name):
			return
		self._requirements[name] = enums.RequirementStateType.PENDING
		return True

	def confirm(self, name):
		if not self._requirements.get(name):
			return
		self._requirements[name] = enums.RequirementStateType.PASS
		return True

	def deny(self, name):
		if not self._requirements.get(name):
			return
		self._requirements[name] = enums.RequirementStateType.FAIL
		return True


requirements = RRequirementManager()

def get_requirement_manager() -> RRequirementManager:
	return requirements