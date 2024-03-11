import json
import logging
import os
import tempfile


# Define and set variables that are required in the config file.
core_config_keys = [
    "FLPRODUCT", "TARGETVERSION", "LOGOS_RELEASE_VERSION",
    "INSTALLDIR", "WINETRICKSBIN", "WINEBIN_CODE", "WINE_EXE",
    "WINECMD_ENCODING", "LOGS", "BACKUPDIR", "LAST_UPDATED",
    "RECOMMENDED_WINE64_APPIMAGE_URL",
]
for k in core_config_keys:
    globals()[k] = os.getenv(k)

# Define and set additional variables that can be set in the env.
extended_config = {
    'APPIMAGE_LINK_SELECTION_NAME': 'selected_wine.AppImage',
    'CHECK_UPDATES': False,
    'CONFIG_FILE': None,
    'CUSTOMBINPATH': None,
    'DEBUG': False,
    'DELETE_LOG': None,
    'DIALOG': None,
    'LOGOS_LOG': os.path.expanduser("~/.local/state/Logos_on_Linux/Logos_on_Linux.log"),  # noqa: E501
    'LOGOS_EXE': None,
    'LOGOS_EXECUTABLE': None,
    'LOGOS_VERSION': None,
    'LOGOS64_MSI': "Logos-x64.msi",
    'LOGOS64_URL': None,
    'REINSTALL_DEPENDENCIES': False,
    'SELECTED_APPIMAGE_FILENAME': None,
    'SKIP_DEPENDENCIES': False,
    'SKIP_FONTS': False,
    'VERBOSE': False,
    'WINE_EXE': None,
    'WINEDEBUG': "fixme-all,err-all",
    'WINEDLLOVERRIDES': '',
    'WINEPREFIX': None,
    'WINESERVER_EXE': None,
    'WINETRICKS_UNATTENDED': None,
}
for key, default in extended_config.items():
    globals()[key] = os.getenv(key, default)

# Set other run-time variables not set in the env.
ACTION = 'app'
APPIMAGE_FILE_PATH = None
BADPACKAGES = None
DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/Logos_on_Linux/Logos_on_Linux.json")  # noqa: E501
GUI = None
INSTALL_STEP = 0
INSTALL_STEPS_COUNT = 0
L9PACKAGES = None
LEGACY_CONFIG_FILE = os.path.expanduser("~/.config/Logos_on_Linux/Logos_on_Linux.conf")  # noqa: E501
LLI_AUTHOR = "Ferion11, John Goodman, T. H. Wright, N. Marti"
LLI_CURRENT_VERSION = "4.0.0-alpha.4"
LLI_LATEST_VERSION = None
LLI_TITLE = "Logos Linux Installer"
LOG_LEVEL = logging.WARNING
LOGOS_BLUE = '#0082FF'
LOGOS_GRAY = '#E7E7E7'
LOGOS_WHITE = '#FCFCFC'
# LOGOS_WHITE = '#F7F7F7'
LOGOS_DIR = os.path.dirname(LOGOS_EXE) if LOGOS_EXE else None  # noqa: F821
LOGOS_FORCE_ROOT = False
LOGOS_ICON_FILENAME = None
LOGOS_ICON_URL = None
LOGOS_LATEST_VERSION_FILENAME = "LogosLinuxInstaller"
LOGOS_LATEST_VERSION_URL = None
LOGOS9_RELEASES = None      # used to save downloaded releases list
LOGOS9_WINE64_BOTTLE_TARGZ_NAME = "wine64_bottle.tar.gz"
LOGOS9_WINE64_BOTTLE_TARGZ_URL = f"https://github.com/ferion11/wine64_bottle_dotnet/releases/download/v5.11b/{LOGOS9_WINE64_BOTTLE_TARGZ_NAME}"  # noqa: E501
LOGOS10_RELEASES = None     # used to save downloaded releases list
MYDOWNLOADS = None
OS_NAME = None
OS_RELEASE = None
PACKAGE_MANAGER_COMMAND_INSTALL = None
PACKAGE_MANAGER_COMMAND_REMOVE = None
PACKAGE_MANAGER_COMMAND_QUERY = None
PACKAGES = None
PASSIVE = None
PRESENT_WORKING_DIRECTORY = os.getcwd()
REBOOT_REQUIRED = None
RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME = None
RECOMMENDED_WINE64_APPIMAGE_FULL_VERSION = None
RECOMMENDED_WINE64_APPIMAGE_FILENAME = None
RECOMMENDED_WINE64_APPIMAGE_VERSION = None
RECOMMENDED_WINE64_APPIMAGE_BRANCH = None
SUPERUSER_COMMAND = None
VERBUM_PATH = None
WINETRICKS_URL = "https://raw.githubusercontent.com/Winetricks/winetricks/5904ee355e37dff4a3ab37e1573c56cffe6ce223/src/winetricks"  # noqa: E501
WORKDIR = tempfile.mkdtemp(prefix="/tmp/LBS.")


def get_config_file_dict(config_file_path):
    config_dict = {}
    if config_file_path.endswith('.json'):
        try:
            with open(config_file_path, 'r') as config_file:
                cfg = json.load(config_file)

            for key, value in cfg.items():
                config_dict[key] = value
            return config_dict
        except TypeError as e:
            logging.error("Error opening Config file.")
            logging.error(e)
            return None
        except FileNotFoundError:
            logging.info(f"No config file not found at {config_file_path}")
            return config_dict
        except json.JSONDecodeError as e:
            logging.error("Config file could not be read.")
            logging.error(e)
            return None
    elif config_file_path.endswith('.conf'):
        # Legacy config from bash script.
        logging.info("Reading from legacy config file.")
        with open(config_file_path, 'r') as config_file:
            for line in config_file:
                line = line.strip()
                if len(line) == 0:  # skip blank lines
                    continue
                if line[0] == '#':  # skip commented lines
                    continue
                parts = line.split('=')
                if len(parts) == 2:
                    value = parts[1].strip('"').strip("'")  # remove quotes
                    vparts = value.split('#')  # get rid of potential comment
                    if len(vparts) > 1:
                        value = vparts[0].strip().strip('"').strip("'")
                    config_dict[parts[0]] = value
        return config_dict


def set_config_env(config_file_path):
    config_dict = get_config_file_dict(config_file_path)
    if config_dict is None:
        return
        # msg.logos_error(f"Error: Unable to get config at {config_file_path}")
    logging.info(f"Setting {len(config_dict)} variables from config file.")
    for key, value in config_dict.items():
        globals()[key] = value


def get_env_config():
    for var in globals().keys():
        val = os.getenv(var)
        if val is not None:
            logging.info(f"Setting '{var}' to '{val}'")
            globals()[var] = val
