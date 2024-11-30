import json
import logging
import os
import tempfile
from typing import Optional

from . import constants

# Define and set variables that are required in the config file.
# XXX: slowly kill these
current_logos_version = None
LOGS = None
LAST_UPDATED = None
LLI_LATEST_VERSION = None
lli_release_channel = None

# Define and set additional variables that can be set in the env.
extended_config = {
    'CONFIG_FILE': None,
    'DIALOG': None,
    # Dependent on DIALOG with env override
    'use_python_dialog': None,
}
for key, default in extended_config.items():
    globals()[key] = os.getenv(key, default)

# Set other run-time variables not set in the env.
ACTION: str = 'app'
LOGOS_LATEST_VERSION_FILENAME = constants.APP_NAME
LOGOS_LATEST_VERSION_URL: Optional[str] = None
SUPERUSER_COMMAND: Optional[str] = None
wine_user = None
WORKDIR = tempfile.mkdtemp(prefix="/tmp/LBS.")
console_log = []
processes = {}
threads = []
logos_linux_installer_status = None
logos_linux_installer_status_info = {
    0: "yes",
    1: "uptodate",
    2: "no",
    None: "constants.LLI_CURRENT_VERSION or config.LLI_LATEST_VERSION is not set.",  # noqa: E501
}
check_if_indexing = None


# XXX: remove this
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


# XXX: remove this
def set_config_env(config_file_path):
    config_dict = get_config_file_dict(config_file_path)
    if config_dict is None:
        return
        # msg.logos_error(f"Error: Unable to get config at {config_file_path}")
    logging.info(f"Setting {len(config_dict)} variables from config file.")
    for key, value in config_dict.items():
        globals()[key] = value

# XXX: remove this
def get_env_config():
    for var in globals().keys():
        val = os.getenv(var)
        if val is not None:
            logging.info(f"Setting '{var}' to '{val}'")
            globals()[var] = val

