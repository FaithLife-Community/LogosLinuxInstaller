#!/usr/bin/env python3
import glob
import logging
import os
import sys
import datetime
import argparse

import config
from app import InstallerApp
from app import InstallerWindow
from logos_setup import install
from msg import cli_msg
from msg import gtk_info
from msg import initialize_logging
from msg import gtk_info
from msg import logos_error
from utils import checkDependencies
from utils import curses_menu
from utils import die_if_root
from utils import die_if_running
from utils import file_exists
from utils import get_os
from utils import get_package_manager
from utils import getDialog
from utils import set_appimage
from utils import set_default_config
from utils import setDebug
from wine import disable_logging
from wine import enable_logging
from wine import run_control_panel
from wine import run_wine_proc
from wine import run_winetricks

# Basic Functionality
#TODO: Fix post-install
#TODO: Test get_os and get_package_manager
#TODO: Verify necessary packages now that we are using python
#TODO: Redo logos_progress
#TODO: Redo all GUI commands
#TODO: Fix python print lines to use logos_error
#TODO: Test optargs and menu options

# AppImage Handling
#TODO: Convert checkAppImages(). See https://github.com/ferion11/LogosLinuxInstaller/pull/193/commits/bfefb3c05c7a9989e81372d77fa785fc75bd4e94
#TODO: Fix set_appimage()
#TODO: Add update_appimage()

# Script updates and ideas
#TODO: Put main menu into a while loop
#TODO: Add an option to reinstall dependencies for SteamOS
#TODO: Add a get_winetricks option to post-install menu
#TODO: Simplify variables? Import environment?
#TODO: Distribute as single executable through PyInstaller
#TODO: Implement logging via logging module


def parse_command_line():
    parser = argparse.ArgumentParser(description=f'Installs {os.environ.get("FLPRODUCT")} Bible Software with Wine on Linux.')
    parser.add_argument('--version', '-v', action='version', version=f'{config.LOGOS_SCRIPT_TITLE}, {config.LOGOS_SCRIPT_VERSION} by {config.LOGOS_SCRIPT_AUTHOR}')
    parser.add_argument('--config', '-c', metavar='CONFIG_FILE', help='Use the Logos on Linux config file when setting environment variables. Defaults to ~/.config/Logos_on_Linux/Logos_on_Linux.conf. Optionally can accept a config file provided by the user.')
    parser.add_argument('--verbose', '-V', action='store_true', help='Enable verbose mode')
    parser.add_argument('--skip-fonts', '-F', action='store_true', help='Skip font installations')
    parser.add_argument('--force-root', '-f', action='store_true', help='Set LOGOS_FORCE_ROOT to true, which permits the root user to use the script.')
    parser.add_argument('--reinstall-dependencies', '-I', action='store_true', help="Reinstall your distro's dependencies.")
    parser.add_argument('--regenerate-scripts', '-g', action='store_true', help='Regenerate the Logos.sh and controlPanel.sh scripts.')
    parser.add_argument('--make-skel', '-k', action='store_true', help='Make a skeleton install only.')
    parser.add_argument('--custom-binary-path', '-p', metavar='CUSTOMBINPATH', help='Specify a custom wine binary path.')
    parser.add_argument('--check-resources', '-R', action='store_true', help='Check resources and exit')
    parser.add_argument('--edit-config', '-e', action='store_true', help='Edit configuration file')
    parser.add_argument('--indexing', '-i', action='store_true', help='Perform indexing')
    parser.add_argument('--backup', '-b', action='store_true', help='Perform backup')
    parser.add_argument('--restore', '-r', action='store_true', help='Perform restore')
    parser.add_argument('--logs', '-l', action='store_true', help='Enable/disable logs')
    parser.add_argument('--dirlink', '-d', action='store_true', help='Create directory link')
    parser.add_argument('--shortcut', '-s', action='store_true', help='Create shortcut')

    args = parser.parse_args()

    if args.config:
        config.CONFIG_FILE = args.config
        config.get_config_env(config.CONFIG_FILE)

    if args.verbose:
        config.LOG_LEVEL = logging.DEBUG
        config.WINEDEBUG = ''
        config.VERBOSE = True

    if args.skip_fonts:
        config.SKIP_FONTS = True

    if args.force_root:
        config.LOGOS_FORCE_ROOT = True

    if args.reinstall_dependencies:
        config.REINSTALL_DEPENDENCIES = True

    if args.regenerate_scripts:
        config.REGENERATE = True

    if args.debug:
        setDebug()

    if args.make_skel:
        config.SKEL = True

    if args.custom_binary_path:
        if os.path.isdir(args.custom_binary_path):
            config.CUSTOMBINPATH = args.custom_binary_path
        else:
            sys.stderr.write(f"{config.LOGOS_SCRIPT_TITLE}: User supplied path: \"{args.custom_binary_path}\". Custom binary path does not exist.\n")
            parser.print_help()
            sys.exit()

