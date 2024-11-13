import abc
from dataclasses import dataclass
from datetime import datetime
import enum
import json
import logging
import os
from pathlib import Path
from typing import Optional

from ou_dedetai import config, network, utils, constants

# Strings for choosing a follow up file or directory
PROMPT_OPTION_DIRECTORY = "Choose Directory"
PROMPT_OPTION_FILE = "Choose File"

class App(abc.ABC):
    def __init__(self, **kwargs) -> None:
        self.conf = Config(self)

    def ask(self, question: str, options: list[str]) -> str:
        """Asks the user a question with a list of supplied options

        Returns the option the user picked.

        If the internal ask function returns None, the process will exit with an error code 1
        """
        if options is not None and self._exit_option is not None:
            options += [self._exit_option]
        answer = self._ask(question, options)
        if answer == self._exit_option:
            answer = None
        
        if answer is None:
            exit(1)

        return answer

    _exit_option: Optional[str] = "Exit"

    @abc.abstractmethod
    def _ask(self, question: str, options: list[str] = None) -> Optional[str]:
        """Implementation for asking a question pre-front end

        Options may include ability to prompt for an additional value.
        Implementations MUST handle the follow up prompt before returning

        If you would otherwise return None, consider shutting down cleanly,
        the calling function will exit the process with an error code of one
        if this function returns None
        """
        raise NotImplementedError()

    def _hook(self):
        """A hook for any changes the individual apps want to do when the config changes"""
        pass

    # XXX: unused at present
    @abc.abstractmethod
    def update_progress(self, message: str, percent: Optional[int] = None):
        """Updates the progress of the current operation"""
        pass


@dataclass
class LegacyConfiguration:
    """Configuration and it's keys from before the user configuration class existed.
    
    Useful for one directional compatibility"""
    FLPRODUCT: Optional[str] = None
    TARGETVERSION: Optional[str] = None
    TARGET_RELEASE_VERSION: Optional[str] = None
    current_logos_version: Optional[str] = None
    curses_colors: Optional[str] = None
    INSTALLDIR: Optional[str] = None
    WINETRICKSBIN: Optional[str] = None
    WINEBIN_CODE: Optional[str] = None
    WINE_EXE: Optional[str] = None
    WINECMD_ENCODING: Optional[str] = None
    LOGS: Optional[str] = None
    BACKUPDIR: Optional[str] = None
    LAST_UPDATED: Optional[str] = None
    RECOMMENDED_WINE64_APPIMAGE_URL: Optional[str] = None
    LLI_LATEST_VERSION: Optional[str] = None
    logos_release_channel: Optional[str] = None
    lli_release_channel: Optional[str] = None

    @classmethod
    def config_file_path() -> str:
        return os.getenv(constants.CONFIG_FILE_ENV) or constants.DEFAULT_CONFIG_PATH
    
    @classmethod
    def from_file_and_env() -> "LegacyConfiguration":
        config_file_path = LegacyConfiguration.config_file_path()
        config_dict = LegacyConfiguration()
        if config_file_path.endswith('.json'):
            try:
                with open(config_file_path, 'r') as config_file:
                    cfg = json.load(config_file)

                for key, value in cfg.items():
                    config_dict[key] = value
            except TypeError as e:
                logging.error("Error opening Config file.")
                logging.error(e)
                raise e
            except FileNotFoundError:
                logging.info(f"No config file not found at {config_file_path}")
            except json.JSONDecodeError as e:
                logging.error("Config file could not be read.")
                logging.error(e)
                raise e
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

        # Now update from ENV
        for var in LegacyConfiguration().__dict__.keys():
            if os.getenv(var) is not None:
                config_dict[var] = os.getenv(var)

        return config_dict


@dataclass
class UserConfiguration:
    """This is the class that actually stores the values.

    Normally shouldn't be used directly, as it's types may be None
    
    Easy reading to/from JSON and supports legacy keys"""
    faithlife_product: Optional[str] = None
    faithlife_product_version: Optional[str] = None
    faithlife_product_release: Optional[str] = None
    install_dir: Optional[Path] = None
    winetricks_binary: Optional[Path] = None
    wine_binary: Optional[Path] = None
    # This is where to search for wine
    wine_binary_code: Optional[str] = None
    backup_directory: Optional[Path] = None

    # Color to use in curses. Either "Logos", "Light", or "Dark"
    curses_colors: str = "Logos"
    # Faithlife's release channel. Either "stable" or "beta"
    faithlife_product_release_channel: str = "stable"
    # The Installer's release channel. Either "stable" or "beta"
    installer_release_channel: str = "stable"

    @classmethod
    def read_from_file_and_env() -> "UserConfiguration":
        # First read in the legacy configuration
        new_config = UserConfiguration.from_legacy(LegacyConfiguration.from_file_and_env())
        # Then read the file again this time looking for the new keys
        config_file_path = LegacyConfiguration.config_file_path()

        new_keys = UserConfiguration().__dict__.keys()

        if config_file_path.endswith('.json'):
            with open(config_file_path, 'r') as config_file:
                cfg = json.load(config_file)

            for key, value in cfg.items():
                if key in new_keys:
                    new_config[key] = value
        else:
            logging.info("Not reading new values from non-json config")

        return new_config

    @classmethod
    def from_legacy(legacy: LegacyConfiguration) -> "UserConfiguration":
        return UserConfiguration(
            faithlife_product=legacy.FLPRODUCT,
            backup_directory=legacy.BACKUPDIR,
            curses_colors=legacy.curses_colors,
            faithlife_product_release=legacy.TARGET_RELEASE_VERSION,
            faithlife_product_release_channel=legacy.logos_release_channel,
            faithlife_product_version=legacy.TARGETVERSION,
            install_dir=legacy.INSTALLDIR,
            installer_release_channel=legacy.lli_release_channel,
            wine_binary=legacy.WINE_EXE,
            wine_binary_code=legacy.WINEBIN_CODE,
            winetricks_binary=legacy.WINETRICKSBIN
        )
    
    def write_config(self):
        config_file_path = LegacyConfiguration.config_file_path()
        with open(config_file_path, 'w') as config_file:
            json.dump(self.__dict__, config_file)

