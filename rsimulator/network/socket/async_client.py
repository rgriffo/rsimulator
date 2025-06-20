import asyncio
import zmq
import zmq.asyncio
import time

from ...utils import enums
from ...conf.network import network_config as config


class BaseClient:
    def __init__(self, parent_node):
        self.pn = parent_node
        self.message_queue = None

    async def add(self, buffer):
        await self.message_queue.put(buffer)

    async def handle_queue(self):
        self.message_queue = asyncio.Queue()
        while self.pn.running:
            buffer = await self.message_queue.get()
            if buffer == "EXIT":
                break
            await self.send(buffer)

    async def send(self, buffer):
        raise NotImplementedError("")

    async def run(self):
        raise NotImplementedError("")


class TCPClient(BaseClient):

    def __init__(self, parent_node):
        super().__init__(parent_node)
        self.reader = None
        self.writer = None

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(self.pn.host, self.pn.port)
        self.pn.logger.info(f"Client {self.pn.name} connected to {self.pn.host}:{self.pn.port}")

    async def read_full_message(self):
        buffer = self.reader.read(4096)
        if not buffer:
            return
        message = self.pn.deserialize(buffer, to_dict=False)
        self.pn.logger.debug(f"Message received: {message}")
        return buffer

    async def send(self, buffer):
        if self.writer.is_closing():
            self.pn.logger.error(f"Cannot send messages: Not connected to server!")
        if buffer is None:
            return
        self.writer.write(buffer)
        await self.writer.drain()

    async def receive(self):
        while self.pn.running:
            try:
                buffer = await self.read_full_message()
                if not buffer:
                    continue
            except asyncio.CancelledError:
                self.pn.logger.error(f"asyncio.CancelledError")
            except Exception as e:
                self.pn.logger.error(f"", exc=e)

    async def run(self):

        await self.connect()

        sender_task = asyncio.create_task(self.handle_queue())
        receiver_task = asyncio.create_task(self.receive())

        await sender_task
        receiver_task.cancel()
        self.pn.logger.info(f"Closing {self.pn.name} connection")
        self.writer.close()
        await self.writer.wait_closed()


class UDPClient(BaseClient, asyncio.DatagramProtocol):

    def __init__(self, parent_node):
        BaseClient.__init__(self, parent_node)
        asyncio.DatagramProtocol.__init__(self)
        self.transport = None

    async def connect(self):
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: self, remote_addr=(self.pn.host, self.pn.port)
        )
        self.pn.logger.info(f"{self.pn.name} connected to {self.pn.host}:{self.pn.port}")

    def datagram_received(self, data, addr):
        message = data.decode()
        self.pn.logger.debug(f"Received message from {addr}: {message}")

    async def send(self, buffer):
        try:
            self.pn.logger.debug(f"Sending message: {buffer}")
            self.transport.sendto(buffer, (self.pn.host, self.pn.port))
        except Exception as e:
            self.pn.logger.error(f"Cannot send message!", exc=e)

    async def run(self):
        await self.connect()
        await self.handle_queue()
        self.transport.close()


class ZMQReqClient(BaseClient):

    def __init__(self, parent_node):
        super().__init__(parent_node)
        self.context = zmq.asyncio.Context()
        self.socket = None

    async def connect(self):
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{self.pn.host}:{self.pn.port}")

        # while self.pn.running:
        #     try:
        #         await self.socket.send_string(config.ZMQ_CONNECTION_REQUEST)
        #         self.pn.logger.info(f"Client status: {self.pn.name} is waiting for connection...")
        #         response = await asyncio.wait_for(self.socket.recv_string(), 1)
        #         if response == config.ZMQ_CONNECTION_REPLY:
        #             self.pn.logger.info(f"Client status: {self.pn.name} CONNECTED")
        #             self.pn.connected = True
        #             return
        #     except zmq.error.ZMQError as e:
        #         self.pn.logger.info(f"Retrying... {e}")
        #         await asyncio.sleep(1)
        #     except asyncio.TimeoutError as e:
        #         self.pn.logger.info(f"Timeout... {e}")
        #         await asyncio.sleep(1)
        #     except Exception as e:
        #         self.pn.logger.warning(f'Client status: {self.pn.name} retrying to connect', exc=e)
        #         await asyncio.sleep(1)

    async def send(self, buffer):
        try:
            await self.socket.send(buffer)
            message = self.pn.deserialize(buffer, to_dict=False)
            self.pn.logger.debug(f"Message {message.type} sent: {message.payload}")

            response = await self.socket.recv()
            response = self.pn.deserialize(response, to_dict=False)
            self.pn.logger.debug(f"Response for {message.type} received: {response.payload}")
            self.pn.response = response
        except Exception as e:
            self.pn.logger.error(f"Cannot send message!", exc=e)

    async def run(self):
        await self.connect()
        await self.handle_queue()
        self.close()

    def close(self):
        if self.socket:
            self.socket.close()
        self.context.term()
        self.pn.logger(f"{self.pn.name} client disconnected.")


class ZMQPushClient(BaseClient):

    def __init__(self, parent_node):
        super().__init__(parent_node)
        self.context = zmq.asyncio.Context()
        self.socket = None

    async def connect(self):
        self.socket = self.context.socket(zmq.PUSH)
        self.socket.connect(f"tcp://{self.pn.host}:{self.pn.port}")
        await self.ping_pong()

    async def ping_pong(self):
        while self.pn.running:
            try:
                await self.socket.send_string(config.ZMQ_CONNECTION_REQUEST)
                self.pn.logger.info(f"Client status: {self.pn.name} is waiting for connection...")
                response = await asyncio.wait_for(self.socket.recv_string(), 1)
                if response == config.ZMQ_CONNECTION_REPLY:
                    self.pn.logger.info(f"Client status: {self.pn.name} CONNECTED")
                    self.pn.connected = True
                    return
            except zmq.error.ZMQError:
                await asyncio.sleep(1)
                continue
            except asyncio.TimeoutError:
                await asyncio.sleep(1)
            except Exception as e:
                self.pn.logger.warning(f'Client status: {self.pn.name} retrying to connect', exc=e)
                await asyncio.sleep(1)

    async def send(self, buffer):
        try:
            await self.socket.send(buffer)
            message = self.pn.deserialize(buffer, to_dict=False)
            self.pn.logger.debug(f"Message {message.type} sent: {message.payload}")
        except Exception as e:
            self.pn.logger.error(f"Cannot send message!", exc=e)

    async def run(self):
        await self.connect()
        await self.handle_queue()
        self.close()

    def close(self):
        if self.socket:
            self.socket.close()
        self.context.term()
        self.pn.logger(f"{self.pn.name} client disconnected.")


def get_async_client(protocol: enums.ProtocolType):
    return TCPClient if protocol is enums.ProtocolType.TCP else \
        UDPClient if protocol is enums.ProtocolType.UDP else \
            ZMQReqClient if protocol is enums.ProtocolType.ZMQ_REQ else \
                ZMQPushClient if protocol is enums.ProtocolType.ZMQ_PUSH else None