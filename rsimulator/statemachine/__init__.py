import yaml
from .requirement import requirements
from .rglobal import get_global_manager
from .statemachine import get_sm_manager
from .statemachine import create_machine
from .statemachine import StateMachine
from importlib import import_module

from .. import sm_config

def set_statemachine_log_file_name(filename):
	sm_config._sm_log_file = filename

def add_machines(filename):
	with open(filename, 'r') as stream:
		machines = yaml.safe_load(stream)

	for machine in machines:
		module = import_module(machine['module'])
		create_machine(
			name=machine,
			model=getattr(module, 'StateMachine')(),
			states=getattr(module, 'states'),
			transitions=getattr(module, 'transitions'),
			initial=getattr(module, 'initial'),
		)
