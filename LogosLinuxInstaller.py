#!/usr/bin/env python3
import logging
import os
import sys
import argparse

import config
from app import App
from app import ControlWindow
from app import InstallerWindow
from control import open_config_file
from control import remove_all_index_files
from control import remove_library_catalog
from installer import install
from msg import cli_msg
from msg import initialize_logging
from msg import logos_error
from msg import update_log_level
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
from utils import write_config
from wine import run_indexing
from wine import run_logos
from wine import run_winetricks
from wine import switch_logging


def parse_command_line():
    parser = argparse.ArgumentParser(description=f'Installs FaithLife Bible Software with Wine on Linux.')
    parser.add_argument('--version', '-v', action='version', version=f'{config.LOGOS_SCRIPT_TITLE}, {config.LOGOS_SCRIPT_VERSION} by {config.LOGOS_SCRIPT_AUTHOR}')
    parser.add_argument('--config', '-c', metavar='CONFIG_FILE', help=f'Use a custom Logos on Linux config file during installation. Default config is at {config.DEFAULT_CONFIG_PATH}.')
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
    parser.add_argument('--control-panel', '-C', action='store_true', help='Open Control Panel app')
    return parser.parse_args()

def parse_args(args):
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
            cli_msg(f"{config.LOGOS_SCRIPT_TITLE}: User supplied path: \"{args.custom_binary_path}\". Custom binary path does not exist.")
            parser.print_help()
            sys.exit(1)

    if args.indexing:
        config.ACTION = 'indexing'
    if args.passive:
        config.PASSIVE = True
    if args.logs:
        config.ACTION = 'logging'
    if args.control_panel:
        config.ACTION = 'control'

def run_control_panel():
    classname = "LogosLinuxControlPanel"
    app = App(className=classname)
    win = ControlWindow(app, class_=classname)
    app.mainloop()

def edit_config():
    open_config_file()

def backup():
    pass

def restore():
    pass

def main():
    cli_args = parse_command_line()

    # Initialize logging.
    initialize_logging(config.LOG_LEVEL)

    die_if_running()
    die_if_root()

    # Set initial config; incl. defining CONFIG_FILE.
    set_default_config()
    # Update config from CONFIG_FILE.
    if not file_exists(config.CONFIG_FILE) and file_exists(config.LEGACY_CONFIG_FILE):
        config.set_config_env(config.LEGACY_CONFIG_FILE)
        write_config(config.CONFIG_FILE)
    else:
        config.set_config_env(config.CONFIG_FILE)

    # Parse CLI args and update affected config vars.
    parse_args(cli_args)

    # Set terminal log level based on CLI config.
    cli_log_level = config.LOG_LEVEL
    update_log_level(config.LOG_LEVEL)

    # Re-read environment variables.
    config.get_env_config()

    if config.DELETE_INSTALL_LOG and os.path.isfile(config.LOGOS_LOG):
        # Write empty file before continuing.
        with open(config.LOGOS_LOG, 'w') as f:
            f.write('')

    # If Logos app is installed, run the desired Logos action.
    if config.LOGOS_EXE is not None and os.access(config.LOGOS_EXE, os.X_OK):
        logging.info(f"App is installed: {config.LOGOS_EXE}")
        if config.ACTION == 'control':
            run_control_panel()
            sys.exit(0)
        elif config.ACTION == 'indexing':
            run_indexing()
            sys.exit(0)
        elif config.ACTION == 'logging':
            switch_logging()
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

    cli_msg(f"{config.LOGOS_SCRIPT_TITLE}, {config.LOGOS_SCRIPT_VERSION} by {config.LOGOS_SCRIPT_AUTHOR}.")
    logging.info("Starting installation.") 
    logging.info(f"Using DIALOG: {config.DIALOG}")

    if config.GUI is True:
        setDebug()

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
        installer_app = App(className=classname)
        InstallerWindow(installer_app, class_=classname)
        installer_app.mainloop()
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
        switch_logging()
    else:
        logos_error("Unknown menu choice.")

    sys.exit(0)
# END FUNCTION DECLARATIONS

if __name__ == '__main__':
    main()
