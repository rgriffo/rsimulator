import logging
import inspect
import traceback


class RLogger(logging.Logger):
	_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
	_global_level = logging.INFO
	_disabled = True
	file_handlers = dict()
	console_handler = None

	def __init__(self, name, log_level=logging.INFO, file_name=None, console=False):
		super().__init__(name)
		self.setLevel(log_level)
		if file_name:
			self.addHandler(RLogger.get_file_handler(file_name))
		if console:
			self.addHandler(RLogger.get_console_handler())

	def only_info(self, msg, *args, **kwargs):
		"""Log only if in INFO"""
		if self.isEnabledFor(logging.DEBUG):
			return
		if self.isEnabledFor(logging.INFO):
			self.info(msg, *args, **kwargs)

	# Uso questa per stampare messaggi di check che devo cancellare
	# così è facile ricercare ed eliminare tutte le occorrenze
	def trial(self, msg, *args, **kwargs):
		self.info(msg, *args, **kwargs)

	def error(self, msg, exc=None):
		if exc:
			tb = exc.__traceback__
			last_frame = traceback.extract_tb(tb)[-1]
			module_name = last_frame.filename
			function_name = last_frame.name
			line_number = last_frame.lineno
			msg = f"[{module_name}.{function_name} - line {line_number}] {msg}: {exc}"

		return super().error(msg)

	def set_log_file(self, file_path):
		self._log_file = file_path

	@classmethod
	def get_file_handler(cls, file_name):
		file_handler = cls.file_handlers.get(file_name)
		if not file_handler:
			cls.file_handlers[file_name] = logging.FileHandler(file_name, mode='w')
			cls.file_handlers[file_name].setFormatter(cls._formatter)
		return cls.file_handlers[file_name]

	@classmethod
	def get_console_handler(cls):
		if not cls.console_handler:
			cls.console_handler = logging.StreamHandler()
			cls.console_handler.setFormatter(cls._formatter)
		return cls.console_handler


