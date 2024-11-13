import logging
import os

# Define app name variables.
APP_NAME = 'Ou Dedetai'
BINARY_NAME = 'oudedetai'
PACKAGE_NAME = 'ou_dedetai'
REPOSITORY_LINK = "https://github.com/FaithLife-Community/LogosLinuxInstaller"

# Set other run-time variables not set in the env.
DEFAULT_CONFIG_PATH = os.path.expanduser(f"~/.config/FaithLife-Community/{BINARY_NAME}.json")  # noqa: E501
CONFIG_FILE_ENV = "CONFIG_PATH"
LEGACY_CONFIG_FILES = [
    os.path.expanduser("~/.config/FaithLife-Community/Logos_on_Linux.json"),  # noqa: E501
    os.path.expanduser("~/.config/Logos_on_Linux/Logos_on_Linux.conf")  # noqa: E501
]
LLI_AUTHOR = "Ferion11, John Goodman, T. H. Wright, N. Marti"
LLI_CURRENT_VERSION = "4.0.0-beta.4"
LOG_LEVEL = logging.WARNING
LOGOS_BLUE = '#0082FF'
LOGOS_GRAY = '#E7E7E7'
LOGOS_WHITE = '#FCFCFC'
LOGOS9_WINE64_BOTTLE_TARGZ_NAME = "wine64_bottle.tar.gz"
LOGOS9_WINE64_BOTTLE_TARGZ_URL = f"https://github.com/ferion11/wine64_bottle_dotnet/releases/download/v5.11b/{LOGOS9_WINE64_BOTTLE_TARGZ_NAME}"  # noqa: E501
PID_FILE = f'/tmp/{BINARY_NAME}.pid'
WINETRICKS_VERSION = '20220411'
