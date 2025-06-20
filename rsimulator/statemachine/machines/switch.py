from threading import Lock
import time

from rsimulator.statemachine import StateMachine


states = ['on', 'off']

transitions = [
	dict(
		trigger='start',
		source='off',
		dest='on',
	),
	dict(
		trigger='stop',
		source='on',
		dest='off',
	)
]

class SwitchSM(StateMachine):

    def __init__(self):
        super().__init__()
        self.lock = Lock()
        self._first_connection = True
        self._property = 'Switch Property'

        # properties
        self._sending = True

    @property
    def sending(self):
        with self.lock:
            return self._sending

    @sending.setter
    def sending(self, value):
        with self.lock:
            if value != self._sending:
                self.sending_changed(value)
                self._sending = value

    def sending_changed(self, value):
        if value and self.state == 'off':
            self.start()
        elif not value and self.state == 'on':
            self.stop()

    def on_enter_on(self):
        self.logger.info(f'{self._property}: ON')

    def on_enter_off(self):
        self.logger.info(f'{self._property}: OFF')

    def action(self):
        # set in this method the action to perform if property is on
        pass

    def loop(self):
        if self.state == 'on':
            self.action()
