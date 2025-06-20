import socket
import threading
import time

import zmq
import abc
import struct

from ...utils import enums
from ...conf.network import network_config as config
from ...utils.rsignal import signal_instance

BUFFER_SIZE = 4096

class Server(abc.ABC):

	def __init__(self, parent_node):
		self.pn = parent_node
		self.server_socket = None
		self.client_threads = list()

	@abc.abstractmethod
	def start(self):
		pass

	def send_message(self, client, buffer):
		client.sendall(buffer)
		self.pn.logger.debug(f"Message sent: {buffer}")

	def handle_queue(self, client_socket):
		try:
			while self.pn.running:
				message = self.pn.message_queue.get()
				if message == "EXIT":
					self.pn.logger.info("Exiting message handling.")
					break
				self.send_message(client_socket, message)
		except Exception as e:
			self.pn.logger.error(f"", exc=e)
		finally:
			client_socket.close()

	def stop(self):
		self.server_socket.close()
		for thread in self.client_threads:
			thread.join()


class TCPServer(Server):

	def __init__(self, parent_node=None):
		super(TCPServer, self).__init__(parent_node)

	def start(self):
		self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

		# In questo modo evito "Address already in use"
		self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

		# Imposto SO_LINGER per chiudere subito la connessione senza TIME_WAIT
		linger = struct.pack('ii', 1, 0)
		self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)

		self.server_socket.bind((self.pn.host, self.pn.port))
		self.server_socket.listen(5)
		self.server_socket.settimeout(config.SERVER_SOCKET_TIMEOUT)
		self.pn.logger.info(f"{self.pn.name} status: LISTENING on {self.pn.host}:{self.pn.port}...")
		self.accept_clients()

	def accept_clients(self):
		while self.pn.running:
			try:
				client_socket, client_address = self.server_socket.accept()
				client_socket.settimeout(config.SERVER_SOCKET_TIMEOUT)
				self.pn.logger.info(f"New connection from {client_address}")
				signal_instance.emit(f'{self.pn.name}_connected', logger=self.pn.logger)
				self.pn.connected = True
				_receiver = threading.Thread(target=self.handle_client, args=(client_socket, client_address),
					name=f'{self.pn.name}_{client_address}_receiver')
				_sender = threading.Thread(target=self.handle_queue, args=(client_socket,),
					name=f'{self.pn.name}_{client_address}_sender')
				self.client_threads.append(_receiver)
				self.client_threads.append(_sender)
				_receiver.start()
				_sender.start()

			except socket.timeout:
				continue
			except Exception as e:
				break
		self.stop()

	def handle_client(self, client_socket, client_address):
		while self.pn.running:
			try:
				data = client_socket.recv(1024)
				if not data:
					break
				# Dispatch message to appropriate handler
				response_buffer = self.pn.dispatcher.dispatch(data)

				if response_buffer:
					client_socket.sendall(response_buffer)
			except UnicodeError as e:
				self.pn.logger.error(f"", exc=e)
				break
		client_socket.shutdown(socket.SHUT_RDWR)
		client_socket.close()


class SpecTCPServer(TCPServer):

	def __init__(self, parent_node=None):
		super(SpecTCPServer, self).__init__(parent_node)

	def handle_client(self, client_socket, client_address):
		while self.pn.running:
			try:
				[start, end] = self.pn.get_message_length_start_end_bytes()
				id_length = client_socket.recv(end)
				message_length = int.from_bytes(id_length[start:], self.pn.interface_pkg.BYTE_ORDER.lower())
				data = id_length
				remaining = message_length - 8
				while remaining > 0:
					new_data = client_socket.recv(remaining)
					remaining -= len(new_data)
					data += new_data

				if not data:
					continue

				# Dispatch message to appropriate handler
				responses = self.pn.dispatcher.dispatch(data)
				received_message_name = self.pn.get_message_name_from_buffer(data)
				for response in responses:
					for message_name, message_buffer in response.items():
						message_dict = self.pn.deserialize(message_buffer)
						self.pn.logger.debug(f'Response to {received_message_name}: Sending {message_name}: {message_dict}')
						client_socket.sendall(message_buffer)
			except UnicodeError as e:
				self.pn.logger.error(f"", exc=e)
				break
			except socket.timeout:
				continue
			except Exception as e:
				self.pn.logger.error(f"", exc=e)
		client_socket.close()

	def send_message(self, client, buffer):
		"""Send a serialized message to the client."""
		message_name = self.pn.get_message_name_from_buffer(buffer)
		try:
			client.sendall(buffer)
		except ConnectionError as e:
			self.pn.logger.error(f'Connection Error: message {message_name} not sent', exc=e)
		except Exception as e:
			self.pn.logger.error(f'Error: message {message_name} not sent', exc=e)
		else:
			# self.pn.logger.only_info(f"Message {message_name} sent!")
			self.pn.logger.debug(f"Message {message_name} sent: "
								   f"{self.pn.deserialize(buffer)}")

