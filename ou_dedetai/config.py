import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Optional


# Define app name variables.
name_app = 'Ou Dedetai'
name_binary = 'oudedetai'
name_package = 'ou_dedetai'
repo_link = "https://github.com/FaithLife-Community/LogosLinuxInstaller"

# Define and set variables that are required in the config file.
core_config_keys = [
    "FLPRODUCT", "TARGETVERSION", "TARGET_RELEASE_VERSION",
    "current_logos_version", "curses_colors",
    "INSTALLDIR", "WINETRICKSBIN", "WINEBIN_CODE", "WINE_EXE",
    "WINECMD_ENCODING", "LOGS", "BACKUPDIR", "LAST_UPDATED",
    "RECOMMENDED_WINE64_APPIMAGE_URL", "LLI_LATEST_VERSION",
    "logos_release_channel", "lli_release_channel",
]
for k in core_config_keys:
    globals()[k] = os.getenv(k)

# Define and set additional variables that can be set in the env.
extended_config = {
    'APPIMAGE_LINK_SELECTION_NAME': 'selected_wine.AppImage',
    'APPDIR_BINDIR': None,
    'CHECK_UPDATES': False,
    'CONFIG_FILE': None,
    'CUSTOMBINPATH': None,
    'DEBUG': False,
    'DELETE_LOG': None,
    'DIALOG': None,
    'LOGOS_LOG': os.path.expanduser(f"~/.local/state/FaithLife-Community/{name_binary}.log"),  # noqa: E501
    'wine_log': os.path.expanduser("~/.local/state/FaithLife-Community/wine.log"),  # noqa: #E501
    'LOGOS_EXE': None,
    'LOGOS_EXECUTABLE': None,
    'LOGOS_VERSION': None,
    'LOGOS64_MSI': "Logos-x64.msi",
    'LOGOS64_URL': None,
    'REINSTALL_DEPENDENCIES': False,
    'SELECTED_APPIMAGE_FILENAME': None,
    'SKIP_DEPENDENCIES': False,
    'SKIP_FONTS': False,
    'SKIP_WINETRICKS': False,
    'use_python_dialog': None,
    'VERBOSE': False,
    'WINEBIN_CODE': None,
    'WINEDEBUG': "fixme-all,err-all",
    'WINEDLLOVERRIDES': '',
    'WINEPREFIX': None,
    'WINE_EXE': None,
    'WINESERVER_EXE': None,
    'WINETRICKS_UNATTENDED': None,
}
for key, default in extended_config.items():
    globals()[key] = os.getenv(key, default)

# Set other run-time variables not set in the env.
ACTION: str = 'app'
APPIMAGE_FILE_PATH: Optional[str] = None
authenticated = False # FIXME: no references
BADPACKAGES: Optional[str] = None # FIXME: no references
DEFAULT_CONFIG_PATH = os.path.expanduser(f"~/.config/FaithLife-Community/{name_binary}.json")  # noqa: E501
FLPRODUCTi: Optional[str] = None
GUI = None # FIXME: no references
INSTALL_STEP: int = 0
INSTALL_STEPS_COUNT: int = 0
L9PACKAGES = None
LEGACY_CONFIG_FILES = [
    os.path.expanduser("~/.config/FaithLife-Community/Logos_on_Linux.json"),  # noqa: E501
    os.path.expanduser("~/.config/Logos_on_Linux/Logos_on_Linux.conf")  # noqa: E501
]
LLI_AUTHOR = "Ferion11, John Goodman, T. H. Wright, N. Marti"
LLI_CURRENT_VERSION = "4.0.0-beta.2"
LLI_LATEST_VERSION: Optional[str] = None
LLI_TITLE = name_app
LOG_LEVEL = logging.WARNING
LOGOS_BLUE = '#0082FF'
LOGOS_GRAY = '#E7E7E7'
LOGOS_WHITE = '#FCFCFC'
# LOGOS_WHITE = '#F7F7F7'
LOGOS_DIR = os.path.dirname(LOGOS_EXE) if LOGOS_EXE else None  # noqa: F821
LOGOS_FORCE_ROOT: bool = False
LOGOS_ICON_FILENAME: Optional[str] = None
LOGOS_ICON_URL: Optional[str] = None
LOGOS_LATEST_VERSION_FILENAME = name_binary
LOGOS_LATEST_VERSION_URL: Optional[str] = None
LOGOS9_RELEASES = None      # used to save downloaded releases list # FIXME: not set #noqa: E501
LOGOS9_WINE64_BOTTLE_TARGZ_NAME = "wine64_bottle.tar.gz"
LOGOS9_WINE64_BOTTLE_TARGZ_URL = f"https://github.com/ferion11/wine64_bottle_dotnet/releases/download/v5.11b/{LOGOS9_WINE64_BOTTLE_TARGZ_NAME}"  # noqa: E501
LOGOS10_RELEASES = None     # used to save downloaded releases list # FIXME: not set #noqa: E501
MYDOWNLOADS: Optional[str] = None # FIXME: Should this use the tempfile module?
OS_NAME: Optional[str] = None
OS_RELEASE: Optional[str] = None
PACKAGE_MANAGER_COMMAND_INSTALL: Optional[list[str]] = None
PACKAGE_MANAGER_COMMAND_REMOVE: Optional[list[str]] = None
PACKAGE_MANAGER_COMMAND_QUERY: Optional[list[str]] = None
PACKAGES: Optional[str] = None
PASSIVE: Optional[bool] = None
pid_file = f'/tmp/{name_binary}.pid'
PRESENT_WORKING_DIRECTORY: str = os.getcwd()
QUERY_PREFIX: Optional[str] = None
REBOOT_REQUIRED: Optional[str] = None
RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME: Optional[str] = None
RECOMMENDED_WINE64_APPIMAGE_FULL_VERSION: Optional[str] = None
RECOMMENDED_WINE64_APPIMAGE_FILENAME: Optional[str] = None
RECOMMENDED_WINE64_APPIMAGE_VERSION: Optional[str] = None
RECOMMENDED_WINE64_APPIMAGE_BRANCH: Optional[str] = None
SUPERUSER_COMMAND: Optional[str] = None
VERBUM_PATH: Optional[str] = None
WINETRICKS_URL = "https://raw.githubusercontent.com/Winetricks/winetricks/5904ee355e37dff4a3ab37e1573c56cffe6ce223/src/winetricks"  # noqa: E501
WINETRICKS_VERSION = '20220411'
wine_user = None
WORKDIR = tempfile.mkdtemp(prefix="/tmp/LBS.")
install_finished = False
console_log = []
margin = 2
console_log_lines = 1
current_option = 0
current_page = 0
total_pages = 0
options_per_page = 8
resizing = False
processes = {}
threads = []
logos_login_cmd = None
logos_cef_cmd = None
logos_indexer_cmd = None
logos_indexer_exe = None
logos_linux_installer_status = None
logos_linux_installer_status_info = {
    0: "yes",
    1: "uptodate",
    2: "no",
    None: "config.LLI_CURRENT_VERSION or config.LLI_LATEST_VERSION is not set.",  # noqa: E501
}
check_if_indexing = None


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
    installdir = config_dict.get('INSTALLDIR')
    if installdir:
        global APPDIR_BINDIR
        APPDIR_BINDIR = f"{installdir}/data/bin"


def get_env_config():
    for var in globals().keys():
        val = os.getenv(var)
        if val is not None:
            logging.info(f"Setting '{var}' to '{val}'")
            globals()[var] = val


def get_timestamp():
    return datetime.today().strftime('%Y-%m-%dT%H%M%S')
