
from ... import enums
from ... import network_config
from .zmq import interface


def get_interface_pkg(protocol: enums.ProtocolType, node_name=None):
	uploaded_interface_pkg = network_config.interface_pkg(node_name)
	if uploaded_interface_pkg is not None:
		return uploaded_interface_pkg

	if 'zmq' in protocol.name.lower():
		return interface