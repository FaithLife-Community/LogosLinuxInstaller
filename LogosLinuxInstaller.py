#!/usr/bin/env python3
import logging
import os
import sys
import argparse

import config
import control
import gui_app
import installer
import msg
import tui_app
import utils
import wine


def get_parser():
    parser = argparse.ArgumentParser(description=f'Installs FaithLife Bible Software with Wine on Linux.')
    parser.add_argument(
        '-v', '--version', action='version',
        version=f'{config.LOGOS_SCRIPT_TITLE}, {config.LOGOS_SCRIPT_VERSION} by {config.LOGOS_SCRIPT_AUTHOR}',
    )

    # Define options that affect runtime config.
    cfg = parser.add_argument_group(title="runtime config options")
    cfg.add_argument(
        '-F', '--skip-fonts', action='store_true',
        help='skip font installations',
    )
    cfg.add_argument(
        '-V', '--verbose', action='store_true',
        help='enable verbose mode',
    )
    cfg.add_argument(
        '-D', '--debug', action='store_true',
        help='enable Wine debug output',
    )
    cfg.add_argument(
        '-c', '--config', metavar='CONFIG_FILE',
        help=f'use a custom config file during installation [default: {config.DEFAULT_CONFIG_PATH}]',
    )
    cfg.add_argument(
        '-f', '--force-root', action='store_true',
        help='set LOGOS_FORCE_ROOT to true, which permits the root user to use the script',
    )
    cfg.add_argument(
        '-p', '--custom-binary-path', metavar='CUSTOMBINPATH',
        help='specify a custom wine binary path',
    )
    cfg.add_argument(
        '-L', '--delete-log', action='store_true',
        help='delete the log file',
    )
    cfg.add_argument(
        '-P', '--passive', action='store_true',
        help='run product installer non-interactively',
    )

    # Define runtime actions (mutually exclusive).
    grp = parser.add_argument_group(
        title="subcommands",
        description="these options run specific subcommands; only 1 at a time is accepted",
    )
    cmd = grp.add_mutually_exclusive_group()
    cmd.add_argument(
        '--install-app', action='store_true',
        help='install FaithLife app',
    )
    cmd.add_argument(
        '--run-installed-app', '-C', action='store_true',
        help='run installed FaithLife app',
    )
    cmd.add_argument(
        '--run-indexing', action='store_true',
        help='perform indexing',
    )
    cmd.add_argument(
        '--remove-library-catalog', action='store_true',
        #help='remove library catalog database file'
        help=argparse.SUPPRESS,
    )
    cmd.add_argument(
        '--remove-index-files', action='store_true',
        help=argparse.SUPPRESS,
    )
    cmd.add_argument(
        '--edit-config', action='store_true',
        help='edit configuration file',
    )
    cmd.add_argument(
        '--install-dependencies', '-I', action='store_true',
        help="install your distro's dependencies",
    )
    cmd.add_argument(
        '--backup', action='store_true',
        #help='perform backup',
        help=argparse.SUPPRESS,
    )
    cmd.add_argument(
        '--restore', action='store_true',
        #help='perform restore',
        help=argparse.SUPPRESS,
    )
    cmd.add_argument(
        '--set-appimage', action='store_true',
        help=argparse.SUPPRESS,
    )
    cmd.add_argument(
        '--get-winetricks', action='store_true',
        help='download or update Winetricks',
    )
    cmd.add_argument(
        '--run-winetricks', action='store_true',
        help='start Winetricks window',
    )
    cmd.add_argument(
        '--toggle-app-logging', action='store_true',
        help='enable/disable app logs',
    )
    cmd.add_argument(
        '--create-shortcuts', action='store_true',
        help='[re-]create app shortcuts',
    )
    cmd.add_argument(
        '--remove-install-dir', action='store_true',
        help='delete the current installation folder',
    )
    cmd.add_argument(
        '--dirlink', action='store_true',
        #help='create directory link',
        help=argparse.SUPPRESS,
    )
    cmd.add_argument(
        '--make-skel', action='store_true',
        #help='make a skeleton install only',
        help=argparse.SUPPRESS,
    )
    cmd.add_argument(
        '--check-resources', action='store_true',
        #help='check resources'
        help=argparse.SUPPRESS,
    )
    return parser