def run_logos():
    run_wine_proc(config.WINE_EXE, exe=config.LOGOS_EXE)
    run_wine_proc(config.WINESERVER_EXE, flags=["-w"])

def run_indexing():
    for root, dirs, files in os.walk(os.path.join(config.WINEPREFIX, "drive_c")):
        for f in files:
            if f == "LogosIndexer.exe" and root.endswith("Logos/System"):
                logos_indexer_exe = os.path.join(root, f)
                break

    run_wine_proc(config.WINESERVER_EXE, flags=["-k"])
    run_wine_proc(config.WINE_EXE, exe=logos_indexer_exe)
    run_wine_proc(config.WINESERVER_EXE, flags=["-w"])

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

def remove_all_index_files():
    LOGOS_DIR = os.path.dirname(config.LOGOS_EXE)
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
    exit(0)

def edit_config():
    pass

def backup():
    pass

def restore():
    pass

def main():
    # Set initial config; incl. defining CONFIG_FILE.
    set_default_config()
    # Update config from CONFIG_FILE.
    # FIXME: This means that values in CONFIG_FILE take precedence over env variables.
    #   Is this preferred, or should env variables take precedence over CONFIG_FILE?
    if file_exists(config.CONFIG_FILE):
        config.get_config_env(config.CONFIG_FILE)

    # Check for environment variables.
    if config.DIALOG is None:
        getDialog()
        
    if config.GUI is not None: # NDM: not sure about this logic
        with open(config.LOGOS_LOG, "a") as f:
            f.write("Running in a GUI. Enabling logging.\n")
        setDebug()

    die_if_running()
    die_if_root()

    parse_command_line()
    if config.VERBOSE:
        print(f"{config.DIALOG=}")

    cli_msg(f"{config.LOGOS_SCRIPT_TITLE}, {config.LOGOS_SCRIPT_VERSION} by {config.LOGOS_SCRIPT_AUTHOR}.")

    # Configure logging.
    initialize_logging(config.LOG_LEVEL)    

    logging.info(f"Using DIALOG: {config.DIALOG}")

    options_default = ["Install Logos Bible Software"]
    options_exit = ["Exit"]
    if file_exists(config.CONFIG_FILE):
        options_installed = [f"Run {config.FLPRODUCT}", "Run Indexing", "Remove Library Catalog", "Remove All Index Files", "Edit Config", "Reinstall Dependencies", "Back up Data", "Restore Data", "Set AppImage", "Control Panel", "Run Winetricks"]
        if os.environ.get("LOGS") == "DISABLED":
            options_installed.extend("Enable Logging")
        else:
            options_installed.extend("Disable Logging")
        options = options_default + options_installed + options_exit
    else:
        options = options_default + options_exit

    if config.DIALOG == 'tk':
        logging.warning("Tk requires tcl8.6 package, which provides tclsh8.6 binary.")
        classname = "LogosLinuxInstaller"
        installer_app = InstallerApp(className=classname)
        InstallerWindow(installer_app, class_=classname)
        installer_app.mainloop()
        return

    elif config.DIALOG in ['whiptail', 'dialog', 'curses']:
        choice = curses_menu(options, "Welcome to Logos on Linux", "What would you like to do?")
    elif config.DIALOG == "zenity":
        gtk_info("Welcome to Logos on Linux", "What would you like to do?")
        logging.info("Welcome to Logos on Linux", "What would you like to do?")
    elif config.DIALOG == "kdialog":
        logos_error("kdialog not implemented.", "")

    if "Exit" in choice:
        sys.exit(0)
    elif "Install" in choice:
        install()
    elif f"Run {config.FLPRODUCT}" in choice:
        run_logos()
    elif "Run Indexing" in choice:
        run_indexing()
    elif "Remove Library Catalog" in choice:
        remove_library_catalog()
    elif "Remove All Index Files" in choice:
        remove_all_index_files()
    elif "Edit Config" in choice:
        edit_config()
    elif "Reinstall Dependencies":
        checkDependencies()
    elif "Back up Data" in choice:
        backup()
    elif "Restore Data" in choice:
        restore()
    elif "Set AppImage" in choice:
        set_appimage()
    elif "Control Panel" in choice:
        run_control_panel()
    elif "Run Winetricks" in choice:
        run_winetricks()
    elif "Logging" in choice:
        if os.environ["LOGS"] == "DISABLED":
            enable_logging()
        else:
            disable_logging()
    else:
        logos_error("Unknown menu choice.", "")
# END FUNCTION DECLARATIONS

if __name__ == '__main__':
    # BEGIN SCRIPT EXECUTION
    main()

    sys.exit(0)
    # END SCRIPT EXECUTION
