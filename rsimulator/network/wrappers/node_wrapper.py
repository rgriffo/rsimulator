import logging
import threading
import queue
import abc
import importlib
import asyncio
import time

from ..socket.client import Client
from ...utils import enums
from ...utils import error
from ...utils import rlogging
from ...conf.network import network_config as config
from ..socket import get_client, get_server, get_async_client, get_async_server
from ...utils.rsignal import signal_instance

from .in_message_wrapper import get_in_message_wrapper
from .out_message_wrapper import get_out_message_wrapper
from .twoway_message_wrapper import get_two_way_message_wrapper


class NodeWrapper(abc.ABC):
	"""
	Implementation for InterfaceWrapper.
	Contains In/Out MessageWrapper objects as class members
	"""

	def __init__(self, **kwargs):
		self._running = False
		self._connected = False
		self._exclude_from_log = list()

		self.messages = dict()
		self.role = kwargs.get('role')
		self.protocol = kwargs.get('protocol')
		self.name = kwargs.get('name')
		self.host = kwargs.get('host')
		self.port = kwargs.get('port')
		self.periodic_messages = set()
		self.thread = None
		self.message_queue = None
		self.socket = None

		log_level = kwargs.get('log_level', 'INFO')
		self.logger = rlogging.RLogger(f"Node.{self.name}",
			file_name=config.network_log_path(), log_level=getattr(logging, log_level.upper()))


		if None in (self.protocol, self.role, self.host, self.port, self.name):
			raise ValueError(f'Definition error. protocol: {self.protocol.__repr__}, role:{self.role.__repr__}, '
							 f'host:{self.host}, port:{self.port}')

		# Initialize data
		self.interface_pkg = kwargs.get('interface_pkg')
		Dispatcher = kwargs.get('dispatcher')
		self.default_data = kwargs.get('default_data', dict())
		self.glitch_data = kwargs.get('glitch_data', dict())

		if self.interface_pkg is None:
			raise TypeError(f'Interface cannot be None for {self.name}')
		if Dispatcher is None:
			raise TypeError(f'Dispatcher cannot be None for {self.name}')

		self.dispatcher = Dispatcher(parent_node=self)

		# All the contained data will be added
		# dynamically as members of the class
		kwargs.setdefault('messages', list())
		self.init_messages(kwargs['messages'])

	def init_messages(self, messages):
		def reply(message_name_in, message_name_out):
			def internal_reply():
				self.logger.info(f'On {message_name_in} received: Sending {message_name_out}')
				self.send_message(message_name_out)
			return internal_reply


		for message_name, data in messages.items():
			if data.get('exclude_from_log', False):
				self._exclude_from_log.append(message_name)
			direction = data.get('direction', None)

			if direction is None:
				raise KeyError(f'No direction for message {message_name}')
			direction = enums.MessageDirectionType[direction.upper()]

			if direction is enums.MessageDirectionType.IN:
				if 'reply' in data:
					signal_instance.connect((self.name, message_name), reply)
				MessageWrapper = get_in_message_wrapper(self.protocol)
				self.messages[message_name] = MessageWrapper(
					parent_node=self,
					name=message_name,
				)

			elif direction is enums.MessageDirectionType.OUT:
				MessageWrapper = get_out_message_wrapper(self.protocol)
				if MessageWrapper is None:
					raise TypeError(f'MessageWrapper cannot be None in {self.name}-{message_name}')

				self.messages[message_name] = MessageWrapper(
					parent_node=self,
					name=message_name,
					periodic=data.get('periodic', False),
					interval=data.get('interval', 1),
					default_data=self.default_data.get(message_name, None),
					glitch_data=self.glitch_data.get(message_name, None),
				)

			elif direction is enums.MessageDirectionType.TWO_WAY:
				MessageWrapper = get_two_way_message_wrapper(self.protocol)
				if MessageWrapper is None:
					raise TypeError(f'MessageWrapper cannot be None in {self.name}-{message_name}')
				self.messages[message_name] = MessageWrapper(
					parent_node=self,
					name=message_name,
					periodic=data.get('periodic', False),
					interval=data.get('interval', 1),
					default_data=self.default_data.get(message_name, None),
					glitch_data=self.glitch_data.get(message_name, None),
				)


	@abc.abstractmethod
	def serialize(self, message_name):
		pass

	@abc.abstractmethod
	def deserialize(self, buffer, to_dict=True):
		pass

	def get_message(self, message_name):
		return self.messages.get(message_name)

	def start(self):

		def start_server():
			"""Start a server."""
			Server = get_server(self.protocol)
			server = Server(self)
			server.start()

		def start_client():
			"""Start a client and create a queue for it."""
			Client = get_client(self.protocol)
			client = Client(self)
			client.connect()
			client.handle_queue()

		async def start_async_server():
			Server = get_async_server(self.protocol)
			self.socket = Server(self)
			await self.socket.start()

		async def start_async_client():
			Client = get_async_client(self.protocol)
			self.socket = Client(self)
			await self.socket.run()

		async def async_start():
			self.logger.debug(f'Starting node {self.name} activities...')
			await getattr(self, f'start_async_{self.role.name.lower()}')()

		if not config.asynchronous_network:
			_start = start_client if self.role.name.lower() == 'client' else start_server
			self.message_queue = queue.Queue()
			self.thread = threading.Thread(target=_start, name=f'{self.name}_thread')
			self.thread.start()
		else:
			NotImplementedError('Non ho ancora configurato lo start di una rete asincrona')

	def stop(self):
		if not config.asynchronous_network:
			for message_name in self.periodic_messages:
				self.deactivate_periodic_message(message_name)
			self.message_queue.put('EXIT')
			self.thread.join()
		else:
			NotImplementedError('Non ho ancora configurato lo stop di una rete asincrona')



	def send_buffer(self, buffer):
		self.message_queue.put(buffer)

	def send_message(self, message_name):
		if config.asynchronous_network:
			loop = asyncio.get_event_loop()
			loop.run_until_complete(self.socket.add(self.serialize(message_name)))
		else:
			self.message_queue.put(self.serialize(message_name))

	def activate_periodic_message(self, message_name):
		self.get_message(message_name).periodic = True
		self.periodic_messages.add(message_name)

	def deactivate_periodic_message(self, message_name):
		self.get_message(message_name).periodic = False
		self.periodic_messages.remove(message_name)

	@property
	def connected(self):
		return self._connected

	@connected.setter
	def connected(self, value):
		self._connected = value
		if value:
			signal_instance.emit(f'{self.name}_connected', logger=self.logger)

	@property
	def running(self):
		return self._running

	@running.setter
	def running(self, value):
		if self._running == value:
			return
		self._running = value
		if value:
			self.start()
		else:
			self.stop()


