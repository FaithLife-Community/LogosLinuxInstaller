import os
import time
from enum import Enum
import logging
import psutil
import threading

import config
import main
import msg
import system
import utils
import wine


class State(Enum):
    RUNNING = 1
    STOPPED = 2
    STARTING = 3
    STOPPING = 4


class LogosManager:
    def __init__(self, app=None):
        self.logos_state = State.STOPPED
        self.indexing_state = State.STOPPED
        self.app = app
        if config.wine_user is None:
            wine.get_wine_user()
        if config.logos_indexer_cmd is None or config.login_window_cmd is None or config.logos_cef_cmd is None:
            config.login_window_cmd = f'C:\\users\\{config.wine_user}\\AppData\\Local\\Logos\\System\\Logos.exe'  # noqa: E501
            config.logos_cef_cmd = f'C:\\users\\{config.wine_user}\\AppData\\Local\\Logos\\System\\LogosCEF.exe'  # noqa: E501
            config.logos_indexer_cmd = f'C:\\users\\{config.wine_user}\\AppData\\Local\\Logos\\System\\LogosIndexer.exe'  # noqa: E501
        for root, dirs, files in os.walk(os.path.join(config.WINEPREFIX, "drive_c")):  # noqa: E501
            for f in files:
                if f == "LogosIndexer.exe" and root.endswith("Logos/System"):
                    config.logos_indexer_exe = os.path.join(root, f)
                    break

    def monitor_indexing(self):
        if config.logos_indexer_cmd in config.processes:
            indexer = config.processes[config.logos_indexer_cmd]
            if indexer and isinstance(indexer[0], psutil.Process) and indexer[0].is_running():
                self.indexing_state = State.RUNNING
            else:
                self.indexing_state = State.STOPPED

    def monitor_logos(self):
        splash = config.processes.get(config.LOGOS_EXE, [])
        login_window = config.processes.get(config.login_window_cmd, [])
        logos_cef = config.processes.get(config.logos_cef_cmd, [])

        splash_running = splash[0].is_running() if splash else False
        login_running = login_window[0].is_running() if login_window else False
        logos_cef_running = logos_cef[0].is_running() if logos_cef else False

        if self.logos_state == State.RUNNING:
            if not (splash_running or login_running or logos_cef_running):
                self.stop()
        elif self.logos_state == State.STOPPED:
            if splash and isinstance(splash[0], psutil.Process) and splash_running:
                self.logos_state = State.STARTING
            if (login_window and isinstance(login_window[0], psutil.Process) and login_running) or (
                    logos_cef and isinstance(logos_cef[0], psutil.Process) and logos_cef_running):
                self.logos_state = State.RUNNING

    def monitor(self):
        if utils.file_exists(config.LOGOS_EXE):
            if config.wine_user is None:
                wine.get_wine_user()
            system.get_logos_pids()
            try:
                self.monitor_indexing()
                self.monitor_logos()
            except Exception as e:
                pass

    def start(self):
        self.logos_state = State.STARTING
        logos_release = utils.convert_logos_release(config.current_logos_version)  # noqa: E501
        wine_release, _ = wine.get_wine_release(str(utils.get_wine_exe_path()))

        def run_logos():
            wine.run_wine_proc(
                str(utils.get_wine_exe_path()),
                exe=config.LOGOS_EXE
            )

        # TODO: Find a way to incorporate check_wine_version_and_branch()
        if 30 > logos_release[0] > 9 and (
                wine_release[0] < 7 or (wine_release[0] == 7 and wine_release[1] < 18)):  # noqa: E501
            txt = f"Can't run {config.FLPRODUCT} 10+ with Wine below 7.18."
            logging.critical(txt)
            msg.status(txt, self.app)
        if logos_release[0] > 29 and wine_release[0] < 9 and wine_release[1] < 10:
            txt = f"Can't run {config.FLPRODUCT} 30+ with Wine below 9.10."
            logging.critical(txt)
            msg.status(txt, self.app)
        else:
            wine.wineserver_kill()
            app = self.app
            if config.DIALOG == 'tk':
                # Don't send "Running" message to GUI b/c it never clears.
                app = None
            msg.status(f"Running {config.FLPRODUCT}…", app=app)
            utils.start_thread(run_logos, daemon_bool=False)
            self.logos_state = State.RUNNING

    def stop(self):
        self.logos_state = State.STOPPING
        if self.app:
            pids = []
            for process_name in [config.LOGOS_EXE, config.login_window_cmd, config.logos_cef_cmd]:
                process_list = config.processes.get(process_name)
                if process_list:
                    pids.extend([str(process.pid) for process in process_list])
                else:
                    logging.debug(f"No Logos processes found for {process_name}.")

            if pids:
                try:
                    system.run_command(['kill', '-9'] + pids)
                    self.logos_state = State.STOPPED
                    msg.status(f"Stopped Logos processes at PIDs {', '.join(pids)}.", self.app)
                except Exception as e:
                    logging.debug("Error while stopping Logos processes: {e}.")
            else:
                logging.debug("No Logos processes to stop.")
                self.logos_state = State.STOPPED
        wine.wineserver_wait()

    def index(self):
        self.indexing_state = State.STARTING
        index_finished = threading.Event()

        def run_indexing():
            wine.run_wine_proc(
                str(utils.get_wine_exe_path()),
                exe=config.logos_indexer_exe
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
                    msg.status(f"Indexing is running… (Elapsed Time: {formatted_time})", self.app)
                    update_send = 0
            index_finished.set()

        def wait_on_indexing():
            index_finished.wait()
            self.indexing_state = State.STOPPED
            msg.status(f"Indexing has finished.", self.app)
            wine.wineserver_wait()

        wine.wineserver_kill()
        msg.status(f"Indexing has begun…", self.app)
        # index_thread = threading.Thread(target=run_indexing)
        # index_thread.start()
        index_thread = utils.start_thread(run_indexing, daemon=False)
        self.indexing_state = State.RUNNING
        time.sleep(1)  # If we don't wait, the thread starts too quickly
        # and the process won't yet be launched when we try to pull it from config.processes
        process = config.processes[config.logos_indexer_exe]
        # check_thread = threading.Thread(target=check_if_indexing, args=(process,))
        check_thread = utils.start_thread(check_if_indexing, process)
        # wait_thread = threading.Thread(target=wait_on_indexing)
        wait_thread = utils.start_thread(wait_on_indexing)
        # check_thread.start()
        # wait_thread.start()
        main.threads.extend([index_thread, check_thread, wait_thread])
        config.processes[config.logos_indexer_exe] = index_thread
        config.processes[config.check_if_indexing] = check_thread
        config.processes[wait_on_indexing] = wait_thread

    def stop_indexing(self):
        self.indexing_state = State.STOPPING
        if self.app:
            pids = []
            for process_name in [config.logos_indexer_exe]:
                process_list = config.processes.get(process_name)
                if process_list:
                    pids.extend([str(process.pid) for process in process_list])
                else:
                    logging.debug(f"No LogosIndexer processes found for {process_name}.")

            if pids:
                try:
                    system.run_command(['kill', '-9'] + pids)
                    self.indexing_state = State.STOPPED
                    msg.status(f"Stopped LogosIndexer processes at PIDs {', '.join(pids)}.", self.app)
                except Exception as e:
                    logging.debug("Error while stopping LogosIndexer processes: {e}.")
            else:
                logging.debug("No LogosIndexer processes to stop.")
                self.indexing_state = State.STOPPED
        wine.wineserver_wait()

    def get_app_logging_state(self, init=False):
        state = 'DISABLED'
        current_value = wine.get_registry_value(
            'HKCU\\Software\\Logos4\\Logging',
            'Enabled'
        )
        if current_value == '0x1':
            state = 'ENABLED'
        if self.app is not None:
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
            str(utils.get_wine_exe_path()),
            exe='reg',
            exe_args=exe_args
        )
        process.wait()
        wine.wineserver_wait()
        config.LOGS = state
        if self.app is not None:
            self.app.logging_q.put(state)
            self.app.root.event_generate(self.app.logging_event)
