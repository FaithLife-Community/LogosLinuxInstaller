# import logging
import queue
import threading

import config
import installer
import logos
# import msg
import utils


class CLI:
    def __init__(self):
        config.DIALOG = "cli"
        self.running = True
        self.choice_q = queue.Queue()
        self.input_q = queue.Queue()
        self.input_event = threading.Event()
        self.choice_event = threading.Event()
        self.logos = logos.LogosManager(app=self)

    def stop(self):
        self.running = False

    def install_app(self):
        self.thread = utils.start_thread(
            installer.ensure_launcher_shortcuts,
            app=self
        )
        self.user_input_processor()

    def run_installed_app(self):
        self.thread = utils.start_thread(self.logos.start, app=self)

    def user_input_processor(self, evt=None):
        while self.running:
            prompt = None
            question = None
            options = None
            choice = None
            # Wait for next input queue item.
            self.input_event.wait()
            self.input_event.clear()
            prompt = self.input_q.get()
            if prompt is None:
                return
            if prompt is not None and isinstance(prompt, tuple):
                question = prompt[0]
                options = prompt[1]
            if question is not None and options is not None:
                # Convert options list to string.
                default = options[0]
                options[0] = f"{options[0]} [default]"
                optstr = ', '.join(options)
                choice = input(f"{question}: {optstr}: ")
                if len(choice) == 0:
                    choice = default
            if choice is not None and choice.lower() == 'exit':
                self.running = False
            if choice is not None:
                self.choice_q.put(choice)
                self.choice_event.set()


def command_line_interface():
    CLI().run()
