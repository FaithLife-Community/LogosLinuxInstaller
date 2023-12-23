#!/usr/bin/env python3
import glob
import logging
import os
import sys
import argparse

import config
from app import InstallerApp
from app import InstallerWindow
from installer import install
from msg import cli_msg
from msg import initialize_logging
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
from wine import run_control_panel
from wine import run_indexing
from wine import run_logos
from wine import run_wine_proc
from wine import run_winetricks
from wine import switch_logging

# Basic Functionality
#TODO: Fix post-install
#TODO: Test get_os and get_package_manager
#TODO: Verify necessary packages now that we are using python
#TODO: Redo logos_progress
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
#TODO: Implement logging via logging module


def parse_command_line():
    parser = argparse.ArgumentParser(description=f'Installs {os.environ.get("FLPRODUCT")} Bible Software with Wine on Linux.')
    parser.add_argument('--version', '-v', action='version', version=f'{config.LOGOS_SCRIPT_TITLE}, {config.LOGOS_SCRIPT_VERSION} by {config.LOGOS_SCRIPT_AUTHOR}')
    parser.add_argument('--config', '-c', metavar='CONFIG_FILE', help='Use the Logos on Linux config file when setting environment variables. Defaults to ~/.config/Logos_on_Linux/Logos_on_Linux.conf. Optionally can accept a config file provided by the user.')
    parser.add_argument('--verbose', '-V', action='store_true', help='Enable verbose mode')
    parser.add_argument('--skip-fonts', '-F', action='store_true', help='Skip font installations')
    parser.add_argument('--force-root', '-f', action='store_true', help='Set LOGOS_FORCE_ROOT to true, which permits the root user to use the script.')
    parser.add_argument('--reinstall-dependencies', '-I', action='store_true', help="Reinstall your distro's dependencies.")
    parser.add_argument('--debug', '-D', action='store_true', help='Enable Wine debug output.')
    parser.add_argument('--make-skel', '-k', action='store_true', help='Make a skeleton install only.')
    parser.add_argument('--custom-binary-path', '-p', metavar='CUSTOMBINPATH', help='Specify a custom wine binary path.')
    parser.add_argument('--check-resources', '-R', action='store_true', help='Check resources and exit')
    parser.add_argument('--delete-install-log', '-L', action='store_true', help='Delete the installation log file.')
    parser.add_argument('--edit-config', '-e', action='store_true', help='Edit configuration file')
    parser.add_argument('--indexing', '-i', action='store_true', help='Perform indexing')
    parser.add_argument('--backup', '-b', action='store_true', help='Perform backup')
    parser.add_argument('--restore', '-r', action='store_true', help='Perform restore')
    parser.add_argument('--logs', '-l', action='store_true', help='Enable/disable logs')
    parser.add_argument('--dirlink', '-d', action='store_true', help='Create directory link')
    parser.add_argument('--shortcut', '-s', action='store_true', help='Create shortcut')
    parser.add_argument('--passive', '-P', action='store_true', help='Install Faithlife product non-interactively')

    args = parser.parse_args()

    if args.config:
        config.CONFIG_FILE = args.config
        config.set_config_env(config.CONFIG_FILE)

    if args.verbose:
        config.LOG_LEVEL = logging.DEBUG
        config.WINEDEBUG = ''
        config.VERBOSE = True

    if args.delete_install_log:
        config.DELETE_INSTALL_LOG = True

    if args.skip_fonts:
        config.SKIP_FONTS = True

    if args.force_root:
        config.LOGOS_FORCE_ROOT = True

    if args.reinstall_dependencies:
        config.REINSTALL_DEPENDENCIES = True

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

    if args.indexing:
        config.ACTION = 'indexing'
    if args.passive:
        config.PASSIVE = True

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
    die_if_running()
    die_if_root()

    # Set initial config; incl. defining CONFIG_FILE.
    set_default_config()
    # Update config from CONFIG_FILE.
    # FIXME: This means that values in CONFIG_FILE take precedence over env variables.
    #   Is this preferred, or should env variables take precedence over CONFIG_FILE?
    if file_exists(config.CONFIG_FILE):
        config.set_config_env(config.CONFIG_FILE)

    parse_command_line()
    if config.VERBOSE:
        print(f"{config.DIALOG=}")

    # If Logos app is installed, run the desired Logos action.
    if config.LOGOS_EXE is not None and os.access(config.LOGOS_EXE, os.X_OK):
        if config.ACTION == 'indexing':
            run_indexing()
            sys.exit(0)

        elif config.ACTION == 'app':
            run_logos()
            sys.exit(0)

    # Check for environment variables.
    if config.DIALOG is None:
        getDialog()
    else:
        config.DIALOG = config.DIALOG.lower()
        if config.DIALOG == 'tk':
            config.GUI = True
        
    if config.GUI is True:
        with open(config.LOGOS_LOG, "a") as f:
            f.write("Running in a GUI. Enabling logging.\n")
        setDebug()

    die_if_running()
    die_if_root()

    cli_msg(f"{config.LOGOS_SCRIPT_TITLE}, {config.LOGOS_SCRIPT_VERSION} by {config.LOGOS_SCRIPT_AUTHOR}.")

    # Configure logging.
    if config.DELETE_INSTALL_LOG and os.path.isfile(config.LOGOS_LOG):
        os.remove(config.LOGOS_LOG)
    logging.info(f"Using DIALOG: {config.DIALOG}")

    options_default = ["Install Logos Bible Software"]
    options_exit = ["Exit"]
    if file_exists(config.CONFIG_FILE):
        options_installed = [f"Run {config.FLPRODUCT}", "Run Indexing", "Remove Library Catalog", "Remove All Index Files", "Edit Config", "Reinstall Dependencies", "Back up Data", "Restore Data", "Set AppImage", "Control Panel", "Run Winetricks"]
        if config.LOGS == "DISABLED":
            options_installed.append("Enable Logging")
        else:
            options_installed.append("Disable Logging")
        options = options_default + options_installed + options_exit
    else:
        options = options_default + options_exit

    choice = None
    if config.DIALOG is None or config.DIALOG == 'tk':
        classname = "LogosLinuxInstaller"
        installer_app = InstallerApp(className=classname)
        InstallerWindow(installer_app, class_=classname)
        installer_app.mainloop()
        # # Launch app after installation if successful.
        # if config.LOGOS_EXE is not None and os.access(config.LOGOS_EXE, os.X_OK):
        #     run_logos()
        #     sys.exit(0)
        # else:
        #     logos_error("Installation was unsuccessful.")
    elif config.DIALOG == 'curses':
        choice = curses_menu(options, "Welcome to Logos on Linux", "What would you like to do?")

    if choice is None or choice == "Exit":
        sys.exit(0)
    elif choice.startswith("Install"):
        install()
    elif choice == f"Run {config.FLPRODUCT}":
        run_logos()
    elif choice == "Run Indexing":
        run_indexing()
    elif choice == "Remove Library Catalog":
        remove_library_catalog()
    elif choice == "Remove All Index Files":
        remove_all_index_files()
    elif choice == "Edit Config":
        edit_config()
    elif choice == "Reinstall Dependencies":
        checkDependencies()
    elif choice == "Back up Data":
        backup()
    elif choice == "Restore Data":
        restore()
    elif choice == "Set AppImage":
        set_appimage()
    elif choice == "Control Panel":
        run_control_panel()
    elif choice == "Run Winetricks":
        run_winetricks()
    elif choice.endswith("Logging"):
        if config.LOGS == "DISABLED":
            action = 'disable'
        else:
            action = 'enable'
        switch_logging(action=action)
    else:
        logos_error("Unknown menu choice.")

    sys.exit(0)
# END FUNCTION DECLARATIONS

if __name__ == '__main__':
    main()
