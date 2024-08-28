import logging
import threading
import queue

import config
import installer
import msg
import utils


class CLI:
    def __init__(self):
        self.running = True
        self.choice_q = queue.Queue()
        self.input_q = queue.Queue()
        self.event = threading.Event()

    def stop(self):
        self.running = False

    def run(self):
        config.DIALOG = "cli"

        self.thread = utils.start_thread(installer.ensure_launcher_shortcuts, daemon_bool=True, app=self)

        while self.running:
            self.user_input_processor()

        msg.logos_msg("Exiting CLI installer.")


    def user_input_processor(self):
        prompt = None
        question = None
        options = None
        choice = None
        if self.input_q.qsize() > 0:
            prompt = self.input_q.get()
        if prompt is not None and isinstance(prompt, tuple):
            question = prompt[0]
            options = prompt[1]
        if question is not None and options is not None:
            choice = input(f"{question}: {options}: ")
        if choice is not None and choice.lower() == 'exit':
            self.running = False
        if choice is not None:
            self.choice_q.put(choice)
            self.event.set()


def command_line_interface():
    CLI().run()
