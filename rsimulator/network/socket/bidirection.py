import abc
from ...conf.network import network_config as config
from .server import Server
from .client import Client


class Bidirectional(Server, Client):
	def __init__(self, parent_node):
		Server.__init__(parent_node)
		Client.__init__(parent_node)

