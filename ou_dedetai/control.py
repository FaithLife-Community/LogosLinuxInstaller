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

from ou_dedetai.app import DOWNLOAD, App

from . import config
from . import constants
from . import msg
from . import network
from . import system
from . import tui_curses
from . import utils


def edit_file(config_file: str):
    subprocess.Popen(['xdg-open', config_file])


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
    backup_dir = Path(app.conf.backup_dir).expanduser().resolve()

    # FIXME: Why is this different per UI? Should this always accept?
    if config.DIALOG == 'tk' or config.DIALOG == 'curses':
        pass  # user confirms in GUI or TUI
    else:
        verb = 'Use' if mode == 'backup' else 'Restore backup from'
        if not msg.cli_question(f"{verb} existing backups folder \"{app.conf.backup_dir}\"?", ""):  # noqa: E501
            answer = None
            while answer is None or (mode == 'restore' and not answer.is_dir()):  # noqa: E501
                answer = msg.cli_ask_filepath("Please provide a backups folder path:")
                answer = Path(answer).expanduser().resolve()
                if not answer.is_dir():
                    msg.status(f"Not a valid folder path: {answer}", app=app)
            config.app.conf.backup_directory = answer

    # Set source folders.
    backup_dir = Path(app.conf.backup_dir)
    try:
        backup_dir.mkdir(exist_ok=True, parents=True)
    except PermissionError:
        verb = 'access'
        if mode == 'backup':
            verb = 'create'
        msg.logos_warning(f"Can't {verb} folder: {backup_dir}")
        return

    if mode == 'restore':
        restore_dir = utils.get_latest_folder(app.conf.backup_dir)
        restore_dir = Path(restore_dir).expanduser().resolve()
        if config.DIALOG == 'tk':
            pass
        elif config.DIALOG == 'curses':
            app.screen_q.put(app.stack_confirm(24, app.todo_q, app.todo_e,
                                               f"Restore most-recent backup?: {restore_dir}", "", "",
                                               dialog=config.use_python_dialog))
            app.todo_e.wait()  # Wait for TUI to confirm restore_dir
            app.todo_e.clear()
            if app.tmp == "No":
                question = "Please choose a different restore folder path:"
                app.screen_q.put(app.stack_input(25, app.todo_q, app.todo_e, question, f"{restore_dir}",
                                                 dialog=config.use_python_dialog))
                app.todo_e.wait()
                app.todo_e.clear()
                restore_dir = Path(app.tmp).expanduser().resolve()
        else:
            # Offer to restore the most recent backup.
            if not msg.cli_question(f"Restore most-recent backup?: {restore_dir}", ""):  # noqa: E501
                restore_dir = msg.cli_ask_filepath("Path to backup set that you want to restore:")  # noqa: E501
        source_dir_base = restore_dir
    else:
        source_dir_base = Path(config.LOGOS_EXE).parent
    src_dirs = [source_dir_base / d for d in data_dirs if Path(source_dir_base / d).is_dir()]  # noqa: E501
    logging.debug(f"{src_dirs=}")
    if not src_dirs:
        msg.logos_warning(f"No files to {mode}", app=app)
        return

    # FIXME: UI specific code
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
        current_backup_name = f"{app.conf.faithlife_product}{app.conf.faithlife_product_version}-{timestamp}"  # noqa: E501
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


def remove_install_dir(app: App):
    folder = Path(app.conf.install_dir)
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


def set_winetricks(app: App):
    msg.status("Preparing winetricks…")
    if app.conf.winetricks_binary != DOWNLOAD:
        valid = True
        # Double check it's a valid winetricks
        if not Path(app.conf.winetricks_binary).exists():
            logging.warning("Winetricks path does not exist, downloading instead...")
            valid = False
        if not os.access(app.conf.winetricks_binary, os.X_OK):
            logging.warning("Winetricks path given is not executable, downloading instead...")
            valid = False
        if not utils.check_winetricks_version(app.conf.winetricks_binary):
            logging.warning("Winetricks version mismatch, downloading instead...")
            valid = False
        if valid:
            logging.info(f"Found valid winetricks: {app.conf.winetricks_binary}")
            return 0
        # Continue executing the download if it wasn't valid

    system.install_winetricks(app.conf.installer_binary_dir, app)
    app.conf.wine_binary = os.path.join(
        app.conf.installer_binary_dir,
        "winetricks"
    )
    return 0
