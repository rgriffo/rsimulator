import os
import yaml
import pkgutil

class Config:

	_instance = None
	_network_file = None
	_network_data = None

	_default_zmq_interface_enabled = True
	_default_zmq_handlers_enabled = True

	_zmq_messages = dict()

	_uploaded_packages = dict()
	_uploaded_default_data = dict()
	_uploaded_glitch_data = dict()
	_uploaded_dispatchers = dict()

	_asynchronous_network = False

	_network_log_file = 'network.log'

	ZMQ_CONNECTION_REQUEST = '__ping__'
	ZMQ_CONNECTION_REPLY = '__pong__'
	MAX_LENGTH_IN_MESSAGES_DEQUE = 10
	CLIENT_CONNECTION_ATTEMPTS = 50
	SERVER_SOCKET_TIMEOUT = 0.5



	def __new__(cls, *args, **kwargs):
		"""
		Singleton implementation for Network Config.
		"""
		if not cls._instance:
			cls._instance = super(Config, cls).__new__(cls, *args, **kwargs)

		return cls._instance

	def __init__(self):
		"""Initialize data structure if it doesn't exist yet."""
		pass


	def interface_pkg(self, node_name):
		if not node_name:
			return
		return self._uploaded_packages.get(node_name, None)

	def default_data(self, node_name):
		if not node_name:
			return
		return self._uploaded_default_data.get(node_name, dict())

	def glitch_data(self, node_name):
		if not node_name:
			return
		return self._uploaded_glitch_data.get(node_name, dict())

	def dispatcher(self, node_name):
		if not node_name:
			return
		return self._uploaded_dispatchers.get(node_name, None)


	@property
	def network_file(self):
		return self._network_file

	@network_file.setter
	def network_file(self, value):
		self._network_file = value

	@property
	def network_data(self):
		return self._network_data

	@network_data.setter
	def network_data(self, value):
		self._network_data = value

	@property
	def default_zmq_handlers_enabled(self):
		return self._default_zmq_handlers_enabled

	@property
	def asynchronous_network(self):
		return self._asynchronous_network

	@asynchronous_network.setter
	def asynchronous_network(self, value):
		self._asynchronous_network = value

	def add_node_interface_pkg(self, interface_alias, package):
		self._uploaded_packages[interface_alias] = package

	def add_node_default_data(self, node_name, default_data_file):
		with open(default_data_file, 'r') as stream:
			default_data = yaml.safe_load(stream)
		self._uploaded_default_data.__setitem__(node_name, default_data)

	def add_node_glitch_data(self, node_name, glitch_data_file):
		with open(glitch_data_file, 'r') as stream:
			glitch_data = yaml.safe_load(stream)
		self._uploaded_glitch_data.__setitem__(node_name, glitch_data)

	def add_node_dispatcher(self, node_name, dispatcher):
		self._uploaded_dispatchers.__setitem__(node_name, dispatcher)

	def set_network_data(self):
		with open(self.network_file, 'r') as file:
			self._network_data = yaml.safe_load(file)

	@staticmethod
	def network_log_path():
		_path = os.path.join(os.getcwd(), 'log/')
		os.makedirs(_path, exist_ok=True)
		return os.path.join(_path, Config._network_log_file)

	# ZMQ

	def disable_default_zmq_interface(self):
		self._default_zmq_interface_enabled = False
		self._default_zmq_handlers_enabled= False

	def enable_default_zmq_interface(self, handlers=True):
		self._default_zmq_interface_enabled = True
		self._default_zmq_handlers_enabled = handlers

	def disable_default_zmq_handlers(self):
		self._default_zmq_handlers_enabled = False

	def upload_zmq_messages(self, descriptor_file):
		with open(descriptor_file, 'r') as stream:
			new_messages = yaml.safe_load(stream)
		self._zmq_messages = {**self._zmq_messages, **new_messages}

	def get_zmq_messages(self):
		if self._default_zmq_interface_enabled:
			default_messages = self.get_zmq_default_descriptor()
			return {**self._zmq_messages, **default_messages}
		return self._zmq_messages

	@staticmethod
	def get_zmq_default_descriptor():
		data = pkgutil.get_data('rsimulator', "network/interface/zmq/descriptor.yaml")
		return yaml.safe_load(data.decode("utf-8"))

# Configuration Manager instance
network_config = Config()
