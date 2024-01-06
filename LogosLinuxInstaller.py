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
from installer import setWinetricks
from msg import cli_msg
from msg import initialize_logging
from msg import logos_error
from msg import update_log_level
from utils import check_dependencies
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
    parser.add_argument(
        '-v', '--version', action='version',
        version=f'{config.LOGOS_SCRIPT_TITLE}, {config.LOGOS_SCRIPT_VERSION} by {config.LOGOS_SCRIPT_AUTHOR}',
    )

    # Define options that affect runtime config.
    cfg = parser.add_argument_group(title="runtime config options", description="these options set runtime config")
    cfg.add_argument(
        '-F', '--skip-fonts', action='store_true',
        help='skip font installations'
    )
    cfg.add_argument(
        '-V', '--verbose', action='store_true',
        help='enable verbose mode'
    )
    cfg.add_argument(
        '-D', '--debug', action='store_true',
        help='enable Wine debug output'
    )
    cfg.add_argument(
        '-c', '--config', metavar='CONFIG_FILE',
        help=f'use a custom config file during installation [default: {config.DEFAULT_CONFIG_PATH}]'
    )
    cfg.add_argument(
        '-f', '--force-root', action='store_true',
        help='set LOGOS_FORCE_ROOT to true, which permits the root user to use the script'
    )
    cfg.add_argument(
        '-p', '--custom-binary-path', metavar='CUSTOMBINPATH',
        help='specify a custom wine binary path'
    )
    cfg.add_argument(
        '-L', '--delete-log', action='store_true',
        help='delete the log file'
    )
    cfg.add_argument(
        '-P', '--passive', action='store_true',
        help='run product installer non-interactively'
    )

    # Define runtime actions (mutually exclusive).
    grp = parser.add_argument_group(
        title="subcommands",
        description="these options run specific subcommands; only 1 at a time is accepted")
    cmd = grp.add_mutually_exclusive_group()
    cmd.add_argument(
        '--control-panel', '-C', action='store_true',
        help='open Control Panel app'
    )
    cmd.add_argument(
        '--run-indexing', action='store_true',
        help='perform indexing'
    )
    cmd.add_argument(
        '--reinstall-dependencies', '-I', action='store_true',
        help="reinstall your distro's dependencies"
    )
    cmd.add_argument(
        '--toggle-app-logging', action='store_true',
        help='enable/disable app logs'
    )
    cmd.add_argument(
        '--run-winetricks', action='store_true',
        help='start Winetricks window'
    )
    cmd.add_argument(
        '--get-winetricks', action='store_true',
        help='download or update Winetricks'
    )
    cmd.add_argument(
        '--edit-config', action='store_true',
        help='edit configuration file'
    )
    cmd.add_argument(
        '--create-shortcut', action='store_true',
        help='[re-]create app shortcut',
    )
    cmd.add_argument(
        '--backup', action='store_true',
        help=argparse.SUPPRESS, # 'Perform backup'
    )
    cmd.add_argument(
        '--restore', action='store_true',
        help=argparse.SUPPRESS # 'Perform restore'
    )
    cmd.add_argument(
        '--dirlink', action='store_true',
        help=argparse.SUPPRESS, # 'Create directory link'
    )
    cmd.add_argument(
        '--make-skel', action='store_true',
        help=argparse.SUPPRESS, # 'Make a skeleton install only.'
    )
    cmd.add_argument(
        '--check-resources', action='store_true',
        help=argparse.SUPPRESS,  # 'check resources and exit'
    )
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
        check_dependencies()
        sys.exit(0)

    if args.get_winetricks: 
       setWinetricks()
       sys.exit(0)

    if args.run_winetricks:
        run_winetricks()
        sys.exit(0)

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
        # If Logos app is installed, run the desired Logos action.
        if config.LOGOS_EXE is not None and os.access(config.LOGOS_EXE, os.X_OK):
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
        if config.DIALOG is None or config.DIALOG == 'tk':
            classname = "LogosLinuxInstaller"
            installer_app = App(className=classname)
            InstallerWindow(installer_app, class_=classname)
            installer_app.mainloop()

    if config.GUI is False:
        while True:
            options_default = ["Install Logos Bible Software"]
            options_exit = ["Exit"]
            if file_exists(config.LOGOS_EXE):
                options_installed = [f"Run {config.FLPRODUCT}", "Run Indexing", "Remove Library Catalog", "Remove All Index Files", "Edit Config", "Reinstall Dependencies", "Back up Data", "Restore Data", "Set AppImage", "Control Panel", "Download or Update Winetricks", "Run Winetricks"]
                if config.LOGS == "DISABLED":
                    options_installed.append("Enable Logging")
                else:
                    options_installed.append("Disable Logging")
                options = options_default + options_installed + options_exit
            else:
                options = options_default + options_exit

            choice = None
            if config.DIALOG == 'curses':
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
                check_dependencies()
            elif choice == "Back up Data":
                backup()
            elif choice == "Restore Data":
                restore()
            elif choice == "Set AppImage":
                set_appimage()
            elif choice == "Control Panel":
                run_control_panel()
            elif choice == "Download or Update Winetricks":
                setWinetricks()
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
