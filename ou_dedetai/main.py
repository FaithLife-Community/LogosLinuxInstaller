#!/usr/bin/env python3
import argparse
import curses

from ou_dedetai.config import EphemeralConfiguration, PersistentConfiguration, get_wine_prefix_path

try:
    import dialog  # noqa: F401
except ImportError:
    pass
import logging
import os
import shutil
import sys

from . import cli
from . import config
from . import control
from . import constants
from . import gui_app
from . import msg
from . import network
from . import system
from . import tui_app
from . import utils
from . import wine

from .config import processes, threads


def get_parser():
    desc = "Installs FaithLife Bible Software with Wine."
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument(
        '-v', '--version', action='version',
        version=(
            f"{constants.APP_NAME}, "
            f"{constants.LLI_CURRENT_VERSION} by {constants.LLI_AUTHOR}"
        ),
    )

    # Define options that affect runtime config.
    cfg = parser.add_argument_group(title="runtime config options")
    cfg.add_argument(
        '-a', '--check-for-updates', action='store_true',
        help='force a check for updates'
    )
    cfg.add_argument(
        '-K', '--skip-dependencies', action='store_true',
        help='skip dependencies check and installation',
    )
    cfg.add_argument(
        '-F', '--skip-fonts', action='store_true',
        help='skip font installations',
    )
    cfg.add_argument(
        '-W', '--skip-winetricks', action='store_true',
        help='skip winetricks installations. For development purposes only!!!',
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
            f"[default: {constants.DEFAULT_CONFIG_PATH}]"
        ),
    )
    cfg.add_argument(
        '-f', '--force-root', action='store_true',
        help=(
            "Running Wine/winetricks as root is highly discouraged. "
            "Set this to do allow it anyways"
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
        help=f'Update {constants.APP_NAME} to the latest release.',
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
        '--install-d3d-compiler', action='store_true',
        help='Install d3dcompiler through Winetricks',
    )
    cmd.add_argument(
        '--install-fonts', action='store_true',
        help='Install fonts through Winetricks',
    )
    cmd.add_argument(
        '--install-icu', action='store_true',
        help='Install ICU data files for Logos 30+',
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
    cmd.add_argument(
        '--winetricks', nargs='+',
        help="run winetricks command",
    )
    return parser


def parse_args(args, parser) -> EphemeralConfiguration:
    if args.config:
        ephemeral_config = EphemeralConfiguration.load_from_path(args.config)
    else:
        ephemeral_config = EphemeralConfiguration.load()

    # XXX: move the following options into the ephemeral_config
    if args.verbose:
        msg.update_log_level(logging.INFO)

    if args.debug:
        msg.update_log_level(logging.DEBUG)

    if args.delete_log:
        ephemeral_config.delete_log = True

    if args.set_appimage:
        ephemeral_config.wine_appimage_path = args.set_appimage[0]

    if args.skip_fonts:
        ephemeral_config.install_fonts_skip = True

    if args.skip_winetricks:
        ephemeral_config.winetricks_skip = True

    # FIXME: Should this have been args.check_for_updates?
    # Should this even be an option?
    # if network.check_for_updates:
    #     ephemeral_config.check_updates_now = True

    if args.skip_dependencies:
        ephemeral_config.install_dependencies_skip = True

    if args.force_root:
        ephemeral_config.app_run_as_root_permitted = True

    if args.custom_binary_path:
        if os.path.isdir(args.custom_binary_path):
            # Set legacy environment variable for config to pick up
            os.environ["CUSTOMBINPATH"] = args.custom_binary_path
        else:
            message = f"Custom binary path does not exist: \"{args.custom_binary_path}\"\n"  # noqa: E501
            parser.exit(status=1, message=message)

    if args.passive:
        ephemeral_config.faithlife_install_passive = True

    # Set ACTION function.
    actions = {
        'backup': cli.backup,
        'create_shortcuts': cli.create_shortcuts,
        'edit_config': cli.edit_config,
        'get_winetricks': cli.get_winetricks,
        'install_app': cli.install_app,
        'install_d3d_compiler': cli.install_d3d_compiler,
        'install_dependencies': cli.install_dependencies,
        'install_fonts': cli.install_fonts,
        'install_icu': cli.install_icu,
        'remove_index_files': cli.remove_index_files,
        'remove_install_dir': cli.remove_install_dir,
        'remove_library_catalog': cli.remove_library_catalog,
        'restore': cli.restore,
        'run_indexing': cli.run_indexing,
        'run_installed_app': cli.run_installed_app,
        'run_winetricks': cli.run_winetricks,
        'set_appimage': cli.set_appimage,
        'toggle_app_logging': cli.toggle_app_logging,
        'update_self': cli.update_self,
        'update_latest_appimage': cli.update_latest_appimage,
        'winetricks': cli.winetricks,
    }

    config.ACTION = None
    for arg, action in actions.items():
        if getattr(args, arg):
            if arg == "set_appimage":
                ephemeral_config.wine_appimage_path = getattr(args, arg)[0]
                if not utils.file_exists(ephemeral_config.wine_appimage_path):
                    e = f"Invalid file path: '{ephemeral_config.wine_appimage_path}'. File does not exist."  # noqa: E501
                    raise argparse.ArgumentTypeError(e)
                if not utils.check_appimage(ephemeral_config.wine_appimage_path):
                    e = f"{ephemeral_config.wine_appimage_path} is not an AppImage."
                    raise argparse.ArgumentTypeError(e)
            if arg == 'winetricks':
                config.winetricks_args = getattr(args, 'winetricks')
            config.ACTION = action
            break
    if config.ACTION is None:
        config.ACTION = run_control_panel
    logging.debug(f"{config.ACTION=}")
    return ephemeral_config


def run_control_panel(ephemeral_config: EphemeralConfiguration):
    logging.info(f"Using DIALOG: {config.DIALOG}")
    if config.DIALOG is None or config.DIALOG == 'tk':
        gui_app.control_panel_app(ephemeral_config)
    else:
        try:
            curses.wrapper(tui_app.control_panel_app, ephemeral_config)
        except KeyboardInterrupt:
            raise
        except SystemExit:
            logging.info("Caught SystemExit, exiting gracefully...")
            try:
                close()
            except Exception as e:
                raise e
            raise
        except curses.error as e:
            logging.error(f"Curses error in run_control_panel(): {e}")
            raise e
        except Exception as e:
            logging.error(f"An error occurred in run_control_panel(): {e}")
            raise e


def setup_config() -> EphemeralConfiguration:
    parser = get_parser()
    cli_args = parser.parse_args()  # parsing early lets 'help' run immediately

    # Get config based on env and configuration file temporarily just to load a couple values out
    # We'll load this fully later.
    temp = EphemeralConfiguration.load()
    log_level = temp.log_level or constants.DEFAULT_LOG_LEVEL
    app_log_path = temp.app_log_path or constants.DEFAULT_APP_LOG_PATH
    del temp

    # Set runtime config.
    # Initialize logging.
    msg.initialize_logging(log_level, app_log_path)

    # Set default config; incl. defining CONFIG_FILE.
    utils.set_default_config()

    # XXX: do this in the new scheme (read then write the config).
    # We also want to remove the old file, (stored in CONFIG_FILE?)

    # # Update config from CONFIG_FILE.
    # if not utils.file_exists(config.CONFIG_FILE):  # noqa: E501
    #     for legacy_config in constants.LEGACY_CONFIG_FILES:
    #         if utils.file_exists(legacy_config):
    #             config.set_config_env(legacy_config)
    #             utils.write_config(config.CONFIG_FILE)
    #             os.remove(legacy_config)
    #             break
    # else:
    #     config.set_config_env(config.CONFIG_FILE)

    # Parse CLI args and update affected config vars.
    return parse_args(cli_args, parser)


def set_dialog():
    # Set DIALOG and GUI variables.
    if config.DIALOG is None:
        system.get_dialog()
    else:
        config.DIALOG = config.DIALOG.lower()

    if config.DIALOG == 'curses' and "dialog" in sys.modules and config.use_python_dialog is None:  # noqa: E501
        config.use_python_dialog = system.test_dialog_version()

        if config.use_python_dialog is None:
            logging.debug("The 'dialog' package was not found. Falling back to Python Curses.")  # noqa: E501
            config.use_python_dialog = False
        elif config.use_python_dialog:
            logging.debug("Dialog version is up-to-date.")
            config.use_python_dialog = True
        else:
            logging.error("Dialog version is outdated. The program will fall back to Curses.")  # noqa: E501
            config.use_python_dialog = False
    logging.debug(f"Use Python Dialog?: {config.use_python_dialog}")


def check_incompatibilities():
    # Check for AppImageLauncher
    if shutil.which('AppImageLauncher'):
        question_text = "Remove AppImageLauncher? A reboot will be required."
        secondary = (
            "Your system currently has AppImageLauncher installed.\n"
            f"{constants.APP_NAME} is not compatible with AppImageLauncher.\n"
            f"For more information, see: {constants.REPOSITORY_LINK}/issues/114"
        )
        no_text = "User declined to remove AppImageLauncher."
        msg.logos_continue_question(question_text, no_text, secondary)
        system.remove_appimagelauncher()


def is_app_installed(ephemeral_config: EphemeralConfiguration):
    persistent_config = PersistentConfiguration.load_from_path(ephemeral_config.config_path)
    if persistent_config.faithlife_product is None or persistent_config.install_dir is None:
        # Not enough information stored to find the product
        return False
    wine_prefix = ephemeral_config.wine_prefix or get_wine_prefix_path(persistent_config.install_dir)
    return utils.find_installed_product(persistent_config.faithlife_product, wine_prefix)


def run(ephemeral_config: EphemeralConfiguration):
    # Run desired action (requested function, defaults to control_panel)
    if config.ACTION == "disabled":
        msg.logos_error("That option is disabled.", "info")
    if config.ACTION.__name__ == 'run_control_panel':
        # if utils.app_is_installed():
        #     wine.set_logos_paths()
        config.ACTION(ephemeral_config)  # run control_panel right away
        return

    # Only control_panel ACTION uses TUI/GUI interface; all others are CLI.
    config.DIALOG = 'cli'

    install_required = [
        'backup',
        'create_shortcuts',
        'install_d3d_compiler',
        'install_fonts',
        'install_icu',
        'remove_index_files',
        'remove_library_catalog',
        'restore',
        'run_indexing',
        'run_installed_app',
        'run_winetricks',
        'set_appimage',
        'toggle_app_logging',
        'winetricks',
    ]
    if config.ACTION.__name__ not in install_required:
        logging.info(f"Running function: {config.ACTION.__name__}")
        config.ACTION(ephemeral_config)
    elif is_app_installed(ephemeral_config):  # install_required; checking for app
        # wine.set_logos_paths()
        # Run the desired Logos action.
        logging.info(f"Running function: {config.ACTION.__name__}")  # noqa: E501
        config.ACTION(ephemeral_config)
    else:  # install_required, but app not installed
        msg.logos_error("App not installed…")


def main():
    ephemeral_config = setup_config()
    set_dialog()

    # XXX: consider configuration migration from legacy to new

    # NOTE: DELETE_LOG is an outlier here. It's an action, but it's one that
    # can be run in conjunction with other actions, so it gets special
    # treatment here once config is set.
    app_log_path = ephemeral_config.app_log_path or constants.DEFAULT_APP_LOG_PATH
    if ephemeral_config.delete_log and os.path.isfile(app_log_path):
        # Write empty file.
        with open(app_log_path, 'w') as f:
            f.write('')

    # Run safety checks.
    # FIXME: Fix utils.die_if_running() for GUI; as it is, it breaks GUI
    # self-update when updating LLI as it asks for a confirmation in the CLI.
    # Disabled until it can be fixed. Avoid running multiple instances of the
    # program.
    # utils.die_if_running()
    if os.getuid() == 0 and not ephemeral_config.app_run_as_root_permitted:
        msg.logos_error("Running Wine/winetricks as root is highly discouraged. Use -f|--force-root if you must run as root. See https://wiki.winehq.org/FAQ#Should_I_run_Wine_as_root.3F")  # noqa: E501

    # Print terminal banner
    logging.info(f"{constants.APP_NAME}, {constants.LLI_CURRENT_VERSION} by {constants.LLI_AUTHOR}.")  # noqa: E501

    check_incompatibilities()

    run(ephemeral_config)


def close():
    logging.debug(f"Closing {constants.APP_NAME}.")
    for thread in threads:
        # Only wait on non-daemon threads.
        if not thread.daemon:
            thread.join()
    logging.debug(f"Closing {constants.APP_NAME} finished.")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        close()

    close()
