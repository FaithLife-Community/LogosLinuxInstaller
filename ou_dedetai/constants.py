import logging
import os

# Define app name variables.
APP_NAME = 'Ou Dedetai'
BINARY_NAME = 'oudedetai'
PACKAGE_NAME = 'ou_dedetai'
REPOSITORY_LINK = "https://github.com/FaithLife-Community/LogosLinuxInstaller"

# Set other run-time variables not set in the env.
DEFAULT_CONFIG_PATH = os.path.expanduser(f"~/.config/FaithLife-Community/{BINARY_NAME}.json")  # noqa: E501
DEFAULT_APP_WINE_LOG_PATH= os.path.expanduser("~/.local/state/FaithLife-Community/wine.log")  # noqa: E501
DEFAULT_APP_LOG_PATH= os.path.expanduser(f"~/.local/state/FaithLife-Community/{BINARY_NAME}.log")  # noqa: E501
DEFAULT_WINEDEBUG = "fixme-all,err-all"
LEGACY_CONFIG_FILES = [
    os.path.expanduser("~/.config/FaithLife-Community/Logos_on_Linux.json"),  # noqa: E501
    os.path.expanduser("~/.config/Logos_on_Linux/Logos_on_Linux.conf")  # noqa: E501
]
LLI_AUTHOR = "Ferion11, John Goodman, T. H. Wright, N. Marti"
LLI_CURRENT_VERSION = "4.0.0-beta.4"
DEFAULT_LOG_LEVEL = logging.WARNING
LOGOS_BLUE = '#0082FF'
LOGOS_GRAY = '#E7E7E7'
LOGOS_WHITE = '#FCFCFC'
LOGOS9_WINE64_BOTTLE_TARGZ_NAME = "wine64_bottle.tar.gz"
LOGOS9_WINE64_BOTTLE_TARGZ_URL = f"https://github.com/ferion11/wine64_bottle_dotnet/releases/download/v5.11b/{LOGOS9_WINE64_BOTTLE_TARGZ_NAME}"  # noqa: E501
PID_FILE = f'/tmp/{BINARY_NAME}.pid'
WINETRICKS_VERSION = '20220411'

# Strings for choosing a follow up file or directory
PROMPT_OPTION_DIRECTORY = "Choose Directory"
PROMPT_OPTION_FILE = "Choose File"

# String for when a binary is meant to be downloaded later
DOWNLOAD = "Download"
