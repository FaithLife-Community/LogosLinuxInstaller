import logging
import sys

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
    appimage_choices = [["AppImage", filename, "AppImage of Wine64"] for filename in appimages]  # noqa: E501
    appimage_choices.extend(["Input Custom AppImage", "Return to Main Menu"])
    sai_choice = tui.menu(
        appimage_choices,
        "AppImage Updater",
        "Which AppImage should be used?"
    )
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
        options_first = []
        options_default = ["Install Logos Bible Software"]
        options_main = [
            "Install Dependencies",
            "Download or Update Winetricks",
            "Run Winetricks"
        ]
        options_installed = [
            f"Run {config.FLPRODUCT}",
            "Run Indexing",
            "Remove Library Catalog",
            "Remove All Index Files",
            "Edit Config",
            "Back up Data",
            "Restore Data",
        ]
        options_exit = ["Exit"]
        if utils.file_exists(config.LOGOS_EXE):
            if config.LLI_LATEST_VERSION and utils.get_runmode() == 'binary':
                logging.debug("Checking if Logos Linux Installers needs updated.")  # noqa: E501
                status, error_message = utils.compare_logos_linux_installer_version()  # noqa: E501
                if status == 0:
                    options_first.append("Update Logos Linux Installer")
                elif status == 1:
                    logging.warning("Logos Linux Installer is up-to-date.")
                elif status == 2:
                    logging.warning("Logos Linux Installer is newer than the latest release.")  # noqa: E501
                else:
                    logging.error(f"{error_message}")

            if config.WINEBIN_CODE == "AppImage" or config.WINEBIN_CODE == "Recommended":  # noqa: E501
                logging.debug("Checking if the AppImage needs updated.")
                status, error_message = utils.compare_recommended_appimage_version()  # noqa: E501
                if status == 0:
                    options_main.insert(0, "Update to Latest AppImage")
                elif status == 1:
                    logging.warning("The AppImage is already set to the latest recommended.")  # noqa: E501
                elif status == 2:
                    logging.warning("The AppImage version is newer than the latest recommended.")  # noqa: E501
                else:
                    logging.error(f"{error_message}")

                options_main.insert(1, "Set AppImage")

            if config.LOGS == "DISABLED":
                options_installed.append("Enable Logging")
            else:
                options_installed.append("Disable Logging")

            options = options_first + options_installed + options_main + options_default + options_exit  # noqa: E501
        else:
            options = options_first + options_default + options_main + options_exit  # noqa: E501

        choice = tui.menu(
            options,
            f"Welcome to Logos on Linux ({config.LLI_CURRENT_VERSION})",
            "What would you like to do?"
        )

        if choice is None or choice == "Exit":
            sys.exit(0)
        elif choice.startswith("Install"):
            installer.ensure_launcher_shortcuts()
        elif choice.startswith("Update Logos Linux Installer"):
            utils.update_to_latest_lli_release()
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
        elif choice == "Update to Latest AppImage":
            utils.update_to_latest_recommended_appimage()
        elif choice == "Set AppImage":
            set_appimage()
        elif choice == "Download or Update Winetricks":
            control.set_winetricks()
        elif choice == "Run Winetricks":
            wine.run_winetricks()
        elif choice.endswith("Logging"):
            wine.switch_logging()
        else:
            msg.logos_error("Unknown menu choice.")