# XXX: what to do with these?
# Used to be called current_logos_version, but actually could be used in Verbium too.
installed_faithlife_product_release: Optional[str] = None
# Whether or not the installed faithlife product is configured for additional logging.
# Used to be called "LOGS"
installed_faithlife_logging: Optional[bool] = None
# Text encoding of the wine command. This calue can be retrieved from the system
winecmd_encoding: Optional[str] = None
last_updated: Optional[datetime] = None
recommended_wine_url: Optional[str] = None
latest_installer_version: Optional[str] = None


class Config:
    """Set of configuration values. 
    
    If the user hasn't selected a particular value yet, they will be prompted in their UI."""

    # Storage for the keys
    user: UserConfiguration

    def __init__(self, app: App) -> None:
        self.app = app
        self.user = UserConfiguration.read_from_file_and_env()
        logging.debug("Current persistent config:")
        for k, v in self.user.__dict__.items():
            logging.debug(f"{k}: {v}")
    
    def _ask_if_not_found(self, config_key: str, question: str, options: list[str], dependent_config_keys: Optional[list[str]] = None) -> str:
        # XXX: should this also update the feedback?
        if not getattr(config, config_key):
            if dependent_config_keys is not None:
                for dependent_config_key in dependent_config_keys:
                    setattr(config, dependent_config_key, None)
            setattr(config, config_key, self.app.ask(question, options))
            self.app._hook()
            # And update the file so it's always up to date.
            self.user.write_config()
        return getattr(config, config_key)

    @property
    def faithlife_product(self) -> str:
        question = "Choose which FaithLife product the script should install: "  # noqa: E501
        options = ["Logos", "Verbum"]
        return self._ask_if_not_found("FLPRODUCT", question, options, ["TARGETVERSION", "TARGET_RELEASE_VERSION"])
    
    @property
    def faithlife_product_version(self) -> str:
        question = f"Which version of {self.faithlife_product} should the script install?: ",  # noqa: E501
        options = ["10", "9"]
        return self._ask_if_not_found("FLPRODUCT", question, options, ["TARGET_RELEASE_VERSION"])

    @property
    def faithlife_product_release(self) -> str:
        question = f"Which version of {self.faithlife_product} {self.faithlife_product_version} do you want to install?: ",  # noqa: E501
        options = network.get_logos_releases(None)
        return self._ask_if_not_found("TARGET_RELEASE_VERSION", question, options)

    # FIXME: should this just ensure that winetricks is installed and in the right location? That isn't really a matter for a config...
    @property
    def winetricks_binary(self) -> str:
        question = f"Should the script use the system's local winetricks or download the latest winetricks from the Internet? The script needs to set some Wine options that {self.faithlife_product} requires on Linux.",  # noqa: E501
        options = utils.get_winetricks_options()
        return self._ask_if_not_found("WINETRICKSBIN", question, options)
    
    @property
    def install_dir(self) -> str:
        default = f"{str(Path.home())}/{self.faithlife_product}Bible{self.faithlife_product_version}"  # noqa: E501
        question = f"Where should {self.faithlife_product} files be installed to?: "  # noqa: E501
        options = [default, PROMPT_OPTION_DIRECTORY]
        output = self._ask_if_not_found("INSTALLDIR", question, options)
        # XXX: Why is this stored separately if it's always at this relative path? Shouldn't this relative string be a constant?
        config.APPDIR_BINDIR = f"{output}/data/bin"
        return output

    @property
    def wine_binary(self) -> str:
        if not config.WINE_EXE:
            question = f"Which Wine AppImage or binary should the script use to install {self.faithlife_product} v{self.faithlife_product_version} in {self.install_dir}?: ",  # noqa: E501
            network.set_recommended_appimage_config()
            options = utils.get_wine_options(
                utils.find_appimage_files(config.TARGET_RELEASE_VERSION),
                utils.find_wine_binary_files(config.TARGET_RELEASE_VERSION)
            )

            choice = self.app.ask(question, options)

            # Make the possibly relative path absolute before storing
            config.WINE_EXE = utils.get_relative_path(
                utils.get_config_var(choice),
                self.install_dir
            )
            self.app._hook()
        return config.WINE_EXE
    
    