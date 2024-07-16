#!/usr/bin/env python3
import logging
import os
import argparse
import curses
import sys
import threading

processes = {}
threads = []

import config
import control
import gui_app
import installer
import msg
import network
import system
import tui_app
import utils
import wine

def get_parser():
    desc = "Installs FaithLife Bible Software with Wine on Linux."
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument(
        '-v', '--version', action='version',
        version=(
            f"{config.LLI_TITLE}, "
            f"{config.LLI_CURRENT_VERSION} by {config.LLI_AUTHOR}"
        ),
    )

    # Define options that affect runtime config.
    cfg = parser.add_argument_group(title="runtime config options")
    cfg.add_argument(
        '-F', '--skip-fonts', action='store_true',
        help='skip font installations',
    )
    cfg.add_argument(
        '-a', '--check-for-updates', action='store_true',
        help='force a check for updates'
    )
    cfg.add_argument(
        '-K', '--skip-dependencies', action='store_true',
        help='skip dependencies check and installation',
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
        help=(
            "use a custom config file during installation "
            f"[default: {config.DEFAULT_CONFIG_PATH}]"
        ),
    )
    cfg.add_argument(
        '-f', '--force-root', action='store_true',
        help=(
            "set LOGOS_FORCE_ROOT to true, which permits "
            "the root user to use the script"
        ),
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
        description=(
            "these options run specific subcommands; "
            "only 1 at a time is accepted"
        ),
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
        # help='remove library catalog database file'
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
        # help='perform backup',
        help=argparse.SUPPRESS,
    )
    cmd.add_argument(
        '--restore', action='store_true',
        # help='perform restore',
        help=argparse.SUPPRESS,
    )
    cmd.add_argument(
        '--update-self', '-u', action='store_true',
        help='Update Logos Linux Installer to the latest release.',
    )
    cmd.add_argument(
        '--update-latest-appimage', '-U', action='store_true',
        help='Update the to the latest AppImage.',
    )
    cmd.add_argument(
        '--set-appimage', nargs=1, metavar=('APPIMAGE_FILE_PATH'),
        help='Update the AppImage symlink. Requires a path.',
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
        # help='create directory link',
        help=argparse.SUPPRESS,
    )
    cmd.add_argument(
        '--check-resources', action='store_true',
        # help='check resources'
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

    if network.check_for_updates:
        config.CHECK_UPDATES = True

    if args.skip_dependencies:
        config.SKIP_DEPENDENCIES = True

    if args.force_root:
        config.LOGOS_FORCE_ROOT = True

    if args.debug:
        utils.set_debug()

    if args.custom_binary_path:
        if os.path.isdir(args.custom_binary_path):
            config.CUSTOMBINPATH = args.custom_binary_path
        else:
            message = f"Custom binary path does not exist: \"{args.custom_binary_path}\"\n"  # noqa: E501
            parser.exit(status=1, message=message)

    if args.passive:
        config.PASSIVE = True

    # Set ACTION function.
    actions = {
        'install_app': installer.ensure_launcher_shortcuts,
        'run_installed_app': wine.run_logos,
        'run_indexing': wine.run_indexing,
        'remove_library_catalog': control.remove_library_catalog,
        'remove_index_files': control.remove_all_index_files,
        'edit_config': control.edit_config,
        'install_dependencies': utils.check_dependencies,
        'backup': control.backup,
        'restore': control.restore,
        'update_self': utils.update_to_latest_lli_release,
        'update_latest_appimage': utils.update_to_latest_recommended_appimage,
        'set_appimage': utils.set_appimage_symlink,
        'get_winetricks': control.set_winetricks,
        'run_winetricks': wine.run_winetricks,
        'toggle_app_logging': wine.switch_logging,
        'create_shortcuts': installer.ensure_launcher_shortcuts,
        'remove_install_dir': control.remove_install_dir,
    }

    config.ACTION = None
    for arg, action in actions.items():
        if getattr(args, arg):
            if arg == "update_latest_appimage" or arg == "set_appimage":
                logging.debug("Running an AppImage command.")
                if config.WINEBIN_CODE != "AppImage" and config.WINEBIN_CODE != "Recommended":  # noqa: E501
                    config.ACTION = "disabled"
                    logging.debug("AppImage commands not added since WINEBIN_CODE != (AppImage|Recommended)")  # noqa: E501
                    break
            if arg == "set_appimage":
                config.APPIMAGE_FILE_PATH = getattr(args, arg)[0]
                if not utils.file_exists(config.APPIMAGE_FILE_PATH):
                    e = f"Invalid file path: '{config.APPIMAGE_FILE_PATH}'. File does not exist."  # noqa: E501
                    raise argparse.ArgumentTypeError(e)
                if not utils.check_appimage(config.APPIMAGE_FILE_PATH):
                    e = f"{config.APPIMAGE_FILE_PATH} is not an AppImage."
                    raise argparse.ArgumentTypeError(e)
            config.ACTION = action
            break
    if config.ACTION is None:
        config.ACTION = run_control_panel
    logging.debug(f"{config.ACTION=}")


def run_control_panel():
    logging.info(f"Using DIALOG: {config.DIALOG}")
    if config.DIALOG is None or config.DIALOG == 'tk':
        gui_app.control_panel_app()
    else:
        try:
            curses.wrapper(tui_app.control_panel_app)
        except KeyboardInterrupt:
            raise
        except SystemExit:
            logging.info("Caught SystemExit, exiting gracefully...")
            try:
                close()
            except Exception as e:
                raise
            raise
        except curses.error as e:
            logging.error(f"Curses error in run_control_panel(): {e}")
            raise
        except Exception as e:
            logging.error(f"An error occurred in run_control_panel(): {e}")
            raise


def main():
    parser = get_parser()
    cli_args = parser.parse_args()  # parsing early lets 'help' run immediately

    # Set runtime config.
    # Initialize logging.
    msg.initialize_logging(config.LOG_LEVEL)
    current_log_level = config.LOG_LEVEL

    # Set default config; incl. defining CONFIG_FILE.
    utils.set_default_config()

    # Update config from CONFIG_FILE.
    if not utils.file_exists(config.CONFIG_FILE) and utils.file_exists(config.LEGACY_CONFIG_FILE):  # noqa: E501
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
    utils.set_runtime_config()
    # Update terminal log level if set in environment and changed from current
    # level.
    if config.VERBOSE:
        config.LOG_LEVEL = logging.VERBOSE
    if config.DEBUG:
        config.LOG_LEVEL = logging.DEBUG
    if config.LOG_LEVEL != current_log_level:
        msg.update_log_level(config.LOG_LEVEL)

    # Set DIALOG and GUI variables.
    if config.DIALOG is None:
        system.get_dialog()
    else:
        config.DIALOG = config.DIALOG.lower()
        if config.DIALOG == 'tk':
            config.GUI = True

    if config.DIALOG == 'curses':
        config.use_python_dialog = system.test_dialog_version()

        if config.use_python_dialog is None:
            logging.debug("The 'dialog' package was not found. Falling back to Python Curses.")
            config.use_python_dialog = False
        elif config.use_python_dialog:
            logging.debug("Dialog version is up-to-date.")
            config.use_python_dialog = True
        else:
            logging.error("Dialog version is outdated. The program will fall back to Curses.")
            config.use_python_dialog = False

    # Log persistent config.
    utils.log_current_persistent_config()

    # NOTE: DELETE_LOG is an outlier here. It's an action, but it's one that
    # can be run in conjunction with other actions, so it gets special
    # treatment here once config is set.
    if config.DELETE_LOG and os.path.isfile(config.LOGOS_LOG):
        control.delete_log_file_contents()

    # Run desired action (requested function, defaulting to installer)
    # Run safety checks.
    # FIXME: Fix utils.die_if_running() for GUI; as it is, it breaks GUI
    # self-update when updating LLI as it asks for a confirmation in the CLI.
    # Disabled until it can be fixed. Avoid running multiple instances of the
    # program.
    # utils.die_if_running()
    utils.die_if_root()

    # Print terminal banner
    logging.info(f"{config.LLI_TITLE}, {config.LLI_CURRENT_VERSION} by {config.LLI_AUTHOR}.")  # noqa: E501
    logging.debug(f"Installer log file: {config.LOGOS_LOG}")

    network.check_for_updates()

    # Check if app is installed.
    install_required = [
        'backup',
        'create_shortcuts',
        'remove_all_index_files',
        'remove_library_catalog',
        'restore',
        'run_indexing',
        'run_logos',
        'switch_logging',
    ]
    if config.ACTION == "disabled":
        msg.logos_error("That option is disabled.", "info")
    elif config.ACTION.__name__ not in install_required:
        logging.info(f"Running function: {config.ACTION.__name__}")
        config.ACTION()
    elif utils.app_is_installed():
        # Run the desired Logos action.
        logging.info(f"Running function: {config.ACTION.__name__}")
        config.ACTION()  # defaults to run_control_panel()
    else:
        logging.info("Starting Control Panel")
        run_control_panel()


def close():
    logging.debug("Closing Logos on Linux.")
    for thread in threads:
        thread.join()
    if len(processes) > 0:
        wine.end_wine_processes()
    else:
        logging.debug("No processes found.")
    logging.debug("Closing Logos on Linux finished.")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        close()

    close()
