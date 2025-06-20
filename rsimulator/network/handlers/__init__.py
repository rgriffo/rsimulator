import functools
import inspect
from ...utils.rsignal import signal_instance

def message_handler(node, message):
    def decorator(func):
        func.node_message = (node, message)
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

def on_connection(node):
    def decorator(func):
        func.connected_node = node
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def register_handlers_module(module):
    message_handler_functions = [func for name, func in inspect.getmembers(module, inspect.isfunction) if hasattr(func, "node_message")]
    on_connection_functions = [func for name, func in inspect.getmembers(module, inspect.isfunction) if hasattr(func, "connected_node")]

    for function in message_handler_functions:
        signal_instance.connect(function.node_message, function)
    for function in on_connection_functions:
        signal_instance.connect(f'{function.connected_node}_connected', function)

