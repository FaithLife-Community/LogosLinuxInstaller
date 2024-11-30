import time
from enum import Enum
import logging
import psutil
import threading

from ou_dedetai.app import App

from . import config
from . import main
from . import msg
from . import system
from . import utils
from . import wine


class State(Enum):
    RUNNING = 1
    STOPPED = 2
    STARTING = 3
    STOPPING = 4


class LogosManager:
    def __init__(self, app: App):
        self.logos_state = State.STOPPED
        self.indexing_state = State.STOPPED
        self.app = app

    def monitor_indexing(self):
        if self.app.conf.logos_indexer_exe in config.processes:
            indexer = config.processes.get(self.app.conf.logos_indexer_exe)
            if indexer and isinstance(indexer[0], psutil.Process) and indexer[0].is_running():  # noqa: E501
                self.indexing_state = State.RUNNING
            else:
                self.indexing_state = State.STOPPED

    def monitor_logos(self):
        splash = config.processes.get(self.app.conf.logos_exe, [])
        login = config.processes.get(self.app.conf.logos_login_exe, [])
        cef = config.processes.get(self.app.conf.logos_cef_exe, [])

        splash_running = splash[0].is_running() if splash else False
        login_running = login[0].is_running() if login else False
        cef_running = cef[0].is_running() if cef else False
        # logging.debug(f"{self.logos_state=}")
        # logging.debug(f"{splash_running=}; {login_running=}; {cef_running=}")

        if self.logos_state == State.STARTING:
            if login_running or cef_running:
                self.logos_state = State.RUNNING
        elif self.logos_state == State.RUNNING:
            if not any((splash_running, login_running, cef_running)):
                self.stop()
        elif self.logos_state == State.STOPPING:
            pass
        elif self.logos_state == State.STOPPED:
            if splash_running:
                self.logos_state = State.STARTING
            if login_running:
                self.logos_state = State.RUNNING
            if cef_running:
                self.logos_state = State.RUNNING

    def monitor(self):
        if self.app.is_installed():
            system.get_logos_pids(self.app)
            try:
                self.monitor_indexing()
                self.monitor_logos()
            except Exception as e:
                # pass
                logging.error(e)

    def start(self):
        self.logos_state = State.STARTING
        wine_release, _ = wine.get_wine_release(self.app.conf.wine_binary)

        def run_logos():
            wine.run_wine_proc(
                self.app.conf.wine_binary,
                self.app,
                exe=self.app.conf.logos_exe
            )

        # Ensure wine version is compatible with Logos release version.
        good_wine, reason = wine.check_wine_rules(
            wine_release,
            self.app.conf.installed_faithlife_product_release,
            self.app.conf.faithlife_product_version
        )
        if not good_wine:
            msg.logos_error(reason, app=self)
        else:
            wine.wineserver_kill(self.app.conf.wineserver_binary)
            app = self.app
            if config.DIALOG == 'tk':
                # Don't send "Running" message to GUI b/c it never clears.
                app = None
            msg.status(f"Running {app.conf.faithlife_product}…", app=app)
            utils.start_thread(run_logos, daemon_bool=False)
            # NOTE: The following code would keep the CLI open while running
            # Logos, but since wine logging is sent directly to wine.log,
            # there's no terminal output to see. A user can see that output by:
            # tail -f ~/.local/state/FaithLife-Community/wine.log
            # if config.DIALOG == 'cli':
            #     run_logos()
            #     self.monitor()
            #     while config.processes.get(app.conf.logos_exe) is None:
            #         time.sleep(0.1)
            #     while self.logos_state != State.STOPPED:
            #         time.sleep(0.1)
            #         self.monitor()
            # else:
            #     utils.start_thread(run_logos, daemon_bool=False)

    def stop(self):
        logging.debug("Stopping LogosManager.")
        self.logos_state = State.STOPPING
        if self.app:
            pids = []
            for process_name in [
                self.app.conf.logos_exe,
                self.app.conf.logos_login_exe,
                self.app.conf.logos_cef_exe
            ]:
                process_list = config.processes.get(process_name)
                if process_list:
                    pids.extend([str(process.pid) for process in process_list])
                else:
                    logging.debug(f"No Logos processes found for {process_name}.")  # noqa: E501

            if pids:
                try:
                    system.run_command(['kill', '-9'] + pids)
                    self.logos_state = State.STOPPED
                    msg.status(f"Stopped Logos processes at PIDs {', '.join(pids)}.", self.app)  # noqa: E501
                except Exception as e:
                    logging.debug(f"Error while stopping Logos processes: {e}.")  # noqa: E501
            else:
                logging.debug("No Logos processes to stop.")
                self.logos_state = State.STOPPED
        wine.wineserver_wait(self.app)

    def index(self):
        self.indexing_state = State.STARTING
        index_finished = threading.Event()

        def run_indexing():
            wine.run_wine_proc(
                self.app.conf.wine_binary,
                exe=self.app.conf.logos_indexer_exe
            )

        def check_if_indexing(process):
            start_time = time.time()
            last_time = start_time
            update_send = 0
            while process.poll() is None:
                update, last_time = utils.stopwatch(last_time, 3)
                if update:
                    update_send = update_send + 1
                if update_send == 10:
                    total_elapsed_time = time.time() - start_time
                    elapsed_min = int(total_elapsed_time // 60)
                    elapsed_sec = int(total_elapsed_time % 60)
                    formatted_time = f"{elapsed_min}m {elapsed_sec}s"
                    msg.status(f"Indexing is running… (Elapsed Time: {formatted_time})", self.app)  # noqa: E501
                    update_send = 0
            index_finished.set()

        def wait_on_indexing():
            index_finished.wait()
            self.indexing_state = State.STOPPED
            msg.status("Indexing has finished.", self.app)
            wine.wineserver_wait(app=self.app)

        wine.wineserver_kill(self.app.conf.wineserver_binary)
        msg.status("Indexing has begun…", self.app)
        index_thread = utils.start_thread(run_indexing, daemon_bool=False)
        self.indexing_state = State.RUNNING
        # If we don't wait the process won't yet be launched when we try to
        # pull it from config.processes.
        while config.processes.get(self.app.conf.logos_indexer_exe) is None:
            time.sleep(0.1)
        logging.debug(f"{config.processes=}")
        process = config.processes[self.app.conf.logos_indexer_exe]
        check_thread = utils.start_thread(
            check_if_indexing,
            process,
            daemon_bool=False
        )
        wait_thread = utils.start_thread(wait_on_indexing, daemon_bool=False)
        main.threads.extend([index_thread, check_thread, wait_thread])
        config.processes[self.app.conf.logos_indexer_exe] = index_thread
        config.processes["check_if_indexing"] = check_thread
        config.processes["wait_on_indexing"] = wait_thread

    def stop_indexing(self):
        self.indexing_state = State.STOPPING
        if self.app:
            pids = []
            for process_name in [self.app.conf.logos_indexer_exe]:
                process_list = config.processes.get(process_name)
                if process_list:
                    pids.extend([str(process.pid) for process in process_list])
                else:
                    logging.debug(f"No LogosIndexer processes found for {process_name}.")  # noqa: E501

            if pids:
                try:
                    system.run_command(['kill', '-9'] + pids)
                    self.indexing_state = State.STOPPED
                    msg.status(f"Stopped LogosIndexer processes at PIDs {', '.join(pids)}.", self.app)  # noqa: E501
                except Exception as e:
                    logging.debug(f"Error while stopping LogosIndexer processes: {e}.")  # noqa: E501
            else:
                logging.debug("No LogosIndexer processes to stop.")
                self.indexing_state = State.STOPPED
        wine.wineserver_wait(app=self.app)

    def get_app_logging_state(self, init=False):
        state = 'DISABLED'
        current_value = wine.get_registry_value(
            'HKCU\\Software\\Logos4\\Logging',
            'Enabled',
            self.app
        )
        if current_value == '0x1':
            state = 'ENABLED'
        if config.DIALOG in ['curses', 'dialog', 'tk']:
            self.app.logging_q.put(state)
            if init:
                self.app.root.event_generate('<<InitLoggingButton>>')
            else:
                self.app.root.event_generate('<<UpdateLoggingButton>>')
        return state

    def switch_logging(self, action=None):
        state_disabled = 'DISABLED'
        value_disabled = '0000'
        state_enabled = 'ENABLED'
        value_enabled = '0001'
        if action == 'disable':
            value = value_disabled
            state = state_disabled
        elif action == 'enable':
            value = value_enabled
            state = state_enabled
        else:
            current_state = self.get_app_logging_state()
            logging.debug(f"app logging {current_state=}")
            if current_state == state_enabled:
                value = value_disabled
                state = state_disabled
            else:
                value = value_enabled
                state = state_enabled

        logging.info(f"Setting app logging to '{state}'.")
        exe_args = [
            'add', 'HKCU\\Software\\Logos4\\Logging', '/v', 'Enabled',
            '/t', 'REG_DWORD', '/d', value, '/f'
        ]
        process = wine.run_wine_proc(
            self.app.conf.wine_binary,
            exe='reg',
            exe_args=exe_args
        )
        wine.wait_pid(process)
        wine.wineserver_wait(app=self.app)
        self.app.conf.faithlife_product_logging = state
        if config.DIALOG in ['curses', 'dialog', 'tk']:
            self.app.logging_q.put(state)
            self.app.root.event_generate(self.app.logging_event)
