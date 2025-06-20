import enum

class RequirementStateType(enum.Enum):
	PENDING = enum.auto()
	PASS = enum.auto()
	FAIL = enum.auto

class MessageDirectionType(enum.Enum):
	UNKNOWN = None
	IN = enum.auto()
	OUT = enum.auto()
	TWO_WAY = enum.auto()

class NodeRoleType(enum.Enum):
	UNKNOWN = None
	SERVER = enum.auto()
	CLIENT = enum.auto()
	BIDIRECTIONAL = enum.auto()

class ProtocolType(enum.Enum):
	UNKNOWN = None
	TCP = enum.auto()
	UDP = enum.auto()
	ZMQ = enum.auto()
	SPEC_TCP = enum.auto()
	SPEC_UDP = enum.auto()

	ZMQ_REQ = enum.auto()
	ZMQ_PUSH = enum.auto()
	ZMQ_REP = enum.auto()
	ZMQ_PULL = enum.auto()
