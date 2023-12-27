import glob
import logging
import os
import subprocess
import sys

import config
from msg import cli_msg


def open_config_file():
    subprocess.Popen(['xdg-open', config.CONFIG_FILE])

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

    cli_msg("======= Removing all LogosBible index files done! =======")
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
