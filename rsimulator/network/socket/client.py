import socket
import threading
import time
import zmq
import abc

from ...utils import enums
from ...conf.network import network_config as config
from ...utils import rsignal


class Client(abc.ABC):

	def __init__(self, parent_node):
		self.pn = parent_node
		self.socket = None

	@abc.abstractmethod
	def connect(self):
		pass

	@abc.abstractmethod
	def send_message(self, buffer):
		pass

	def stop(self):
		try:
			self.socket.shutdown(socket.SHUT_RDWR)
		except OSError:
			pass
		self.socket.close()

	def handle_queue(self):
		try:
			while self.pn.running:
				message = self.pn.message_queue.get()
				if message == "EXIT":
					self.pn.logger.info("Exiting message handling.")
					break
				self.send_message(message)
		except Exception as e:
			self.pn.logger.error(f"", exc=e)
		finally:
			self.stop()


class TCPClient(Client):

	def __init__(self, parent_node):
		super(TCPClient, self).__init__(parent_node)

	def connect(self):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
		self.socket.settimeout(config.SERVER_SOCKET_TIMEOUT)
		attempt = 0
		while attempt < config.CLIENT_CONNECTION_ATTEMPTS:
			try:
				self.socket.connect((self.pn.host, self.pn.port))
				self.pn.logger.info(f"Client status: CONNECTED to {self.pn.host}:{self.pn.port}")
				self.pn.connected = True
				threading.Thread(target=self.receive_message,
					name=f'{self.pn.name}_receiver').start()
				return
			except socket.timeout:
				continue
			except Exception as e:
				self.pn.logger.warning(f'Client status: Retrying to connect to {self.pn.host}:{self.pn.port} ({e})')
				time.sleep(1)
		raise ConnectionError(f'Connection failed (node: {self.pn.name})')

	def send_message(self, buffer):
		if self.socket:
			self.socket.sendall(buffer)
			self.pn.logger.debug(f"Message sent: {buffer}")
		else:
			self.pn.logger.error(f"Cannot send messages: Not connected to server!")

	def receive_message(self):
		while self.pn.running:
			try:
				data = self.socket.recv(4096)
				if not data:
					break
				self.pn.logger.debug(f"Message received: {data}")
			except socket.timeout:
				continue
			except Exception as e:
				self.pn.logger.error(f"", exc=e)
				break


class SpecTCPClient(TCPClient):

	def __init__(self, parent_node):
		super(SpecTCPClient, self).__init__(parent_node)

	def send_message(self, buffer):
		"""Send a serialized message to the server."""
		message_name = self.pn.get_message_name_from_buffer(buffer)
		if self.socket:
			self.socket.sendall(buffer)

			if message_name not in self.pn._exclude_from_log:
				self.pn.logger.debug(f"Message {message_name} sent: {self.pn.deserialize(buffer)}")
		else:
			self.pn.logger.error(f"Cannot send messages: Not connected to server!")

	def receive_message(self):
		"""Receive messages from the server."""
		while self.pn.running:
			try:
				[start, end] = self.pn.get_message_length_start_end_bytes()
				id_length = self.socket.recv(end)
				message_length = int.from_bytes(id_length[start:],
					self.pn.interface_pkg.BYTE_ORDER.lower())

				buffer = id_length
				remaining = message_length - 8
				while remaining > 0:
					new_buffer = self.socket.recv(remaining)
					remaining -= len(new_buffer)
					buffer += new_buffer

				if not buffer:
					break

				# Dispatch message to appropriate handler
				response_buffer = self.pn.dispatcher.dispatch(buffer)

			except socket.timeout:
				continue
			except Exception as e:
				self.pn.logger.error(f"", exc=e)
				break


