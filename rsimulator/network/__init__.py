import copy

from .. import network_config
from .network import (
	get_network,
	create_network,
	wait_for_connections,
	wait_for_connection
)

def set_asynchronous(value=True):
	network_config.asynchronous_network = value

def set_network_file(file):
	network_config.network_file = file
	network_config.set_network_data()

def set_network_log_file_name(file_name):
	network_config._network_log_file = file_name

def add_node_interface_pkg(node_name, package):
	network_config.add_node_interface_pkg(node_name, package)

def add_node_default_data(node_name, default_data):
	network_config.add_node_default_data(node_name, default_data)

def add_node_glitch_data(node_name, glitch_data):
	network_config.add_node_glitch_data(node_name, glitch_data)

def deactivate_default_zmq_handlers():
	network_config.default_zmq_handlers = False
