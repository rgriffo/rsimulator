from ...utils import enums
from ...utils import error

from collections.abc import MutableSequence
from copy import deepcopy
from threading import Lock


class OutMessageWrapper:
	direction = enums.MessageDirectionType.OUT

	def __init__(self, **kwargs):
		self.parent_node = kwargs.get('parent_node')
		self.message = None  # Message instance
		self.name = kwargs.get('name')
		self.periodic = kwargs.get('periodic', False)
		self.interval = kwargs.get('interval', 1)
		self.default_data = kwargs.get('default_data')
		self.glitch_data = kwargs.get('glitch_data')
		self._is_glitching = False
		self._lock = Lock()
		self.reset_data()

	@property
	def lock(self):
		"""
		Returns the lock to be used for accessing the data.
		"""
		return self._lock

	@property
	def is_glitching(self):
		return self._is_glitching

	def get_data(self, keys, glitch=False, to_dict=True, copy=False):
		pass

	def update_data(self, keys, value, glitch=False):
		pass

	def add_items_to_list(self, keys, items, glitch=False):
		pass

	def remove_items_from_list(self, keys, indexes, glitch=False):
		pass

	def get_message_data(self, to_dict=False, glitch=False):
		pass

	def update_message(self, data, glitch=False):
		pass

	def reset_data(self):
		pass

	def serialize(self):
		pass


class SpecOutMessageWrapper(OutMessageWrapper):

	def __init__(self, **kwargs):
		super(SpecOutMessageWrapper, self).__init__(**kwargs)


	def get_data(self, keys, glitch=False, to_dict=True, copy=False):
		"""
		Internal function to navigate through dictionaries and lists.
		Handles nested dictionaries and lists treated as dictionaries with integer keys.
		:param keys: List of keys to navigate through the structure.
		:return: The leaf value or None if not found.
		:param to_dict: Return data as Dict
		:param glitch: True to get glitching data
		:param copy: True if a copy of the value is needed
		"""
		with self.lock:
			if not glitch:
				data = self.message
				for key in keys:
					if isinstance(data, object):
						data = getattr(data, key)
					elif isinstance(data, MutableSequence) and isinstance(key, int):
						try:
							data = data.__getitem__(key)
						except IndexError:
							return error.ErrorType.INDEX_OUT_OF_RANGE
					else:
						return error.ErrorType.NOT_FOUND
					if data is None:
						return error.ErrorType.NOT_FOUND
					if to_dict:
						data = data.to_dict()
			else:
				data = self.glitch_data
				for key in keys:
					data = data[key]
			if copy:
				return deepcopy(data)
			return data

	def update_data(self, keys, value, glitch=False):
		"""
		Internal function to set a value in nested dictionaries.
		Handles both dictionaries and lists treated as dictionaries with integer keys.
		:param glitch: True to set glitching data
		:param keys: List of keys to navigate through the structure.
		:param value: The value to set.
		"""

		if not glitch:
			if not keys:
				self.message = self.message.__class__.from_dict(value)
				return
			obj = self.message
			for key in keys[:-1]:
				if isinstance(obj, MutableSequence) and isinstance(key, int):
					obj = obj.__getitem__(key)
				else:
					if hasattr(obj, f'_{key}'):
						obj = getattr(obj, f'_{key}')
					else:
						obj = getattr(obj, key)
			value = getattr(obj, keys[-1]).__class__.from_dict(value)
			if hasattr(obj, f'_{keys[-1]}'):
				setattr(obj, f'_{keys[-1]}', value)
			else:
				setattr(obj, keys[-1], value)
		else:
			if not keys:
				self.glitch_data = value
				return
			obj = self.glitch_data
			for key in keys[:-1]:
				obj = obj[key]
			obj[keys[-1]] = value

	def add_items_to_list(self, keys, items, glitch=False):
		"""
		Adds an item to a specified list.
		:param keys: The path to the list to update.
		:param items: The items to add to the list.
		:param glitch: True to get glitching data
		:return: The operation status (None if success).
		"""

		if not isinstance(items, list):
			items = [items]
		with self.lock:
			_list = self.get_data(keys, glitch)

			if not glitch:
				if isinstance(_list, error.ErrorType):
					return _list
				if not isinstance(_list, MutableSequence):
					return error.ErrorType.NOT_A_LIST
				items = deepcopy(_list.__class__.from_dict(items)._list)

			_list.extend(items)

	def remove_items_from_list(self, keys, indexes, glitch=False):
		"""
        Removes an item from a specified list.
		:param keys: The path to the list to update.
		:param indexes: The indexes to be removed from the list.
		:param glitch: True to get glitching data
		:return: The operation status (None if success).
		"""
		if not isinstance(indexes, list):
			indexes = [indexes]
		with self.lock:
			_list = self.get_data(keys, glitch)
			if isinstance(_list, error.ErrorType):
				return _list
			if not isinstance(_list, MutableSequence):
				return error.ErrorType.NOT_A_LIST
			for index in indexes:
				if index < _list.__len__():
					return error.ErrorType.INDEX_OUT_OF_RANGE
				_list.pop(index)
		return

	def reset_data(self):
		"""
		Resets the data to its initial state.
		"""
		with self.lock:
			Message = getattr(self.parent_node.interface_pkg, self.name)
			self.message = Message.from_dict(self.default_data)

	def get_message_data(self, to_dict=False, glitch=False):
		message = self.message if not glitch else \
			self.message.__class__.from_dict(self.glitch_data)
		return message if not to_dict else message.to_dict()

	def update_message(self, data, glitch=False):
		if glitch:
			self.glitch_data = data
		else:
			self.message = self.message.__class__.from_dict(data)

	def serialize(self):
		if self.is_glitching:
			return self.message.__class__.from_dict(self.glitch_data).serialize()
		return self.get_message_data().serialize()


class ZMQOutMessageWrapper(OutMessageWrapper):

	def __init__(self, **kwargs):
		super(ZMQOutMessageWrapper, self).__init__(**kwargs)


	def get_message_data(self, to_dict=False, glitch=False):
		if self.message is None:
			self.reset_message()
		message = self.message if not glitch else \
			self.message.__class__.from_dict(self.glitch_data)
		return message if not to_dict else message.to_dict()

	def update_data(self, keys, value, glitch=False):
		if not self.message:
			self.reset_message()
		data = self.message.payload
		for key in keys[:-1]:
			data = data[key]
		data[keys[-1]] = value
		self.message = self.message.__class__.from_dict(data)


	def set_payload(self, payload):
		if self.message is None:
			self.reset_message()
		self.message.payload = payload

	def serialize(self):
		if self.is_glitching:
			return self.message.__class__.from_dict(self.glitch_data).serialize()
		return self.get_message_data().serialize()

	def reset_message(self):
		self.message = getattr(self.parent_node.interface_pkg, self.name)(payload={})


def get_out_message_wrapper(protocol: enums.ProtocolType):
	return OutMessageWrapper if protocol is enums.ProtocolType.TCP else \
		OutMessageWrapper if protocol is enums.ProtocolType.UDP else \
		SpecOutMessageWrapper if protocol is enums.ProtocolType.SPEC_TCP else \
		SpecOutMessageWrapper if protocol is enums.ProtocolType.SPEC_UDP else \
		ZMQOutMessageWrapper if protocol is enums.ProtocolType.ZMQ else None