class UDPClient(Client):

	def __init__(self, parent_node):
		super(UDPClient, self).__init__(parent_node)

	def connect(self):
		"""Initialize the UDP socket."""
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.socket.settimeout(config.SERVER_SOCKET_TIMEOUT)
		self.pn.logger.info(f"Client status: LINKED to {self.pn.host}:{self.pn.port}")
		self.pn.connected = True

	def send_message(self, buffer):
		"""Send a serialized message to the server."""
		self.socket.sendto(buffer, (self.pn.host, self.pn.port))
		self.pn.logger.debug(f"Message sent: {buffer.decode()}")

	def receive_message(self):
		"""Receive messages from the server."""
		while self.pn.running:
			try:
				data, addr = self.socket.recvfrom(1024)
				if not data:
					break
				response_buffer = self.pn.dispatcher.dispatch(data)
			except socket.timeout:
				continue


class SpecUDPClient(UDPClient):

	def __init__(self, parent_node):
		super(SpecUDPClient, self).__init__(parent_node)

	def send_message(self, buffer):
		"""Send a serialized message to the server."""
		message_name = self.pn.get_message_name_from_buffer(buffer)

		try:
			self.socket.sendto(buffer, (self.pn.host, self.pn.port))
			if message_name not in self.pn._exclude_from_log:
				self.pn.logger.debug(f"Message {message_name} sent: "
									   f"{self.pn.deserialize(buffer)}")
		except Exception as e:
			self.pn.logger.error(f"Cannot send messages: Not connected to server!")

	def receive_message(self):
		"""Receive messages from the server."""
		while self.pn.running:
			try:
				[start, end] = self.pn.get_message_length_start_end_bytes()
				id_length, addr = self.socket.recvfrom(end)
				print(f'RECEIVING from {addr}...')
				message_length = int.from_bytes(id_length[start:], self.pn.interface_pkg.BYTE_ORDER.lower())

				buffer = id_length
				remaining = message_length - 8
				while remaining > 0:
					new_buffer, addr = self.socket.recvfrom(remaining)
					remaining -= len(new_buffer)
					buffer += new_buffer

				if not buffer:
					continue

				# Dispatch message to appropriate handler
				response_buffer = self.pn.dispatcher.dispatch(buffer)

			except socket.timeout:
				continue
			except Exception as e:
				self.pn.logger.error(f"Error receiving message.", exc=e)
				break


class ZMQClient(Client):

	def __init__(self, parent_node):
		super(ZMQClient, self).__init__(parent_node)
		self.address = f"tcp://{parent_node.host}:{parent_node.port}"
		self.context = zmq.Context()
		self.response = self.pn.response

	def connect(self, wait_connection=True):
		self.socket = self.context.socket(zmq.REQ)
		self.socket.connect(self.address)

		if wait_connection:
			while self.pn.running:
				try:
					self.socket.send_string(config.ZMQ_CONNECTION_REQUEST)
					self.pn.logger.info(f"{self.pn.name} is waiting for connection to {self.address}...")

					response = self.socket.recv_string()
					if response == config.ZMQ_CONNECTION_REPLY:
						self.pn.logger.info(f"Client status: CONNECTED to {self.address}")
						self.pn.connected = True
						return

				except zmq.error.Again:
					continue

				except Exception as e:
					self.pn.logger.warning(f'Client status: Retrying to connect to {self.address}', exc=e)
					time.sleep(1)

	def send_message(self, buffer):
		try:
			message = self.pn.deserialize(buffer, to_dict=False)
			self.socket.send(buffer)
			self.pn.logger.debug(f"Message {message.type} sent: {message.payload}")
			response_buffer = self.socket.recv()
			self.pn.response = self.pn.interface_pkg.deserialize(response_buffer, to_dict=False)
			self.pn.logger.debug(f"Response for {message.type} received: {self.pn.response.payload}")
		except Exception as e:
			self.pn.logger.error(f"", exc=e)

	def stop(self):
		self.context.term()
		super().stop()


def get_client(protocol: enums.ProtocolType):
	return TCPClient if protocol is enums.ProtocolType.TCP else \
		   UDPClient if protocol is enums.ProtocolType.UDP else \
		   SpecTCPClient if protocol is enums.ProtocolType.SPEC_TCP else \
		   SpecUDPClient if protocol is enums.ProtocolType.SPEC_UDP else \
		   ZMQClient if 'zmq' in protocol.name.lower() else None
