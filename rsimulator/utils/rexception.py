import sys
import traceback
DEBUG = True

def conditional(decorator):
    def decorator_wrapper(func):
        if DEBUG:
            return decorator(func)
        else:
            return func
    return decorator_wrapper

def name_and_traceback(func):
    def wrapper(*args, **kwargs):
        try:
            print(f"Call to Function: {func.__name__}")
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Error in function '{func.__name__}: {e}'")
            traceback.print_exc()
            raise
    return wrapper

def conditional_debugging(cls):
    for attr_name, attr_value in cls.__dict__.items():
        if callable(attr_value) and not attr_name.startswith('__'):
            setattr(cls, attr_name, conditional(name_and_traceback)(attr_value))
    return cls

def conditional_debugging(cls):
    for attr_name, attr_value in cls.__dict__.items():
        if callable(attr_value) and not attr_name.startswith('__'):
            setattr(cls, attr_name, conditional(name_and_traceback)(attr_value))
    return cls

def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    traceback.print_exception(exc_type, exc_value, exc_traceback)

    last_trace = traceback.extract_tb(exc_traceback)[-1]
    file_name = last_trace.filename
    line_number = last_trace.lineno
    function_name = last_trace.name

    print(f"Errore nella funzione '{function_name}' (file '{file_name}', riga {line_number})")

def setup_global_exception_handler():
    sys.excepthook = global_exception_handler