class UDPServer(Server):

	def __init__(self, parent_node=None):
		super(UDPServer, self).__init__(parent_node)

	def start(self):
		self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.server_socket.bind((self.pn.host, self.pn.port))
		self.server_socket.settimeout(config.SERVER_SOCKET_TIMEOUT)
		self.pn.logger.info(f"{self.pn.name} status: LISTENING on {self.pn.host}:{self.pn.port}...")
		self.pn.connected = True
		self.receive_messages()

	def receive_messages(self):
		while self.pn.running:
			try:
				data, addr = self.server_socket.recvfrom(1024)
				if not data:
					continue
				# self.pn.logger.only_info(f"Message received from {addr}!")
				self.pn.logger.debug(f"Received message from {addr}: {data.decode('utf-8')}")
				# Dispatch message to appropriate handler
				response = self.pn.dispatcher.dispatch(data.decode('utf-8'))
				self.server_socket.sendto(response.encode('utf-8'), addr)
			except socket.timeout:
				continue
			except Exception as e:
				self.pn.logger.error(f"", exc=e)
		self.stop()


class SpecUDPServer(UDPServer):

	def __init__(self, parent_node=None):
		super(SpecUDPServer, self).__init__(parent_node)

	def receive_messages(self):
		while self.pn.running:
			try:
				[start, end] = self.pn.msgid_sender_length()
				data, addr = self.server_socket.recvfrom(BUFFER_SIZE)
				if len(data) < end:
					self.pn.logger.warning(f"Received a packet of length {len(data)} from {addr}, it will be ignored.")
					continue
				# ID, SENDER, LENGTH (4 byte + 2 byte + 2 byte)
				msg_id, sender, msg_length = struct.unpack("!I H H", data[start:end])
				while len(data) < msg_length:
					more_data, _ = self.server_socket.recvfrom(BUFFER_SIZE)
					data += more_data
				if not data:
					continue
				received_message_name = self.pn.get_message_name_from_buffer(data)
				responses = self.pn.dispatcher.dispatch(data)
				for response in responses:
					for message_name, message_buffer in response.items():
						message_dict = self.pn.deserialize(message_buffer)
						self.pn.logger.debug(f'Response to {received_message_name}: Sending {message_name}: {message_dict}')
					self.server_socket.sendto(response, addr)

			except socket.timeout:
				continue
			except Exception as e:
				self.pn.logger.error(f"", exc=e)
		self.stop()


class ZMQServer(Server):

	def __init__(self, parent_node=None):
		super(ZMQServer, self).__init__(parent_node)
		self.address = f"tcp://{parent_node.host}:{parent_node.port}"
		self.context = zmq.Context()

	def start(self):
		self.server_socket = self.context.socket(zmq.REP)
		self.server_socket.bind(self.address)
		self.pn.logger.info(f"{self.pn.name} status: LISTENING on {self.address}...")
		self.handle_requests()

	def handle_requests(self):
		while self.pn.running:
			try:
				# Receive the request (blocking call)
				request = self.server_socket.recv(flags=zmq.NOBLOCK)
				if request.decode('utf-8') == config.ZMQ_CONNECTION_REQUEST:
					self.server_socket.send_string(config.ZMQ_CONNECTION_REPLY)
					self.pn.connected = True
					self.pn.logger.info('Zmq server connection success!')
					signal_instance.emit(f'{self.pn.name}_connected', logger=self.pn.logger)
					continue
				response_buffer = self.pn.dispatcher.dispatch(request)
				self.server_socket.send(response_buffer)
			except zmq.Again:
				time.sleep(0.1)
			except Exception as e:
				self.pn.logger.error(f"Error (zmq handle_requests)", exc=e)
				break
		self.stop()

	def stop(self):
		self.server_socket.close()
		self.context.term()
		super().stop()


def get_server(protocol: enums.ProtocolType):
	return TCPServer if protocol is enums.ProtocolType.TCP else \
		   UDPServer if protocol is enums.ProtocolType.UDP else \
		   SpecTCPServer if protocol is enums.ProtocolType.SPEC_TCP else \
		   SpecUDPServer if protocol is enums.ProtocolType.SPEC_UDP else \
		   ZMQServer if 'zmq' in protocol.name.lower() else None
