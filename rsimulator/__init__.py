import yaml
from .conf.network import network_config
from .conf.statemachine import sm_config

from .utils import error
from .utils import enums
from .utils import rlogging

from .network import get_network
from .statemachine import get_sm_manager

def start():
	get_network().start()
	get_sm_manager().start()

def stop(signum=None, frame=None):
	get_network().stop()
	get_sm_manager().stop()

def enable_log():
	rlogging.RLogger._disabled = False

def greeting():
	print('Ciao da Riccardo!')

def create_default_yaml(interface_pkg, output_path='output.yaml'):
	output_path += '' if output_path.endswith('.yaml') else '.yaml'
	data = {Message.__name__: Message().to_dict() for Message in interface_pkg.message_map.values()}
	with open(output_path, 'w') as file:
		yaml.dump(data, file, default_flow_style=False, allow_unicode=True)

def create_message_list(interface_pkg, simulator_name, output_file='output.yaml'):
	with open(output_file, 'w') as file:
		file.write('messages:\n')
		for message_id, Message in interface_pkg.message_map.items():
			file.write(f'  {Message.__name__}: ' + '{' + f'direction: {"out" if simulator_name in Message.source else "in"}' + '}\n')