def parse_args(args, parser):
    if args.config:
        config.CONFIG_FILE = args.config
        config.set_config_env(config.CONFIG_FILE)

    if args.verbose:
        utils.set_verbose()

    if args.debug:
        utils.set_debug()

    if args.delete_log:
        config.DELETE_LOG = True

    if args.skip_fonts:
        config.SKIP_FONTS = True

    if args.force_root:
        config.LOGOS_FORCE_ROOT = True

    if args.debug:
        utils.set_debug()

    if args.make_skel:
        config.SKEL = True

    if args.custom_binary_path:
        if os.path.isdir(args.custom_binary_path):
            config.CUSTOMBINPATH = args.custom_binary_path
        else:
            parser.exit(status=1, message=f"Custom binary path does not exist: \"{args.custom_binary_path}\"\n")

    if args.passive:
        config.PASSIVE = True

    # Set ACTION function.
    if args.install_app:
        config.ACTION = installer.install
    elif args.run_installed_app:
        config.ACTION = wine.run_logos
    elif args.run_indexing:
        wine.run_indexing
    elif args.remove_library_catalog:
        control.remove_library_catalog
    elif args.remove_index_files:
        control.remove_all_index_files
    elif args.edit_config:
        config.ACTION = control.edit_config
    elif args.install_dependencies:
        config.ACTION = utils.check_dependencies
    elif args.backup:
        config.ACTION = control.backup
    elif args.restore:
        config.ACTION = control.restore
    elif args.set_appimage:
        utils.set_appimage
    elif args.get_winetricks:
        config.ACTION = control.get_winetricks
    elif args.run_winetricks:
        config.ACTION = wine.run_winetricks
    elif args.toggle_app_logging:
        config.ACTION = wine.switch_logging
    elif args.create_shortcuts:
        config.ACTION = installer.create_shortcuts
    elif args.remove_install_dir:
        config.ACTION = control.remove_install_dir
    else: # default function if app is installed
        config.ACTION = run_control_panel

def run_control_panel():
    logging.info(f"Using DIALOG: {config.DIALOG}")
    if config.DIALOG is None or config.DIALOG == 'tk':
        gui_app.control_panel_app()
    else:
        tui_app.control_panel_app()

def main():
    parser = get_parser()
    cli_args = parser.parse_args() # parsing early lets '--help' run immediately

    ### Set runtime config.
    # Initialize logging.
    msg.initialize_logging(config.LOG_LEVEL)
    current_log_level = config.LOG_LEVEL

    # Set default config; incl. defining CONFIG_FILE.
    utils.set_default_config()

    # Update config from CONFIG_FILE.
    if not utils.file_exists(config.CONFIG_FILE) and utils.file_exists(config.LEGACY_CONFIG_FILE):
        config.set_config_env(config.LEGACY_CONFIG_FILE)
        utils.write_config(config.CONFIG_FILE)
    else:
        config.set_config_env(config.CONFIG_FILE)

    # Parse CLI args and update affected config vars.
    parse_args(cli_args, parser)
    # Update terminal log level if set in CLI and changed from current level.
    if config.LOG_LEVEL != current_log_level:
        msg.update_log_level(config.LOG_LEVEL)
        current_log_level = config.LOG_LEVEL

    # Update config based on environment variables.
    config.get_env_config()
    # Update terminal log level if set in environment and changed from current level.
    if config.VERBOSE:
        config.LOG_LEVEL = logging.VERBOSE
    if config.DEBUG:
        config.LOG_LEVEL = logging.DEBUG
    if config.LOG_LEVEL != current_log_level:
        msg.update_log_level(config.LOG_LEVEL)

    # Set DIALOG and GUI variables.
    if config.DIALOG is None:
        utils.getDialog()
    else:
        config.DIALOG = config.DIALOG.lower()
        if config.DIALOG == 'tk':
            config.GUI = True

    # Log persistent config.
    utils.log_current_persistent_config()

    # NOTE: DELETE_LOG is an outlier here. It's an action, but it's one that can
    #   be run in conjunction with other actions, so it gets special treatment
    #   here once config is set.
    if config.DELETE_LOG and os.path.isfile(config.LOGOS_LOG):
        control.delete_log_file_contents()

    ### Run desired action (requested function, defaulting to installer)
    # Run safety checks.
    utils.die_if_running()
    utils.die_if_root()

    # Print terminal banner
    msg.cli_msg(f"{config.LOGOS_SCRIPT_TITLE}, {config.LOGOS_SCRIPT_VERSION} by {config.LOGOS_SCRIPT_AUTHOR}.")

    # Check if app is installed.
    if config.ACTION.__name__ == 'remove_install_dir': # doesn't require app to be installed
        logging.info(f"Running function: {config.ACTION.__name__}")
        config.ACTION()
    elif utils.app_is_installed():
        # Run the desired Logos action.
        if config.ACTION is None:
            msg.logos_error("No function given for this subcommand.")
        logging.info(f"Running function: {config.ACTION.__name__}")
        config.ACTION() # defaults to run_control_panel()
    else:
        logging.info(f"Starting Control Panel")
        run_control_panel()


if __name__ == '__main__':
    main()
