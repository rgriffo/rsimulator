import logging
import threading
import time
import json
import asyncio

from ..utils import enums
from ..utils import error
from ..utils import rlogging
from ..conf.network import network_config as config


from .dispatcher import get_dispatcher
from .wrappers import get_node_wrapper
from .interface import get_interface_pkg


class RNetwork:
	_instance = None
	_initialized = False
	_messages_ref = dict()  # Associate the message_name to the node_name(s)
	_node_ref = dict()      # Associate the node_name to the message_name(s)
	_running = False
	_tasks = list()

	logger = rlogging.RLogger("RNetwork", log_level=logging.INFO, file_name=config.network_log_path())

	def __new__(cls, *args, **kwargs):
		"""
		Singleton implementation for RNetwork.
		Ensures that only one instance of RNetwork is created.
		"""
		if not cls._instance:
			logging.setLoggerClass(rlogging.RLogger)
			cls._instance = super(RNetwork, cls).__new__(cls, *args, **kwargs)
		return cls._instance

	def __init__(self):
		"""Initialize data structure if it doesn't exist yet."""
		pass

	def init(self):
		if self._initialized:
			return
		self._initialized = True
		network = config.network_data

		for node_name, data in network.items():
			protocol = enums.ProtocolType[data.get('protocol', 'unknown').upper()]
			role = enums.NodeRoleType[data.get('role', 'unknown').upper()]
			host = data.get('host')
			port = data.get('port')
			log_level = data.get('log_level', logging.INFO)
			messages = data.get('messages', dict())
			if 'zmq' in protocol.name.lower():
				messages = config.get_zmq_messages()

			if None in (protocol, role, host, port):
				raise EnvironmentError(
					f'Definition error. protocol: {protocol.__repr__}, '
					f'role:{role.__repr__}, host:{host}, port:{port}')

			Wrapper = get_node_wrapper(protocol)
			Dispatcher = get_dispatcher(protocol, node_name)
			interface_pkg = get_interface_pkg(protocol, node_name)

			if interface_pkg is None:
				raise EnvironmentError(f'Interface package not defined for {node_name}')

			default_data = config.default_data(node_name)
			glitch_data = config.glitch_data(node_name)

			setattr(self, node_name, Wrapper(
				name=node_name,
				role=role,
				protocol=protocol,
				host=host,
				port=port,
				interface_pkg=interface_pkg,
				dispatcher=Dispatcher,
				default_data=default_data,
				glitch_data=glitch_data,
				messages=messages,
				log_level=log_level
			))

			for message_name in messages.keys():
				self.add_ref(message_name, node_name)

	def add_ref(self, message_name, node_name):
		# from message name to node name
		self._messages_ref.setdefault(message_name, list())
		self._messages_ref[message_name].append(node_name)
		# from node name to message name
		self._node_ref.setdefault(node_name, list())
		self._node_ref[node_name].append(message_name)

	def start(self):
		self.logger.info(f'Starting network activities...')
		for node_name in self._node_ref.keys():
			self.get_node_wrap(node_name).running = True

	def stop(self):
		self.logger.info(f'Stopping network activities...')
		for node_name in self._node_ref.keys():
			if self.get_node_wrap(node_name).running:
				self.get_node_wrap(node_name).running = False
				self.logger.info(f'{node_name} status: CLOSED')

	# Send Message Support

	def send_buffer(self, node_name, buffer):
		"""Send a buffer to a specific client using its queue."""
		getattr(self, node_name).send_buffer(buffer)

	def send_dict(self, node_name, _dict):
		"""Send a buffer to a specific client using its queue."""
		buffer = json.dumps(_dict).encode('utf-8')
		getattr(self, node_name).send_buffer(buffer)

	def send_message(self, message_name, node_name=None):
		"""Send an interface message to a specific client using its queue."""
		if not node_name:
			node_name = self.get_node_name_from_message_name(message_name)
		node_wrap = self.get_node_wrap(node_name)
		if not node_wrap:
			return error.ErrorType.NODE_NOT_FOUND
		node_wrap.send_message(message_name)

	# Getters and Setters

	def update_data(self, path_list, value, node_name=None, glitch=False):
		message_name, *path_list = path_list.split('.')
		if isinstance(node_name := node_name or self.get_node_name_from_message_name(message_name), error.ErrorType):
			return node_name
		if not path_list:
			return self.get_node_wrap(node_name).update_message(
				message_name=message_name,
				data=value,
				glitch=glitch)
		else:
			return self.get_node_wrap(node_name).update_data(
				message_name=message_name,
				path_list=path_list,
				value=value,
				glitch=glitch)

	def get_data(self, path_list, node_name=None, glitch=False, to_dict=True, copy=True):
		message_name, *path_list = path_list.split('.')
		if isinstance(node_name := node_name or self.get_node_name_from_message_name(message_name), error.ErrorType):
			return node_name
		if not path_list:
			return self.get_node_wrap(node_name).get_data(
				message_name=message_name,
				path=path_list,
				glitch=glitch,
				to_dict=to_dict,
				copy=copy)
		else:
			return self.get_node_wrap(node_name).get_message_data(
				message_name=message_name,
				to_dict=True,
				glitch=glitch)

	def reset_data(self, node_name, messages=None):
		if not messages:
			for message_name in self._node_ref[node_name]:
				return self.get_node_wrap(node_name).reset_data(
					message_name=message_name)
		else:
			for message_name in messages:
				return self.get_node_wrap(node_name).reset_data(
					message_name=message_name)

	def get_connection_result(self, exclude_zmq=True):
		# A TCP client node is considered connected if is connected to a server
		# A TCP server node is considered connected if at least one client is connected
		# A ZMQ client node is considered connected if is connected to a server
		# A ZMQ server node is considered connected on first ZMQ_CONNECTION_REQUEST reception
		# A UDP client node is considered connected on ZMQ_CONNECTION_REPLY reception
		# A UDP server node is considered connected on start
		# A RNetwork is considered connected if each node is connected
		for node_name in self._node_ref:
			if exclude_zmq and 'zmq' in node_name.lower():
				continue
			if not self.get_node_wrap(node_name).connected:
				return False
		return True

	def get_node_name_from_message_name(self, message_name):
		if message_name not in self._messages_ref:
			self.logger.error(error.ErrorType.MESSAGE_NOT_FOUND.value_with_args(message_name))
			raise KeyError(error.ErrorType.MESSAGE_NOT_FOUND.value_with_args(message_name))
		nodes = self._messages_ref[message_name]
		if len(nodes) > 1:
			self.logger.error(error.ErrorType.MESSAGE_NOT_UNIQUE.value_with_args(message_name))
			raise KeyError(error.ErrorType.MESSAGE_NOT_UNIQUE.value_with_args(message_name))
		return nodes[0]

	def get_node_wrap(self, node_name):
		if not hasattr(self, node_name):
			return
		return getattr(self, node_name)

	def get_message_wrap(self, message_name, node_name=None):
		if not node_name:
			node_name = self.get_node_name_from_message_name(message_name)
		node_wrap = self.get_node_wrap(node_name)
		return node_wrap.get_message(message_name)

	# Periodic Message Support

	def _send_periodically(self, message_name, node_name, interval):
		"""Internal method to send the message at regular intervals."""
		while self.is_periodic_active(message_name=message_name, node_name=node_name):
			self.send_message(message_name, node_name)
			time.sleep(interval)

	def start_periodic(self, message_name, node_name=None, interval=None):
		"""Start sending the periodic message."""
		# If the message is already being sent, then do nothing
		if not node_name:
			node_name = self.get_node_name_from_message_name(message_name)
		if self.is_periodic_active(message_name=message_name, node_name=node_name):
			self.logger.error(f"Message '{message_name}' is already sent periodically.")
			return
		node_wrap = getattr(self, node_name)
		if not interval:
			interval = node_wrap.get_message(message_name).interval
		self.get_node_wrap(node_name).activate_periodic_message(message_name)
		thread = threading.Thread(target=self._send_periodically,
			args=(message_name, node_name, interval),
			name=f'{message_name}_periodic_sender')
		self.logger.info(f"Start sending periodic message: {message_name}")
		thread.start()

	def stop_periodic(self, message_name, node_name=None):
		"""Stop sending the periodic message."""
		if not node_name:
			node_name = self.get_node_name_from_message_name(message_name)
		if self.is_periodic_active(message_name=message_name, node_name=node_name):
			self.get_node_wrap(node_name).deactivate_periodic_message(message_name)
			self.logger.info(f"Stopping periodic message: {message_name}")
		else:
			self.logger.error(f"Cannot stop periodic {message_name}. Message is not active.")

	def is_periodic_active(self, message_name, node_name):
		return self.get_node_wrap(node_name).is_periodic_active(message_name)


# Per il momento non do la possibilità di
# creare più di un network per processo

networks = list()

def create_network() -> RNetwork:
	instance = RNetwork()
	instance.init()
	networks.append(instance)
	return networks[0]

def get_network() -> RNetwork:
	if not networks:
		create_network()
	return networks[0]

def wait_for_connections(exclude_zmq=False):
	network = get_network()
	while True:
		network.logger.info("simulator waiting for connections...")
		if network.get_connection_result(exclude_zmq=exclude_zmq):
			network.logger.info("Connections Done!")
			break
		time.sleep(1)

def wait_for_connection(node_name):
	network = get_network()
	while True:
		if getattr(network, node_name).connected:
			network.logger.info(f"Connection with {node_name} Done!")
			break
		time.sleep(1)
