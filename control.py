"""These functions take no arguments by default.
They can be called from CLI, GUI, or TUI.
"""

import glob
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import config
import installer
import msg
import wine


def edit_config():
    subprocess.Popen(['xdg-open', config.CONFIG_FILE])

def delete_log_file_contents():
    # Write empty file.
    with open(config.LOGOS_LOG, 'w') as f:
        f.write('')

def backup():
    pass

def restore():
    pass

def remove_install_dir():
    folder = Path(config.INSTALLDIR)
    if folder.is_dir() and msg.cli_question(f"Delete \"{folder}\" and all its contents?"):
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

    msg.cli_msg("======= Removing all LogosBible index files done! =======")
    if app is not None:
        app.root.event_generate(app.message_event)
    sys.exit(0)

def remove_library_catalog():
    LOGOS_DIR = os.path.dirname(config.LOGOS_EXE)
    library_catalog_path = os.path.join(LOGOS_DIR, "Data", "*", "LibraryCatalog")
    pattern = os.path.join(library_catalog_path, "*")
    files_to_remove = glob.glob(pattern)
    for file_to_remove in files_to_remove:
        try:
            os.remove(file_to_remove)
            logging.info(f"Removed: {file_to_remove}")
        except OSError as e:
            logging.error(f"Error removing {file_to_remove}: {e}")

def get_winetricks():
    installer.setWinetricks()
