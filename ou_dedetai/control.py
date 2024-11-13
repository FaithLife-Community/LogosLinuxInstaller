"""These functions take no arguments by default.
They can be called from CLI, GUI, or TUI.
"""

import glob
import logging
import queue
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ou_dedetai.app import App

from . import config
from . import constants
from . import msg
from . import network
from . import system
from . import tui_curses
from . import utils


def edit_config():
    subprocess.Popen(['xdg-open', config.CONFIG_FILE])


def delete_log_file_contents():
    # Write empty file.
    with open(config.LOGOS_LOG, 'w') as f:
        f.write('')


def backup(app: App):
    backup_and_restore(mode='backup', app=app)


def restore(app: App):
    backup_and_restore(mode='restore', app=app)


# FIXME: consider moving this into it's own file/module.
def backup_and_restore(mode: str, app: App):
    data_dirs = ['Data', 'Documents', 'Users']
    # Ensure BACKUPDIR is defined.
    if config.BACKUPDIR is None:
        if config.DIALOG == 'tk':
            pass  # config.BACKUPDIR is already set in GUI
        elif config.DIALOG == 'curses':
            app.todo_e.wait()  # Wait for TUI to resolve config.BACKUPDIR
            app.todo_e.clear()
        else:
            try:
                config.BACKUPDIR = input("New or existing folder to store backups in: ")  # noqa: E501
            except KeyboardInterrupt:
                print()
                msg.logos_error("Cancelled with Ctrl+C")
    config.BACKUPDIR = Path(config.BACKUPDIR).expanduser().resolve()
    utils.update_config_file(
        config.CONFIG_FILE,
        'BACKUPDIR',
        str(config.BACKUPDIR)
    )

    # Confirm BACKUPDIR.
    if config.DIALOG == 'tk' or config.DIALOG == 'curses':
        pass  # user confirms in GUI or TUI
    else:
        verb = 'Use' if mode == 'backup' else 'Restore backup from'
        if not msg.cli_question(f"{verb} existing backups folder \"{config.BACKUPDIR}\"?", ""):  # noqa: E501
            answer = None
            while answer is None or (mode == 'restore' and not answer.is_dir()):  # noqa: E501
                answer = msg.cli_ask_filepath("Please provide a backups folder path:")
                answer = Path(answer).expanduser().resolve()
                if not answer.is_dir():
                    msg.status(f"Not a valid folder path: {answer}", app=app)
            config.BACKUPDIR = answer

    # Set source folders.
    backup_dir = Path(config.BACKUPDIR)
    try:
        backup_dir.mkdir(exist_ok=True, parents=True)
    except PermissionError:
        verb = 'access'
        if mode == 'backup':
            verb = 'create'
        msg.logos_warning(f"Can't {verb} folder: {backup_dir}")
        return

    if mode == 'restore':
        config.RESTOREDIR = utils.get_latest_folder(config.BACKUPDIR)
        config.RESTOREDIR = Path(config.RESTOREDIR).expanduser().resolve()
        if config.DIALOG == 'tk':
            pass
        elif config.DIALOG == 'curses':
            app.screen_q.put(app.stack_confirm(24, app.todo_q, app.todo_e,
                                               f"Restore most-recent backup?: {config.RESTOREDIR}", "", "",
                                               dialog=config.use_python_dialog))
            app.todo_e.wait()  # Wait for TUI to confirm RESTOREDIR
            app.todo_e.clear()
            if app.tmp == "No":
                question = "Please choose a different restore folder path:"
                app.screen_q.put(app.stack_input(25, app.todo_q, app.todo_e, question, f"{config.RESTOREDIR}",
                                                 dialog=config.use_python_dialog))
                app.todo_e.wait()
                app.todo_e.clear()
                config.RESTOREDIR = Path(app.tmp).expanduser().resolve()
        else:
            # Offer to restore the most recent backup.
            if not msg.cli_question(f"Restore most-recent backup?: {config.RESTOREDIR}", ""):  # noqa: E501
                config.RESTOREDIR = msg.cli_ask_filepath("Path to backup set that you want to restore:")  # noqa: E501
        source_dir_base = config.RESTOREDIR
    else:
        source_dir_base = Path(config.LOGOS_EXE).parent
    src_dirs = [source_dir_base / d for d in data_dirs if Path(source_dir_base / d).is_dir()]  # noqa: E501
    logging.debug(f"{src_dirs=}")
    if not src_dirs:
        msg.logos_warning(f"No files to {mode}", app=app)
        return

    if config.DIALOG == 'curses':
        if mode == 'backup':
            app.screen_q.put(app.stack_text(8, app.todo_q, app.todo_e, "Backing up data…", wait=True))
        else:
            app.screen_q.put(app.stack_text(8, app.todo_q, app.todo_e, "Restoring data…", wait=True))

    # Get source transfer size.
    q = queue.Queue()
    msg.status("Calculating backup size…", app=app)
    t = utils.start_thread(utils.get_folder_group_size, src_dirs, q)
    try:
        while t.is_alive():
            msg.logos_progress()
            time.sleep(0.5)
        print()
    except KeyboardInterrupt:
        print()
        msg.logos_error("Cancelled with Ctrl+C.", app=app)
    t.join()
    if config.DIALOG == 'tk':
        app.root.event_generate('<<StopIndeterminateProgress>>')
        app.root.event_generate('<<ClearStatus>>')
    src_size = q.get()
    if src_size == 0:
        msg.logos_warning(f"Nothing to {mode}!", app=app)
        return

    # Set destination folder.
    if mode == 'restore':
        dst_dir = Path(config.LOGOS_EXE).parent
        # Remove existing data.
        for d in data_dirs:
            dst = Path(dst_dir) / d
            if dst.is_dir():
                shutil.rmtree(dst)
    else:  # backup mode
        timestamp = utils.get_timestamp().replace('-', '')
        current_backup_name = f"{config.FLPRODUCT}{config.TARGETVERSION}-{timestamp}"  # noqa: E501
        dst_dir = backup_dir / current_backup_name
        logging.debug(f"Backup directory path: \"{dst_dir}\".")

        # Check for existing backup.
        try:
            dst_dir.mkdir()
        except FileExistsError:
            msg.logos_error(f"Backup already exists: {dst_dir}.")

    # Verify disk space.
    if not utils.enough_disk_space(dst_dir, src_size):
        dst_dir.rmdir()
        msg.logos_warning(f"Not enough free disk space for {mode}.", app=app)
        return

    # Run file transfer.
    if mode == 'restore':
        m = f"Restoring backup from {str(source_dir_base)}…"
    else:
        m = f"Backing up to {str(dst_dir)}…"
    msg.status(m, app=app)
    msg.status("Calculating destination directory size", app=app)
    dst_dir_size = utils.get_path_size(dst_dir)
    msg.status("Starting backup…", app=app)
    t = utils.start_thread(copy_data, src_dirs, dst_dir)
    try:
        counter = 0
        while t.is_alive():
            logging.debug(f"DEV: Still copying… {counter}")
            counter = counter + 1
            # progress = utils.get_copy_progress(
            #     dst_dir,
            #     src_size,
            #     dest_size_init=dst_dir_size
            # )
            # utils.write_progress_bar(progress)
            # if config.DIALOG == 'tk':
            #     app.progress_q.put(progress)
            #     app.root.event_generate('<<UpdateProgress>>')
            time.sleep(1)
        print()
    except KeyboardInterrupt:
        print()
        msg.logos_error("Cancelled with Ctrl+C.")
    t.join()
    if config.DIALOG == 'tk':
        app.root.event_generate('<<ClearStatus>>')
    logging.info(f"Finished. {src_size} bytes copied to {str(dst_dir)}")


