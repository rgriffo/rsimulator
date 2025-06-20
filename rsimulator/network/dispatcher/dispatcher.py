from abc import ABC
import json
import struct
import sys

from ...utils import enums
from ...conf.network import network_config as config
from ...utils.rsignal import signal_instance


class Dispatcher(ABC):
	def __init__(self, parent_node=None):
		self.parent_node = parent_node
		self.logger = parent_node.logger

	def dispatch(self, message):
		"""
		Dispatches a message to the appropriate handler
		:param message: The message to process
		:return: The result from the handler
		"""
		self.parent_node.logger.debug(f"Message received! Buffer: {message}")
		return "success".encode('utf-8')


class SpecDispatcher(Dispatcher):
	def __init__(self, parent_node=None):
		super(SpecDispatcher, self).__init__(parent_node)

	def dispatch(self, message):
		"""
		Dispatches a message to the appropriate handler
		:param message: The message to process
		:return: The result from the handler
		"""
		try:
			message_obj = self.parent_node.deserialize(message, toDict=False)
			if message_obj is None:
				raise BufferError(f'{self.parent_node.name} dispatcher received a null message')
		except Exception as e:
			self.logger.critical(f'Exception (dispatcher: dispatch): {e}')

		message_dict = message_obj.toDict()
		message_name = message_obj.__class__.__name__


		self.logger.only_debug(f"Message {message_obj.__class__.__name__} received: {message_dict}")
		self.logger.only_info(f"Message {message_obj.__class__.__name__} received!")

		# 1. Updated message counter
		getattr(self.parent_node, message_name).increment()

		# 2. Save last message
		getattr(self.parent_node, message_name).append(message_dict)

		# 3. Emit signal
		return signal_instance.emit((self.parent_node.name, message_name), data=message_dict, logger=self.logger)



class ZMQDispatcher(Dispatcher):
	def __init__(self, parent_node=None):
		super(ZMQDispatcher, self).__init__(parent_node)

	def dispatch(self, buffer):
		"""
		Dispatches a message to the appropriate handler
		:param buffer: The message to process
		:return: The result from the handler
		"""
		message = self.parent_node.deserialize(buffer, to_dict=False)
		self.logger.debug(f"Message {message.type} received. Payload: {message.payload}")

		results_dict_list = signal_instance.emit((self.parent_node.name, message.type),
									  payload=message.payload, logger=self.logger)

		if results_dict_list:
			self.logger.debug(f'Zmq Response: {results_dict_list[0]}')
			return self.parent_node.interface_pkg.serialize(results_dict_list[0])

		return json.dumps('No answer').encode('utf-8')



def get_dispatcher(protocol: enums.ProtocolType, node_name=None):
	uploaded_dispatcher = config.dispatcher(node_name)
	if uploaded_dispatcher is not None:
		return uploaded_dispatcher

	return Dispatcher if protocol is enums.ProtocolType.TCP else \
		Dispatcher if protocol is enums.ProtocolType.UDP else \
		SpecDispatcher if protocol is enums.ProtocolType.SPEC_TCP else \
		SpecDispatcher if protocol is enums.ProtocolType.SPEC_UDP else \
		ZMQDispatcher if 'zmq' in protocol.name.lower() else None

