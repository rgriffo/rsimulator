import asyncio
from time import sleep

import zmq
import zmq.asyncio
from ...conf.network import network_config as config
from ...utils import enums

class BaseServer:
    """ Classe base per tutti i server con gestione invio e ricezione """

    def __init__(self, parent_node):
        self.pn = parent_node
        self.clients = set()
        self.shutdown_event = None
        self.message_queue = None

    async def start(self):
        raise NotImplementedError("start() must be implemented.")

    async def handle_message(self, buffer, addr):
        responses = self.pn.dispatcher.dispatch(buffer)
        if hasattr(self.pn, 'get_message_name_from_buffer'):
            addr = self.pn.get_message_name_from_buffer(buffer)
        for response in responses:
            for message_name, message_buffer in response.items():
                self.pn.logger.info(f'Response to {addr}: Sending {message_name}')
                if message_buffer:
                    await self.send(message_buffer)
    # Functions to send

    async def add(self, message, addr):
        await self.message_queue.put((message, addr))

    async def handle_queue(self):
        self.message_queue = asyncio.Queue()
        while self.pn.running:
            buffer = await self.message_queue.get()
            if buffer  == "EXIT":
                break
            await self.send(buffer)


    async def send(self, buffer):
        raise NotImplementedError("send() must be implemented")


class TCPServer(BaseServer):

    def __init__(self, parent_node):
        super().__init__(parent_node)
        self.server = None
        self.tasks = list()

    async def start(self):
        self.shutdown_event = asyncio.Event()
        task = asyncio.create_task(self.handle_queue())
        self.tasks.append(task)
        self.pn.logger.info(f"TCP Server {self.pn.name} listening on {self.pn.host}:{self.pn.port}")
        self.server = await asyncio.start_server(self.handle_client, self.pn.host, self.pn.port)
        async with self.server:
            await self.server.serve_forever()
        await self.close()

    async def close(self):
        self.pn.logger.info(f"Shutdown event received! Closing server {self.pn.name}...")
        self.server.close()
        await self.server.wait_closed()
        await asyncio.gather(*self.tasks)

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        self.pn.logger.debug(f"{self.pn.name} connected to {addr}")
        self.clients.add(writer)
        try:
            while self.pn.running:
                buffer = await self.read_full_message(reader)
                if not buffer:
                    break
                await self.handle_message(buffer, addr)
        except Exception as e:
            self.pn.logger.error(f"", exc=e)
        finally:
            self.clients.remove(writer)
            writer.close()
            await writer.wait_closed()

    async def read_full_message(self, reader):
        buffer = reader.read(4096)
        if not buffer:
            return
        self.pn.deserialize(buffer, to_dict=False)
        return buffer

    async def send(self, buffer):
        for client in self.clients:
            try:
                client.write(buffer)
                await client.drain()
            except Exception as e:
                self.pn.logger.error(f"Error sending message to {client}", exc=e)
                # self.clients.remove(client)


class UDPServer(BaseServer, asyncio.DatagramProtocol):

    def __init__(self, parent_node):
        BaseServer.__init__(self, parent_node)
        asyncio.DatagramProtocol.__init__(self)
        self.transport = None
        self.tasks = set()

    async def start(self):
        self.shutdown_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(lambda: self, local_addr=(self.pn.host, self.pn.port))
        self.pn.logger.info(f"UDP Server {self.pn.name} listening on {self.pn.host}:{self.pn.port}")
        asyncio.create_task(self.handle_queue())
        await self.shutdown_event.wait()
        await self.close()

    async def close(self):
        self.pn.logger.info(f"Shutdown event received! Closing server {self.pn.name}...")
        if self.transport:
            self.transport.close()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    def datagram_received(self, data, addr):
        self.clients.add(addr)
        buffer = data.decode()
        self.pn.logger.debug(f"Received message from {addr}: {buffer}")
        task = asyncio.create_task(self.handle_message(buffer, addr))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def send(self, buffer):
        for client in self.clients:
            self.transport.sendto(buffer, client)


class ZMQReplyServer(BaseServer):

    def __init__(self, parent_node):
        super().__init__(parent_node)
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.REP)
        self.tasks = list()

    async def start(self):
        self.shutdown_event = asyncio.Event()
        self.socket.bind(f"tcp://{self.pn.host}:{self.pn.port}")
        self.pn.logger.info(f"Zmq Server listening on {self.pn.host}:{self.pn.port}...")
        # task = asyncio.create_task(self.handle_requests())
        # self.tasks.append(task)
        await self.handle_requests()
        await self.shutdown_event.wait()
        await self.close()

    async def handle_requests(self):
        while self.pn.running:
            request = await self.socket.recv()
            # if request.decode('utf-8') == config.ZMQ_CONNECTION_REQUEST:
            #     self.socket.send_string(config.ZMQ_CONNECTION_REPLY)
            #     self.pn.connected = True
            #     self.pn.logger.info('Zmq server connection success!')
            #     continue
            await self.handle_message(request, f'{self.pn.host}:{self.pn.port}')


    async def handle_message(self, buffer, addr):
        try:
            buffer = self.pn.dispatcher.dispatch(buffer)[0]
        except Exception as e:
            self.pn.logger.error('Reply needed in ZMQ REQ-REPLY', exc=e)
        else:
            message = self.pn.interface_pkg.deserialize(buffer, to_dict=False)
            self.pn.logger.debug(f'Responding {message.type}: {message.payload}')
            await self.send(buffer)

    async def close(self):
        self.pn.logger.info(f"Shutdown event received! Closing server {self.pn.name}...")
        self.socket.close()
        self.context.term()
        await asyncio.gather(*self.tasks)

def get_async_server(protocol: enums.ProtocolType):
    return TCPServer if protocol is enums.ProtocolType.TCP else \
           UDPServer if protocol is enums.ProtocolType.UDP else \
           ZMQReplyServer if protocol is enums.ProtocolType.ZMQ_REP else None