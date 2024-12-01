"""These functions take no arguments by default.
They can be called from CLI, GUI, or TUI.
"""

import glob
import logging
import queue
import os
import shutil
import subprocess
import time
from pathlib import Path

from ou_dedetai.app import App

from . import config
from . import constants
from . import system
from . import utils


def edit_file(config_file: str):
    subprocess.Popen(['xdg-open', config_file])


def backup(app: App):
    backup_and_restore(mode='backup', app=app)


def restore(app: App):
    backup_and_restore(mode='restore', app=app)


# FIXME: almost seems like this is long enough to reuse the install_step count in app
# for a more detailed progress bar
# FIXME: consider moving this into it's own file/module.
def backup_and_restore(mode: str, app: App):
    app.status(f"Starting {mode}...")
    data_dirs = ['Data', 'Documents', 'Users']
    backup_dir = Path(app.conf.backup_dir).expanduser().resolve()

    verb = 'Use' if mode == 'backup' else 'Restore backup from'
    if not app.approve(f"{verb} existing backups folder \"{app.conf.backup_dir}\"?"): #noqa: E501
        # Reset backup dir.
        # The app will re-prompt next time the backup_dir is accessed
        app.conf._raw.backup_dir = None

    # Set source folders.
    backup_dir = Path(app.conf.backup_dir)
    try:
        backup_dir.mkdir(exist_ok=True, parents=True)
    except PermissionError:
        verb = 'access'
        if mode == 'backup':
            verb = 'create'
        app.exit(f"Can't {verb} folder: {backup_dir}")

    if mode == 'restore':
        restore_dir = utils.get_latest_folder(app.conf.backup_dir)
        restore_dir = Path(restore_dir).expanduser().resolve()
        # FIXME: Shouldn't this prompt this prompt the list of backups?
        # Rather than forcing the latest
        # Offer to restore the most recent backup.
        if not app.approve(f"Restore most-recent backup?: {restore_dir}", ""):  # noqa: E501
            # Reset and re-prompt
            app.conf._raw.backup_dir = None
            restore_dir = utils.get_latest_folder(app.conf.backup_dir)
            restore_dir = Path(restore_dir).expanduser().resolve()
        source_dir_base = restore_dir
    else:
        if not app.conf.logos_exe:
            app.exit("Cannot backup, Logos is not installed")
        source_dir_base = Path(app.conf.logos_exe).parent
    src_dirs = [source_dir_base / d for d in data_dirs if Path(source_dir_base / d).is_dir()]  # noqa: E501
    logging.debug(f"{src_dirs=}")
    if not src_dirs:
        app.exit(f"No files to {mode}")

    if mode == 'backup':
        app.status("Backing up data…")
    else:
        app.status("Restoring data…")

    # Get source transfer size.
    q = queue.Queue()
    app.status("Calculating backup size…")
    t = utils.start_thread(utils.get_folder_group_size, src_dirs, q)
    try:
        while t.is_alive():
            # FIXME: consider showing a sign of life to the app
            time.sleep(0.5)
        print()
    except KeyboardInterrupt:
        print()
        app.exit("Cancelled with Ctrl+C.")
    t.join()
    src_size = q.get()
    if src_size == 0:
        app.exit(f"Nothing to {mode}!")

    # Set destination folder.
    if mode == 'restore':
        if not app.conf.logos_exe:
            app.exit("Cannot restore, Logos is not installed")
        dst_dir = Path(app.conf.logos_exe).parent
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
            # This shouldn't happen, there is a timestamp in the backup_dir name
            app.exit(f"Backup already exists: {dst_dir}.")

    # Verify disk space.
    if not utils.enough_disk_space(dst_dir, src_size):
        dst_dir.rmdir()
        app.exit(f"Not enough free disk space for {mode}.")

    # Run file transfer.
    if mode == 'restore':
        m = f"Restoring backup from {str(source_dir_base)}…"
    else:
        m = f"Backing up to {str(dst_dir)}…"
    app.status(m)
    app.status("Calculating destination directory size")
    dst_dir_size = utils.get_path_size(dst_dir)
    app.status("Starting backup…")
    t = utils.start_thread(copy_data, src_dirs, dst_dir)
    try:
        counter = 0
        while t.is_alive():
            logging.debug(f"DEV: Still copying… {counter}")
            counter = counter + 1
            time.sleep(1)
        print()
    except KeyboardInterrupt:
        print()
        app.exit("Cancelled with Ctrl+C.")
    t.join()
    app.status(f"Finished {mode}. {src_size} bytes copied to {str(dst_dir)}")


def copy_data(src_dirs, dst_dir):
    for src in src_dirs:
        shutil.copytree(src, Path(dst_dir) / src.name)


def remove_install_dir(app: App):
    folder = Path(app.conf.install_dir)
    question = f"Delete \"{folder}\" and all its contents?"
    if not folder.is_dir():
        logging.info(f"Folder doesn't exist: {folder}")
        return
    if app.approve(question):
        shutil.rmtree(folder)
        logging.warning(f"Deleted folder and all its contents: {folder}")


def remove_all_index_files(app: App):
    if not app.conf.logos_exe:
        app.exit("Cannot remove index files, Logos is not installed")
    logos_dir = os.path.dirname(app.conf.logos_exe)
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

    app.status("Removed all LogosBible index files!", 100)


def remove_library_catalog(app: App):
    if not app.conf.logos_exe:
        app.exit("Cannot remove library catalog, Logos is not installed")
    logos_dir = os.path.dirname(app.conf.logos_exe)
    files_to_remove = glob.glob(f"{logos_dir}/Data/*/LibraryCatalog/*")
    for file_to_remove in files_to_remove:
        try:
            os.remove(file_to_remove)
            logging.info(f"Removed: {file_to_remove}")
        except OSError as e:
            logging.error(f"Error removing {file_to_remove}: {e}")


def set_winetricks(app: App):
    app.status("Preparing winetricks…")
    if app.conf.winetricks_binary != constants.DOWNLOAD:
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
