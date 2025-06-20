from ...utils import enums

from .out_message_wrapper import OutMessageWrapper, SpecOutMessageWrapper
from .in_message_wrapper import InMessageWrapper, SpecInMessageWrapper


class TwoWayMessageWrapper(OutMessageWrapper, InMessageWrapper):
	direction = enums.MessageDirectionType.TWO_WAY

	def __init__(self, **kwargs):
		InMessageWrapper.__init__(self, **kwargs)
		OutMessageWrapper.__init__(self, **kwargs)


class SpecTwoWayMessageWrapper(SpecOutMessageWrapper, SpecInMessageWrapper):

	def __init__(self, **kwargs):
		SpecOutMessageWrapper.__init__(self, **kwargs)
		SpecInMessageWrapper.__init__(self, **kwargs)


def get_two_way_message_wrapper(protocol: enums.ProtocolType):
	return TwoWayMessageWrapper if protocol is enums.ProtocolType.TCP else \
		TwoWayMessageWrapper if protocol is enums.ProtocolType.UDP else \
		SpecTwoWayMessageWrapper if protocol is enums.ProtocolType.SPEC_TCP else \
		SpecTwoWayMessageWrapper if protocol is enums.ProtocolType.SPEC_UDP else None