import functools
import time
import asyncio

from ...utils import error
from ...conf.network import network_config

from ..network import get_network
from ...statemachine import requirements, get_sm_manager, get_global_manager
from ...utils.rsignal import signal_instance

# PAY ATTENTION TO EXCEPTION_HANDLER --> IT ADJUSTS THE PAYLOAD!
# HANDLER MUST HAVE TWO INPUT PARAMETERS: PAYLOAD e LOGGER
# @RG



descriptor = network_config.get_zmq_default_descriptor()

def check_payload(message_type, payload, logger):
	# Go in error if required key not present
	for required_key in descriptor[message_type]['payload']['required']:
		if required_key not in payload:
			_error = f'{required_key} not included in {message_type} payload'
			logger.error(_error)
			return error_reply('RequiredKeyError', _error)
	# Set default value if optional key not present
	for optional_key, optional_value in descriptor[message_type]['payload']['optional'].items():
		payload.setdefault(optional_key, optional_value)

def exception_handler(func):
	@functools.wraps(func)
	def wrapper(*args, **kwargs):
		payload = kwargs.get("payload") if 'payload' in kwargs else args[0]
		logger = kwargs.get("logger") or args[1]
		message_name = func.__name__.replace('handle_', '')
		if _check := check_payload(message_name, payload, logger) is not None:
			return _check
		try:
			logger.debug(f'Handling {message_name}: {payload}')
			return func(*args, **kwargs)
		except Exception as e:
			logger.error(f'', exc=e)
			return error_reply(e.__class__.__name__, repr(e))
	return wrapper

def error_reply(error_type, detail):
	return dict(
		type='ErrorReply',
		payload={'error': error_type, 'detail': detail}
	)

def success_reply():
	return dict(type='SuccessReply', payload={})

def reply(reply_type, **payload):
	return dict(type=reply_type, payload=payload)

def get_node(payload, wrap=False):
	if node_name := payload['node'] is None:
		node_name = get_network().get_node_name_from_message_name(
			payload['message'])
	return node_name if not wrap else get_network().get_node_wrap(node_name)


@exception_handler
def handle_SendMessageRequest(payload, logger):
	node_name = get_node(payload)
	logger.debug(f'Sending a {payload["message"]} message to {node_name}')
	get_network().send_message(payload["message"], node_name)
	return success_reply()

@exception_handler
def handle_StartPeriodicMessageRequest(payload, logger):
	node_name = get_node(payload)
	get_network().start_periodic(payload["message"], node_name, payload['interval'])
	return success_reply()

@exception_handler
def handle_StopPeriodicMessageRequest(payload, logger):
	node_name = get_node(payload)
	get_network().stop_periodic(payload["message"], node_name)
	return success_reply()

@exception_handler
def handle_MessageCountRequest(payload, logger):
	node_name = get_node(payload)
	message_wrap = get_network().get_message_wrap(payload['message'], node_name)
	return reply('MessageCountReply', count=message_wrap.counter)

@exception_handler
def handle_LastReceivedTimeRequest(payload, logger):
	node_name = get_node(payload)
	last_time = get_network().get_message_wrap(payload['message'], node_name).last_time
	if last_time < 0:
		return error_reply('NeverReceivedMessage',
			f'It seems that {payload["message"]} has never been received')
	return reply('LastReceivedTimeReply', time=last_time)

@exception_handler
def handle_FetchLastReceivedRequest(payload, logger):
	node_name = get_node(payload)
	message_wrap = get_network().get_message_wrap(payload['message'], node_name)
	if (_last := message_wrap.last(payload['number'])) is None:
		return error_reply('ErrorFetchLastReceived', f'No message {payload["message"]} received')
	elif len(_last) < payload['number']:
		return error_reply('ErrorFetchLastReceived', f'Requested too many {payload["message"]} messages')
	return reply('FetchLastReceivedReply', messages=_last)

@exception_handler
def handle_UpdateDataRequest(payload, logger):
	for path_list, value in payload['data'].items():
		result = get_network().update_data(
			path_list=path_list,
			value=value,
			node_name=payload['node'],
			glitch=payload['glitch']
		)
		if isinstance(result, error.ErrorType):
			return error_reply(result.value,
							   f'Error caught updating {path_list}')
	return success_reply()

@exception_handler
def handle_GetDataRequest(payload, logger):
	result = dict()
	for path_list in payload['data']:
		result[path_list] = get_network().get_data(
			path_list=path_list,
			node_name=payload['node'],
			glitch=payload['glitch'],
			to_dict=True,
			copy=True)
		if isinstance(result[path_list], error.ErrorType):
			return error_reply(result[path_list].value,
				f'Error caught getting {path_list}')
	return reply('GetDataReply', data=result)

@exception_handler
def handle_ResetDataRequest(payload, logger):
	result = get_network().reset_data(
		node_name=payload['node'],
		messages=payload['messages']
	)
	if isinstance(result, error.ErrorType):
		return error_reply(result.value,
						   f'Error caught during data reset')
	return success_reply()

@exception_handler
def handle_ConnectionRequest(payload, logger):
	connected = False
	for _ in range(60):
		connected = get_network().get_connection_result()
		if connected or not payload['wait']:
			break
		time.sleep(1)
	return reply('ConnectionReply', connected=connected)

@exception_handler
def handle_RequirementStateRequest(payload, logger):
	state = requirements.get_state(payload['requirement'])
	if state is None:
		return error_reply('Requirement not Found',
		f'{payload["requirement"]} not in requirements list.')
	return reply('RequirementStateReply', state=state.name)

@exception_handler
def handle_CloseNetworkRequest(payload, logger):
	get_network().stop()
	return success_reply()

@exception_handler
def handle_UpdateSMPropertyRequest(payload, logger):
	get_sm_manager().set_property(payload['name'], payload['property'], payload['value'])
	return success_reply()

@exception_handler
def handle_UpdateGlobalVariable(payload, logger):
	result = get_global_manager().update_global_variable(payload['name'], payload['value'])
	return success_reply() if result else error_reply('UpdateGlobalVariableError', f'{payload["name"]} does not exist')


def connect_handlers(node_name):
	signal_instance.connect((node_name, 'SendMessageRequest'), handle_SendMessageRequest)
	signal_instance.connect((node_name, 'StartPeriodicMessageRequest'), handle_StartPeriodicMessageRequest)
	signal_instance.connect((node_name, 'StopPeriodicMessageRequest'), handle_StopPeriodicMessageRequest)
	signal_instance.connect((node_name, 'MessageCountRequest'), handle_MessageCountRequest)
	signal_instance.connect((node_name, 'FetchLastReceivedRequest'), handle_FetchLastReceivedRequest)
	signal_instance.connect((node_name, 'UpdateDataRequest'), handle_UpdateDataRequest)
	signal_instance.connect((node_name, 'GetDataRequest'), handle_GetDataRequest)
	signal_instance.connect((node_name, 'ResetDataRequest'), handle_ResetDataRequest)
	signal_instance.connect((node_name, 'ConnectionRequest'), handle_ConnectionRequest)
	signal_instance.connect((node_name, 'RequirementStateRequest'), handle_RequirementStateRequest)
	signal_instance.connect((node_name, 'LastReceivedTimeRequest'), handle_LastReceivedTimeRequest)
	signal_instance.connect((node_name, 'CloseNetworkRequest'), handle_CloseNetworkRequest)
	signal_instance.connect((node_name, 'UpdateSMPropertyRequest'), handle_UpdateSMPropertyRequest)
	signal_instance.connect((node_name, 'UpdateGlobalVariable'), handle_UpdateGlobalVariable)