class EnlargedNodeWrapper(NodeWrapper, abc.ABC):

	def __init__(self, **kwargs):
		super(EnlargedNodeWrapper, self).__init__(**kwargs)

	# Getters and Setters

	def update_message(self, message_name, data, glitch=False):
		message_wrap = self.get_message_wrap(message_name, out=True)
		if isinstance(message_wrap, error.ErrorType):
			return message_wrap
		return message_wrap.update_message(data=data, glitch=glitch)

	def update_data(self, message_name, path_list, value, glitch=False):
		message_wrap = self.get_message_wrap(message_name, out=True)
		if isinstance(message_wrap, error.ErrorType):
			return message_wrap
		return message_wrap.update_data(path_list, value, glitch)

	def get_message_data(self, message_name, to_dict=False, glitch=False):
		message_wrap = self.get_message_wrap(message_name, out=True)
		if isinstance(message_wrap, error.ErrorType):
			return message_wrap
		return message_wrap.get_message_data(to_dict=to_dict, glitch=glitch)

	def get_data(self, message_name, path_list, glitch=False, to_dict=True, copy=True):
		message_wrap = self.get_message_wrap(message_name, out=True)
		if isinstance(message_wrap, error.ErrorType):
			return message_wrap
		return message_wrap.get_data(path_list, glitch, to_dict, copy)

	def reset_data(self, message_name):
		message_wrap = self.get_message_wrap(message_name, out=True)
		if isinstance(message_wrap, error.ErrorType):
			return message_wrap
		return message_wrap.reset_data()

	def get_message_wrap(self, message_name, out=False):
		if (message_wrap := self.get_message(message_name)) is None:
			return error.ErrorType.MESSAGE_NOT_FOUND
		if out and message_wrap.direction is not enums.MessageDirectionType.OUT:
			return error.ErrorType.NOT_OUT_MESSAGE
		return message_wrap

	# Periodic Message Support

	def is_periodic_active(self, message_name):
		return self.get_message(message_name).periodic