def copy_data(src_dirs, dst_dir):
    for src in src_dirs:
        shutil.copytree(src, Path(dst_dir) / src.name)


def remove_install_dir():
    folder = Path(config.INSTALLDIR)
    if (
        folder.is_dir()
        and msg.cli_question(f"Delete \"{folder}\" and all its contents?")
    ):
        shutil.rmtree(folder)
        logging.warning(f"Deleted folder and all its contents: {folder}")
    else:
        logging.info(f"Folder doesn't exist: {folder}")


def remove_all_index_files(app=None):
    logos_dir = os.path.dirname(config.LOGOS_EXE)
    index_paths = [
        os.path.join(logos_dir, "Data", "*", "BibleIndex"),
        os.path.join(logos_dir, "Data", "*", "LibraryIndex"),
        os.path.join(logos_dir, "Data", "*", "PersonalBookIndex"),
        os.path.join(logos_dir, "Data", "*", "LibraryCatalog")
    ]
    for index_path in index_paths:
        pattern = os.path.join(index_path, "*")
        files_to_remove = glob.glob(pattern)

        for file_to_remove in files_to_remove:
            try:
                os.remove(file_to_remove)
                logging.info(f"Removed: {file_to_remove}")
            except OSError as e:
                logging.error(f"Error removing {file_to_remove}: {e}")

    msg.status("======= Removing all LogosBible index files done! =======")
    if hasattr(app, 'status_evt'):
        app.root.event_generate(app.status_evt)
    sys.exit(0)


