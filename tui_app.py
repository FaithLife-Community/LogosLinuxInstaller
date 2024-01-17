import logging
import sys
import curses

import config
import control
import tui
import installer
import msg
import utils
import wine

def set_appimage():
    # TODO: Allow specifying the AppImage File
    appimages = utils.find_appimage_files()
    appimage_choices = [["AppImage", filename, "AppImage of Wine64"] for filename in appimages]
    appimage_choices.extend(["Input Custom AppImage", "Return to Main Menu"])
    sai_choice = tui.menu(appimage_choices, "AppImage Updater", "Which AppImage should be used?")
    if sai_choice == "Return to Main Menu":
        pass  # Do nothing.
    elif sai_choice == "Input Custom AppImage":
        appimage_filename = tui.get_user_input("Enter AppImage filename: ")
        config.SELECTED_APPIMAGE_FILENAME = appimage_filename
        utils.set_appimage_symlink()
    else:
        appimage_filename = sai_choice
        config.SELECTED_APPIMAGE_FILENAME = appimage_filename
        utils.set_appimage_symlink()

def control_panel_app():
    # Run TUI.
    while True:
        options_default = ["Install Logos Bible Software"]
        options_exit = ["Exit"]
        if utils.file_exists(config.LOGOS_EXE):
            options_installed = [f"Run {config.FLPRODUCT}", "Run Indexing", "Remove Library Catalog", "Remove All Index Files", "Edit Config", "Install Dependencies", "Back up Data", "Restore Data", "Set AppImage", "Download or Update Winetricks", "Run Winetricks"]
            if config.LOGS == "DISABLED":
                options_installed.append("Enable Logging")
            else:
                options_installed.append("Disable Logging")
            options = options_default + options_installed + options_exit
        else:
            options = options_default + options_exit

        choice = tui.menu(options, "Welcome to Logos on Linux", "What would you like to do?")

        if choice is None or choice == "Exit":
            sys.exit(0)
        elif choice.startswith("Install"):
            installer.install()
        elif choice == f"Run {config.FLPRODUCT}":
            wine.run_logos()
        elif choice == "Run Indexing":
            wine.run_indexing()
        elif choice == "Remove Library Catalog":
            control.remove_library_catalog()
        elif choice == "Remove All Index Files":
            control.remove_all_index_files()
        elif choice == "Edit Config":
            control.edit_config()
        elif choice == "Install Dependencies":
            utils.check_dependencies()
        elif choice == "Back up Data":
            control.backup()
        elif choice == "Restore Data":
            control.restore()
        elif choice == "Set AppImage":
            set_appimage()
        elif choice == "Download or Update Winetricks":
            control.get_winetricks()
        elif choice == "Run Winetricks":
            wine.run_winetricks()
        elif choice.endswith("Logging"):
            wine.switch_logging()
        else:
            msg.logos_error("Unknown menu choice.")