class SpecNodeWrapper(EnlargedNodeWrapper):
	"""
	Implementation for InterfaceWrapper.
	Contains In/Out MessageWrapper objects as class members
	"""

	def __init__(self, **kwargs):
		super(SpecNodeWrapper, self).__init__(**kwargs)

	def serialize(self, message_name):
		message_wrap = self.get_message(message_name)
		if message_wrap.direction in (enums.MessageDirectionType.OUT, enums.MessageDirectionType.TWO_WAY):
			return message_wrap.serialize()

	def deserialize(self, buffer, to_dict=True):
		message = self.interface_pkg.deserialize(buffer)
		if isinstance(message, tuple):
			message = message[0]
		if to_dict:
			message = message.to_dict()
		return message

	def get_message_name_from_buffer(self, buffer):
		# To be defined
		raise NotImplementedError

	def msgid_sender_length(self):
		# To be defined
		# return [None, None, None]
		raise NotImplementedError

	def get_message_length_start_end_bytes(self):
		# put here the retriever for the first and last bytes indicating the buffer length
		# return [None, None]
		raise NotImplementedError


class ZMQNodeWrapper(NodeWrapper):
	def __init__(self, **kwargs):
		super(ZMQNodeWrapper, self).__init__(**kwargs)
		if config.default_zmq_handlers_enabled:
			zmq_default_handlers = importlib.import_module(
				'.handlers.zmq_handlers', package='rsimulator.network')
			zmq_default_handlers.connect_handlers(self.name)
		self.last_message_sent = None
		self.response = None

	def init_messages(self, messages):
		for name, structure in messages.items():
			self.messages[name] = self.interface_pkg.Message(name)

	def update_payload(self, message_type, **kwargs):
		for key, value in kwargs.items():
			self.messages[message_type].payload[key] = value

	def set_payload(self, message_type, payload):
		self.messages[message_type].payload = payload

	def get_payload(self, message_type):
		return self.messages[message_type].payload

	def serialize(self, message_name):
		return self.messages[message_name].serialize()

	def deserialize(self, buffer, to_dict=True):
		return self.interface_pkg.deserialize(buffer, to_dict)

	def send_message(self, message_name):
		self.response = None
		self.last_message_sent = message_name
		super().send_message(message_name)

	def send_buffer(self, buffer):
		self.response = None
		self.last_message_sent = 'Generic buffer'
		super().send_buffer(buffer)


	def get_response(self):
		for _ in range(60):
			if self.response is not None:
				return self.response
			time.sleep(1)
		self.logger.error(f'Response not received for {self.last_message_sent}')
		return self.response


def get_node_wrapper(protocol: enums.ProtocolType):
	return NodeWrapper if protocol is enums.ProtocolType.TCP else \
		NodeWrapper if protocol is enums.ProtocolType.UDP else \
		SpecNodeWrapper if protocol is enums.ProtocolType.SPEC_TCP else \
		SpecNodeWrapper if protocol is enums.ProtocolType.SPEC_UDP else \
		ZMQNodeWrapper if 'zmq' in protocol.name.lower() else None