def remove_library_catalog():
    logos_dir = os.path.dirname(config.LOGOS_EXE)
    files_to_remove = glob.glob(f"{logos_dir}/Data/*/LibraryCatalog/*")
    for file_to_remove in files_to_remove:
        try:
            os.remove(file_to_remove)
            logging.info(f"Removed: {file_to_remove}")
        except OSError as e:
            logging.error(f"Error removing {file_to_remove}: {e}")


def set_winetricks():
    msg.status("Preparing winetricks…")
    if not config.APPDIR_BINDIR:
        config.APPDIR_BINDIR = f"{config.INSTALLDIR}/data/bin"
    # Check if local winetricks version available; else, download it
    if config.WINETRICKSBIN is None or not os.access(config.WINETRICKSBIN, os.X_OK):  # noqa: E501
        local_winetricks_path = shutil.which('winetricks')
        if local_winetricks_path is not None:
            # Check if local winetricks version is up-to-date; if so, offer to
            # use it or to download; else, download it.
            local_winetricks_version = subprocess.check_output(["winetricks", "--version"]).split()[0]  # noqa: E501
            if str(local_winetricks_version) != constants.WINETRICKS_VERSION: # noqa: E501
                if config.DIALOG == 'tk': #FIXME: CLI client not considered
                    logging.info("Setting winetricks to the local binary…")
                    config.WINETRICKSBIN = local_winetricks_path
                else:
                    title = "Choose Winetricks"
                    question_text = "Should the script use the system's local winetricks or download the latest winetricks from the Internet? The script needs to set some Wine options that FLPRODUCT requires on Linux."  # noqa: E501

                    options = [
                        "1: Use local winetricks.",
                        "2: Download winetricks from the Internet"
                    ]
                    winetricks_choice = tui_curses.menu(options, title, question_text)  # noqa: E501

                    logging.debug(f"winetricks_choice: {winetricks_choice}")
                    if winetricks_choice.startswith("1"):
                        logging.info("Setting winetricks to the local binary…")
                        config.WINETRICKSBIN = local_winetricks_path
                        return 0
                    elif winetricks_choice.startswith("2"):
                        system.install_winetricks(config.APPDIR_BINDIR)
                        config.WINETRICKSBIN = os.path.join(
                            config.APPDIR_BINDIR,
                            "winetricks"
                        )
                        return 0
                    else:
                        # FIXME: Should this call a function on the app object?
                        msg.status("Installation canceled!")
                        sys.exit(0)
            else:
                msg.status("The system's winetricks is too old. Downloading an up-to-date winetricks from the Internet…")  # noqa: E501
                system.install_winetricks(config.APPDIR_BINDIR)
                config.WINETRICKSBIN = os.path.join(
                    config.APPDIR_BINDIR,
                    "winetricks"
                )
                return 0
        else:
            msg.status("Local winetricks not found. Downloading winetricks from the Internet…")  # noqa: E501
            system.install_winetricks(config.APPDIR_BINDIR)
            config.WINETRICKSBIN = os.path.join(
                config.APPDIR_BINDIR,
                "winetricks"
            )
            return 0
    return 0

