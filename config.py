import json
import logging
import os
import tempfile

# Config file variables to preserve post-install.
APPDIR = os.getenv('APPDIR')
APPDIR_BINDIR = os.getenv('APPDIR_BINDIR')
APPIMAGE_LINK_SELECTION_NAME = os.getenv('APPIMAGE_LINK_SELECTION_NAME')
BACKUPDIR = os.getenv('BACKUPDIR')
FLPRODUCT = os.getenv('FLPRODUCT')
FLPRODUCTi = os.getenv('FLPRODUCTi')
INSTALLDIR = os.getenv('INSTALLDIR')
LOGOS_EXE = os.getenv('LOGOS_EXE')
LOGOS_DIR = os.path.dirname(LOGOS_EXE) if LOGOS_EXE is not None else None
LOGOS_EXECUTABLE = os.getenv('LOGOS_EXECUTABLE')
LOGS = os.getenv('LOGS')
SKIP_FONTS = os.getenv('SKIP_FONTS', False)
TARGETVERSION = os.getenv('TARGETVERSION')
WINE_EXE = os.getenv('WINE_EXE')
WINE64_APPIMAGE_FULL_URL = os.getenv('WINE64_APPIMAGE_FULL_URL', "https://github.com/ferion11/LogosLinuxInstaller/releases/download/wine-devel-8.19/wine-devel_8.19-x86_64.AppImage")
WINE64_APPIMAGE_FULL_FILENAME = os.path.basename(WINE64_APPIMAGE_FULL_URL)
WINEBIN_CODE = os.getenv('WINEBIN_CODE')
WINEPREFIX = os.getenv('WINEPREFIX')
WINESERVER_EXE = os.getenv('WINESERVER_EXE')
WINETRICKSBIN = os.getenv('WINETRICKSBIN')

# Variables that can be set in the environment.
CONFIG_FILE = os.getenv('CONFIG_FILE')
CUSTOMBINPATH = os.getenv('CUSTOMBINPATH')
DEBUG = os.getenv('DEBUG', False)
DELETE_INSTALL_LOG = os.getenv('DELETE_INSTALL_LOG', False)
DIALOG = os.getenv('DIALOG')
LOGOS_LOG = os.getenv('LOGOS_LOG', os.path.expanduser("~/.local/state/Logos_on_Linux/install.log"))
LOGOS_VERSION = os.getenv('LOGOS_VERSION')
LOGOS64_MSI = os.getenv('LOGOS64_MSI')
LOGOS64_URL = os.getenv('LOGOS64_URL')
REINSTALL_DEPENDENCIES = os.getenv('REINSTALL_DEPENDENCIES', False)
SKEL = os.getenv('SKEL')
VERBOSE = os.getenv('VERBOSE', False)
WINEDEBUG = os.getenv('WINEDEBUG', "fixme-all,err-all")
WINEDLLOVERRIDES = os.getenv('WINEDLLOVERRIDES', '')
WINETRICKS_UNATTENDED = os.getenv('WINETRICKS_UNATTENDED')

# Other run-time variables.
ACTION = 'app'
APPIMAGE_LINK_SELECTION_NAME = "selected_wine.AppImage"
DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/Logos_on_Linux/Logos_on_Linux.conf")
EXTRA_INFO = "The following packages are usually necessary: winbind cabextract libjpeg8."
GUI = None
LOGOS_FORCE_ROOT = False
LOGOS_ICON_FILENAME = None
LOGOS_ICON_URL = None
LOGOS_RELEASE_VERSION = None
LOGOS_SCRIPT_TITLE = "Logos Linux Installer"
LOGOS_SCRIPT_AUTHOR = "Ferion11, John Goodman, T. H. Wright"
LOGOS_SCRIPT_VERSION = "4.0.0"
MYDOWNLOADS = None
PASSIVE = None
PRESENT_WORKING_DIRECTORY = os.getcwd()
LOG_LEVEL = logging.WARNING
VERBUM_PATH = None
WINE64_APPIMAGE_FILENAME = os.path.basename(WINE64_APPIMAGE_FULL_URL).split(".AppImage")[0]
WINE64_APPIMAGE_FULL_VERSION = "v8.19-devel"
WINE64_APPIMAGE_URL = WINE64_APPIMAGE_FULL_URL
WINE64_APPIMAGE_VERSION = WINE64_APPIMAGE_FULL_VERSION
WINE64_BOTTLE_TARGZ_NAME = "wine64_bottle.tar.gz"
WINE64_BOTTLE_TARGZ_URL = f"https://github.com/ferion11/wine64_bottle_dotnet/releases/download/v5.11b/{WINE64_BOTTLE_TARGZ_NAME}"
WINETRICKS_DOWNLOADER = "wget"
WINETRICKS_URL = "https://raw.githubusercontent.com/Winetricks/winetricks/5904ee355e37dff4a3ab37e1573c56cffe6ce223/src/winetricks"
WORKDIR = tempfile.mkdtemp(prefix="/tmp/LBS.")

OS_NAME = None
OS_RELEASE = None
PACKAGE_MANAGER_COMMAND = None
PACKAGES = None
SUPERUSER_COMMAND = None


def get_config_file_dict(config_file_path):
    config_dict = {}
    try:
        with open(config_file_path, 'r') as config_file:
            cfg = json.load(config_file)

        for key, value in cfg.items():
            config_dict[key] = value
        return config_dict
    except TypeError as e:
        logging.error(f"Error opening Config file: {e}")
        return None
    except FileNotFoundError:
        # Most likely a new install with no saved config file yet.
        logging.info(f"No config file not found at {config_file_path}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding config file {config_file_path}: {e}")
        return None

def set_config_env(config_file_path):
    config_dict = get_config_file_dict(config_file_path)
    if config_dict is None:
        logos_error(f"Error: Unable to get config at {config_file_path}")
    for key, value in config_dict.items():
        globals()[key] = value
