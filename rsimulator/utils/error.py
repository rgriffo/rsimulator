from enum import Enum


class ErrorType(Enum):
	GENERIC = "Generic Error"
	NOT_FOUND = "Not Found Error"
	NOT_A_LIST = "Not a list"
	INDEX_OUT_OF_RANGE = "Index out of range"

	NODE_NOT_FOUND = "Node not found in the Network"
	MESSAGE_NOT_FOUND = "Message not found Error"
	MESSAGE_NOT_UNIQUE = "The Message Name is not unique in the Network"
	NOT_OUT_MESSAGE = "The Requested message has not out direction"

	def value_with_args(self, *args):
		return f'{self.value} ({args})'

