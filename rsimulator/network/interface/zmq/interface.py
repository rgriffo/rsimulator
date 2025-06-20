import json
import logging
from ....utils import rlogging
from ....conf.network import network_config as config



class Message:
    logger = rlogging.RLogger("ZmqInterface", log_level=logging.INFO, file_name=config.network_log_path())

    def __init__(self, message_type, payload=None):
        """
        Generic message that will be sent from suite to simulator
        :param message_type: Message type
        :param payload: payload associated with the type
        """
        self._type = message_type
        self._payload = payload or dict()

    @property
    def type(self):
        return self._type

    @property
    def payload(self):
        return self._payload

    @payload.setter
    def payload(self, value):
        self._payload = value

    def to_dict(self):
        return {
            "type": self.type,
            "payload": self.payload
        }

    @classmethod
    def from_dict(cls, _dict):
        try:
            message = Message(_dict['type'], _dict['payload'])
        except Exception as e:
           cls.logger.error(f'Received malformed converter dict: {_dict}', exc=e)
           return None
        else:
            return message


    def serialize(self):
        return json.dumps(self.to_dict()).encode('utf-8')


def serialize(message):
    if isinstance(message, dict):
        return Message.from_dict(message).serialize()
    elif isinstance(message, Message):
        return message.serialize()


def deserialize(buffer, to_dict=True):
    _dict = json.loads(buffer.decode('utf-8'))
    if to_dict:
        return _dict
    return Message.from_dict(_dict)
