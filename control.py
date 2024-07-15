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
import threading
import time
from datetime import datetime
from pathlib import Path

import config
# import installer
import msg
import network
import tui_curses
import tui_app
import utils
# import wine


def edit_config():
    subprocess.Popen(['xdg-open', config.CONFIG_FILE])


def delete_log_file_contents():
    # Write empty file.
    with open(config.LOGOS_LOG, 'w') as f:
        f.write('')


def backup(app=None):
    backup_and_restore(mode='backup', app=app)


def restore(app=None):
    backup_and_restore(mode='restore', app=app)


def backup_and_restore(mode='backup', app=None):
    data_dirs = ['Data', 'Documents', 'Users']
    # Ensure BACKUPDIR is defined.
    if config.BACKUPDIR is None:
        if config.DIALOG == 'tk':
            pass  # config.BACKUPDIR is already set in GUI
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
    if config.DIALOG == 'tk':
        pass  # user confirms in GUI
    else:
        verb = 'Use' if mode == 'backup' else 'Restore backup from'
        if not msg.cli_question(f"{verb} existing backups folder \"{config.BACKUPDIR}\"?"):  # noqa: E501
            answer = None
            while answer is None or (mode == 'restore' and not answer.is_dir()):  # noqa: E501
                answer = msg.cli_ask_filepath("Give backups folder path:")
                answer = Path(answer).expanduser().resolve()
                if not answer.is_dir():
                    msg.logos_msg(f"Not a valid folder path: {answer}")
            config.BACKUPDIR = answer

    # Set source folders.
    if mode == 'restore':
        if config.DIALOG == 'tk':
            pass
        else:
            # Offer to restore the most recent backup.
            config.RESTOREDIR = utils.get_latest_folder(config.BACKUPDIR)
            if not msg.cli_question(f"Restore most-recent backup?: {config.RESTOREDIR}"):  # noqa: E501
                config.RESTOREDIR = msg.cli_ask_filepath("Path to backup set that you want to restore:")  # noqa: E501
        config.RESTOREDIR = Path(config.RESTOREDIR).expanduser().resolve()
        source_dir_base = config.RESTOREDIR
    else:
        source_dir_base = Path(config.LOGOS_EXE).parent
    src_dirs = [source_dir_base / d for d in data_dirs if Path(source_dir_base / d).is_dir()]  # noqa: E501
    logging.debug(f"{src_dirs=}")
    if not src_dirs:
        m = "No files to backup"
        if app is not None:
            app.status_q.put(m)
            app.root.event_generate('<<StartIndeterminateProgress>>')
            app.root.event_generate('<<UpdateStatus>>')
        logging.warning(m)
        return

    # Get source transfer size.
    q = queue.Queue()
    t = threading.Thread(
        target=utils.get_folder_group_size,
        args=[src_dirs, q],
        daemon=True
    )
    m = "Calculating backup size"
    if app is not None:
        app.status_q.put(m)
        app.root.event_generate('<<StartIndeterminateProgress>>')
        app.root.event_generate('<<UpdateStatus>>')
    msg.logos_msg(m, end='')
    t.start()
    try:
        while t.is_alive():
            msg.logos_progress()
            time.sleep(0.5)
        print()
    except KeyboardInterrupt:
        print()
        msg.logos_error("Cancelled with Ctrl+C.")
    t.join()
    if app is not None:
        app.root.event_generate('<<StopIndeterminateProgress>>')
        app.root.event_generate('<<ClearStatus>>')
    src_size = q.get()
    if src_size == 0:
        m = f"Nothing to {mode}!"
        logging.warning(m)
        if app is not None:
            app.status_q.put(m)
            app.root.event_generate('<<UpdateStatus>>')
        return

    # Set destination folder.
    if mode == 'restore':
        dst_dir = Path(config.LOGOS_EXE).parent
        # Remove existing data.
        for d in data_dirs:
            dst = Path(dst_dir) / d
            if dst.is_dir():
                shutil.rmtree(dst)
    else:
        timestamp = datetime.today().strftime('%Y%m%dT%H%M%S')
        current_backup_name = f"{config.FLPRODUCT}{config.TARGETVERSION}-{timestamp}"  # noqa: E501
        dst_dir = Path(config.BACKUPDIR) / current_backup_name
        dst_dir.mkdir(exist_ok=True, parents=True)

    # Verify disk space.
    if (
        not utils.enough_disk_space(dst_dir, src_size)
        and not Path(dst_dir / 'Data').is_dir()
    ):
        m = f"Not enough free disk space for {mode}."
        if app is not None:
            app.status_q.put(m)
            app.root.event_generate('<<UpdateStatus>>')
            return
        else:
            msg.logos_error(m)

    # Verify destination.
    if config.BACKUPDIR is None:
        config.BACKUPDIR = Path().home() / 'Logos_on_Linux_backups'
    backup_dir = Path(config.BACKUPDIR)
    backup_dir.mkdir(exist_ok=True, parents=True)
    if not utils.enough_disk_space(backup_dir, src_size):
        msg.logos_error("Not enough free disk space for backup.")

    # Run backup.
    try:
        dst_dir.mkdir()
    except FileExistsError:
        msg.logos_error(f"Backup already exists: {dst_dir}")

    # Run file transfer.
    t = threading.Thread(
        target=copy_data,
        args=(src_dirs, dst_dir),
        daemon=True
    )
    if mode == 'restore':
        m = f"Restoring backup from {str(source_dir_base)}"
    else:
        m = f"Backing up to {str(dst_dir)}"
    logging.info(m)
    msg.logos_msg(m)
    if app is not None:
        app.status_q.put(m)
        app.root.event_generate('<<UpdateStatus>>')
    dst_dir_size = utils.get_path_size(dst_dir)
    t.start()
    try:
        while t.is_alive():
            progress = utils.get_copy_progress(
                dst_dir,
                src_size,
                dest_size_init=dst_dir_size
            )
            utils.write_progress_bar(progress)
            if app is not None:
                app.progress_q.put(progress)
                app.root.event_generate('<<UpdateProgress>>')
            time.sleep(0.5)
        print()
    except KeyboardInterrupt:
        print()
        msg.logos_error("Cancelled with Ctrl+C.")
    t.join()
    if app is not None:
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

    msg.logos_msg("======= Removing all LogosBible index files done! =======")
    if app is not None:
        app.root.event_generate(app.message_event)
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
    msg.logos_msg("Preparing winetricks…")
    if not config.APPDIR_BINDIR:
        config.APPDIR_BINDIR = f"{config.INSTALLDIR}/data/bin"
    # Check if local winetricks version available; else, download it
    if config.WINETRICKSBIN is None or not os.access(config.WINETRICKSBIN, os.X_OK):  # noqa: E501
        local_winetricks_path = shutil.which('winetricks')
        if local_winetricks_path is not None:
            # Check if local winetricks version is up-to-date; if so, offer to
            # use it or to download; else, download it.
            local_winetricks_version = subprocess.check_output(["winetricks", "--version"]).split()[0]  # noqa: E501
            if str(local_winetricks_version) >= "20220411":
                if config.DIALOG == 'tk':
                    logging.info("Setting winetricks to the local binary…")
                    config.WINETRICKSBIN = local_winetricks_path
                else:
                    title = "Choose Winetricks"
                    question_text = "Should the script use the system's local winetricks or download the latest winetricks from the Internet? The script needs to set some Wine options that FLPRODUCT requires on Linux."  # noqa: E501

                    options = [
                        "1: Use local winetricks.",
                        "2: Download winetricks from the Internet"
                    ]
                    winetricks_choice = tui.menu(options, title, question_text)

                    logging.debug(f"winetricks_choice: {winetricks_choice}")
                    if winetricks_choice.startswith("1"):
                        logging.info("Setting winetricks to the local binary…")
                        config.WINETRICKSBIN = local_winetricks_path
                        return 0
                    elif winetricks_choice.startswith("2"):
                        # download_winetricks()
                        utils.install_winetricks(config.APPDIR_BINDIR)
                        config.WINETRICKSBIN = os.path.join(
                            config.APPDIR_BINDIR,
                            "winetricks"
                        )
                        return 0
                    else:
                        msg.logos_msg("Installation canceled!")
                        sys.exit(0)
            else:
                msg.logos_msg("The system's winetricks is too old. Downloading an up-to-date winetricks from the Internet...")  # noqa: E501
                # download_winetricks()
                utils.install_winetricks(config.APPDIR_BINDIR)
                config.WINETRICKSBIN = os.path.join(
                    config.APPDIR_BINDIR,
                    "winetricks"
                )
                return 0
        else:
            msg.logos_msg("Local winetricks not found. Downloading winetricks from the Internet…")  # noqa: E501
            # download_winetricks()
            utils.install_winetricks(config.APPDIR_BINDIR)
            config.WINETRICKSBIN = os.path.join(
                config.APPDIR_BINDIR,
                "winetricks"
            )
            return 0
    return 0


def download_winetricks():
    msg.logos_msg("Downloading winetricks…")
    appdir_bindir = f"{config.INSTALLDIR}/data/bin"
    network.logos_reuse_download(
        config.WINETRICKS_URL,
        "winetricks",
        appdir_bindir
    )
    os.chmod(f"{appdir_bindir}/winetricks", 0o755)
