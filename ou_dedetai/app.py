import abc
from dataclasses import dataclass
from datetime import datetime
import json
import logging
import os
from pathlib import Path
from typing import Optional

from ou_dedetai import msg, network, utils, constants

# Strings for choosing a follow up file or directory
PROMPT_OPTION_DIRECTORY = "Choose Directory"
PROMPT_OPTION_FILE = "Choose File"

# String for when a binary is meant to be downloaded later
DOWNLOAD = "Download"

class App(abc.ABC):
    def __init__(self, **kwargs) -> None:
        self.conf = Config(self)

    def ask(self, question: str, options: list[str]) -> str:
        """Asks the user a question with a list of supplied options

        Returns the option the user picked.

        If the internal ask function returns None, the process will exit with an error code 1
        """
        if len(options) == 1 and (PROMPT_OPTION_DIRECTORY in options or PROMPT_OPTION_FILE in options):
            # Set the only option to be the follow up prompt
            options = options[0]
        elif options is not None and self._exit_option is not None:
            options += [self._exit_option]
        answer = self._ask(question, options)
        if answer == self._exit_option:
            answer = None
        
        if answer is None:
            exit(1)

        return answer

    _exit_option: Optional[str] = "Exit"

    @abc.abstractmethod
    def _ask(self, question: str, options: list[str] | str) -> Optional[str]:
        """Implementation for asking a question pre-front end

        Options may include ability to prompt for an additional value.
        Implementations MUST handle the follow up prompt before returning

        Options may be a single value,
        Implementations MUST handle this single option being a follow up prompt

        If you would otherwise return None, consider shutting down cleanly,
        the calling function will exit the process with an error code of one
        if this function returns None
        """
        raise NotImplementedError()

    def _config_updated(self):
        """A hook for any changes the individual apps want to do when the config changes"""
        pass

    # XXX: unused at present
    @abc.abstractmethod
    def update_progress(self, message: str, percent: Optional[int] = None):
        """Updates the progress of the current operation"""
        pass

# XXX: What about legacy envs? From the extended config?
# Like APPDIR_BINDIR? This no longer can be modified directly, unless we store an override.

@dataclass
class LegacyEnvOverrides:
    """Previous versions of the installer allowed some values to be overridden by environment.
    This keeps that compatibility."""
    APPIMAGE_LINK_SELECTION_NAME: Optional[str]
    APPDIR_BINDIR: Optional[str]
    CHECK_UPDATES: Optional[bool]
    CONFIG_FILE: Optional[str]
    CUSTOMBINPATH: Optional[str]
    DEBUG: Optional[bool]
    DELETE_LOG: Optional[str]
    DIALOG: Optional[str]
    # XXX: default used to be `os.path.expanduser(f"~/.local/state/FaithLife-Community/{constants.BINARY_NAME}.log")`
    LOGOS_LOG: Optional[str]
    # XXX: default used to be `os.path.expanduser("~/.local/state/FaithLife-Community/wine.log")`
    wine_log: Optional[str]
    LOGOS_EXE: Optional[str]
    # This is the logos installer executable name (NOT path)
    LOGOS_EXECUTABLE: Optional[str]
    LOGOS_VERSION: Optional[str]
    # This wasn't overridable in the bash version of this installer (at 554c9a6),
    # nor was it used in the python version (at 8926435)
    # LOGOS64_MSI: Optional[str]
    LOGOS64_URL: Optional[str]
    REINSTALL_DEPENDENCIES: Optional[bool]
    SELECTED_APPIMAGE_FILENAME: Optional[str]
    SKIP_DEPENDENCIES: Optional[bool]
    SKIP_FONTS: Optional[bool]
    SKIP_WINETRICKS: Optional[bool]
    use_python_dialog: Optional[str]
    VERBOSE: Optional[bool]
    WINEBIN_CODE: Optional[str]
    # XXX: move this out of this struct
    WINEDEBUG: Optional[str] = "fixme-all,err-all",
    WINEDLLOVERRIDES: Optional[str]
    WINEPREFIX: Optional[str]
    WINE_EXE: Optional[str]
    WINESERVER_EXE: Optional[str]
    WINETRICKS_UNATTENDED: Optional[str]

    @classmethod
    def from_env() -> "LegacyEnvOverrides":
        legacy_envs = LegacyEnvOverrides()
        for var in LegacyEnvOverrides().__dict__.keys():
            if os.getenv(var) is not None:
                # XXX: this doesn't load bools properly. Use get_type_hints to fid this.
                legacy_envs[var] = os.getenv(var)
        return legacy_envs


# XXX: move these configs into config.py once it's cleared out
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
class EnvironmentOverrides:
    """Allows some values to be overridden from environment.
    
    The actually name of the environment variables remains unchanged from before,
    this translates the environment variable names to the new variable names"""

    installer_binary_directory: Optional[str]
    wineserver_binary: Optional[str]
    faithlife_product_version: Optional[str]
    faithlife_installer_name: Optional[str]
    faithlife_installer_download_url: Optional[str]

    winetricks_skip: Optional[bool]

    wine_dll_overrides: Optional[str]

    # Additional path to look for when searching for binaries.
    # FIXME: consider using PATH instead? (and storing this legacy env in PATH for this process)
    custom_binary_path: Optional[str]

    @classmethod
    def from_legacy(legacy: LegacyEnvOverrides) -> "EnvironmentOverrides":
        EnvironmentOverrides(
            installer_binary_directory=legacy.APPDIR_BINDIR,
            wineserver_binary=legacy.WINESERVER_EXE,
            custom_binary_path=legacy.CUSTOMBINPATH,
            faithlife_product_version=legacy.LOGOS_VERSION,
            faithlife_installer_name=legacy.LOGOS_EXECUTABLE,
            faithlife_installer_download_url=legacy.LOGOS64_URL,
            winetricks_skip=legacy.SKIP_WINETRICKS
        )

    @classmethod
    def from_env() -> "EnvironmentOverrides":
        return EnvironmentOverrides.from_legacy(LegacyEnvOverrides.from_env())


@dataclass
class UserConfiguration:
    """This is the class that actually stores the values.

    Normally shouldn't be used directly, as it's types may be None
    
    Easy reading to/from JSON and supports legacy keys"""

    # XXX: store a version in this config? Just in case we need to do conditional logic reading old version's configurations

    faithlife_product: Optional[str] = None
    faithlife_product_version: Optional[str] = None
    faithlife_product_release: Optional[str] = None
    install_dir: Optional[Path] = None
    winetricks_binary: Optional[str] = None
    wine_binary: Optional[str] = None
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
        new_config: UserConfiguration = UserConfiguration.from_legacy(LegacyConfiguration.from_file_and_env())
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
        output = self.__dict__

        logging.info(f"Writing config to {config_file_path}")
        os.makedirs(os.path.dirname(config_file_path), exist_ok=True)

        # Ensure all paths stored are relative to install_dir
        for k, v in output.items():
            # XXX: test this
            if isinstance(v, Path) or (isinstance(v, str) and v.startswith(self.install_dir)):
                output[k] = utils.get_relative_path(v, self.install_dir)

        try:
            with open(config_file_path, 'w') as config_file:
                json.dump(output, config_file, indent=4, sort_keys=True)
                config_file.write('\n')
        except IOError as e:
            msg.logos_error(f"Error writing to config file {config_file_path}: {e}")  # noqa: E501
            # Continue, the installer can still operate even if it fails to write.


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
    _raw: UserConfiguration

    # Overriding programmatically generated values from ENV
    _overrides: EnvironmentOverrides
    
    _curses_colors_valid_values = ["Light", "Dark", "Logos"]

    # Singleton logic, this enforces that only one config object exists at a time.
    def __new__(cls) -> "Config":
        if not hasattr(cls, '_instance'):
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self, app: App) -> None:
        self.app = app
        self._raw = UserConfiguration.read_from_file_and_env()
        logging.debug("Current persistent config:")
        for k, v in self._raw.__dict__.items():
            logging.debug(f"{k}: {v}")
    
    def _ask_if_not_found(self, parameter: str, question: str, options: list[str], dependent_parameters: Optional[list[str]] = None) -> str:
        # XXX: should this also update the feedback?
        if not getattr(self._raw, parameter):
            if dependent_parameters is not None:
                for dependent_config_key in dependent_parameters:
                    setattr(self._raw, dependent_config_key, None)
            answer = self.app.ask(question, options)
            # Use the setter on this class if found, otherwise set in self._user
            if getattr(Config, parameter) and getattr(Config, parameter).fset is not None:
                getattr(Config, parameter).fset(self, answer)
            else:
                setattr(self._raw, parameter, answer)
                self._write()
        return getattr(self._raw, parameter)

    def _write(self):
        """Writes configuration to file and lets the app know something changed"""
        self._raw.write_config()
        self.app._config_updated()

    @property
    def config_file_path(self) -> str:
        return LegacyConfiguration.config_file_path()

    @property
    def faithlife_product(self) -> str:
        question = "Choose which FaithLife product the script should install: "  # noqa: E501
        options = ["Logos", "Verbum"]
        return self._ask_if_not_found("faithlife_product", question, options, ["faithlife_product_version", "faithlife_product_release"])

    @faithlife_product.setter
    def faithlife_product(self, value: Optional[str]):
        if self._raw.faithlife_product != value:
            self._raw.faithlife_product = value
            # Reset dependent variables
            self.faithlife_product_release = None

            self._write()

    @property
    def faithlife_product_version(self) -> str:
        if self._overrides.faithlife_product_version is not None:
            return self._overrides.faithlife_product_version
        question = f"Which version of {self.faithlife_product} should the script install?: ",  # noqa: E501
        options = ["10", "9"]
        return self._ask_if_not_found("faithlife_product_version", question, options, ["faithlife_product_version"])

    @faithlife_product_version.setter
    def faithlife_product_version(self, value: Optional[str]):
        if self._raw.faithlife_product_version != value:
            self._raw.faithlife_product_release = None
            # Install Dir has the name of the product and it's version. Reset it too
            self._raw.install_dir = None
            # Wine is dependent on the product/version selected
            self._raw.wine_binary = None
            self._raw.wine_binary_code = None
            self._raw.winetricks_binary = None

            self._write()

    @property
    def faithlife_product_release(self) -> str:
        question = f"Which version of {self.faithlife_product} {self.faithlife_product_version} do you want to install?: ",  # noqa: E501
        options = network.get_logos_releases(None)
        return self._ask_if_not_found("faithlife_product_release", question, options)

    @faithlife_product_release.setter
    def faithlife_product_release(self, value: str):
        if self._raw.faithlife_product_release != value:
            self._raw.faithlife_product_release = value
            self._write()

    @property
    def faithlife_installer_name(self) -> str:
        if self._overrides.faithlife_installer_name is not None:
            return self._overrides.faithlife_installer_name
        return f"{self.faithlife_product}_v{self.faithlife_product_version}-x64.msi"

    @property
    def faithlife_installer_download_url(self) -> str:
        if self._overrides.faithlife_installer_download_url is not None:
            return self._overrides.faithlife_installer_download_url
        after_version_url_part = "/Verbum/" if self.faithlife_product == "Verbum" else "/"
        return f"https://downloads.logoscdn.com/LBS{self.faithlife_product_version}{after_version_url_part}Installer/{self.faithlife_product_release}/{self.faithlife_product}-x64.msi"  # noqa: E501

    @property
    def faithlife_product_release_channel(self) -> str:
        return self._raw.faithlife_product_release_channel

    @property
    def installer_release_channel(self) -> str:
        return self._raw.installer_release_channel

    @property
    def winetricks_binary(self) -> str:
        """This may be a path to the winetricks binary or it may be "Download"
        """
        question = f"Should the script use the system's local winetricks or download the latest winetricks from the Internet? The script needs to set some Wine options that {self.faithlife_product} requires on Linux.",  # noqa: E501
        options = utils.get_winetricks_options()
        return self._ask_if_not_found("winetricks_binary", question, options)
    
    @winetricks_binary.setter
    def winetricks_binary(self, value: Optional[str | Path]):
        if value is not None and value != "Download":
            value = Path(value)
            if not value.exists():
                raise ValueError("Winetricks binary must exist")
        if self._raw.winetricks_binary != value:
            self._raw.winetricks_binary = value
            self._write()

    @property
    def install_dir(self) -> str:
        default = f"{str(Path.home())}/{self.faithlife_product}Bible{self.faithlife_product_version}"  # noqa: E501
        question = f"Where should {self.faithlife_product} files be installed to?: "  # noqa: E501
        options = [default, PROMPT_OPTION_DIRECTORY]
        output = self._ask_if_not_found("install_dir", question, options)
        return output

    @property
    # This used to be called APPDIR_BINDIR
    def installer_binary_directory(self) -> str:
        if self._overrides.installer_binary_directory is not None:
            return self._overrides.installer_binary_directory
        return f"{self.install_dir}/data/bin"

    @property
    # XXX: used to be called WINEPREFIX
    def wine_prefix(self) -> str:
        return f"{self.install_dir}/data/wine64_bottle"

    @property
    def wine_binary(self) -> str:
        """Returns absolute path to the wine binary"""
        if not self._raw.wine_binary:
            question = f"Which Wine AppImage or binary should the script use to install {self.faithlife_product} v{self.faithlife_product_version} in {self.install_dir}?: ",  # noqa: E501
            network.set_recommended_appimage_config()
            options = utils.get_wine_options(
                self,
                utils.find_appimage_files(self.faithlife_product_release),
                utils.find_wine_binary_files(self.app, self.faithlife_product_release)
            )

            choice = self.app.ask(question, options)

            self.wine_binary = choice
        # Return the full path so we the callee doesn't need to think about it
        if not Path(self._raw.wine_binary).exists() and (Path(self.install_dir) / self._raw.wine_binary).exists():
            return str(Path(self.install_dir) / self._raw.wine_binary)
        return self._raw.wine_binary

    @wine_binary.setter
    def wine_binary(self, value: str):
        if (Path(self.install_dir) / value).exists():
            value = (Path(self.install_dir) / value).absolute()
        if not Path(value).is_file():
            raise ValueError("Wine Binary path must be a valid file")

        if self._raw.wine_binary != value:
            if value is not None:
                value = Path(value).absolute()
            self._raw.wine_binary = value
            # Reset dependents
            self._raw.wine_binary_code = None
            self._write()

    @property
    def wine64_binary(self) -> str:
        return str(Path(self.wine_binary).parent / 'wine64')
    
    @property
    # This used to be called WINESERVER_EXE
    def wineserver_binary(self) -> str:
        return str(Path(self.wine_binary).parent / 'wineserver')

    @property
    def wine_dll_overrides(self) -> str:
        if self._overrides.wine_dll_overrides is not None:
            return self._overrides.wine_dll_overrides
        # Default is no overrides
        return ''

    def toggle_faithlife_product_release_channel(self):
        if self._raw.faithlife_product_release_channel == "stable":
            new_channel = "beta"
        else:
            new_channel = "stable"
        self._raw.faithlife_product_release_channel = new_channel
        self._write()
    
    def toggle_installer_release_channel(self):
        if self._raw.installer_release_channel == "stable":
            new_channel = "dev"
        else:
            new_channel = "stable"
        self._raw.installer_release_channel = new_channel
        self._write()
    
    @property
    def backup_directory(self) -> Path:
        question = "New or existing folder to store backups in: "
        options = [PROMPT_OPTION_DIRECTORY]
        output = Path(self._ask_if_not_found("backup_directory", question, options))
        output.mkdir(parents=True)
        return output
    
    @property
    def curses_colors(self) -> str:
        """Color for the curses dialog
        
        returns one of: Logos, Light or Dark"""
        return self._raw.curses_colors

    @curses_colors.setter
    def curses_colors(self, value: str):
        if value not in self._curses_colors_valid_values:
            raise ValueError(f"Invalid curses theme, expected one of: {", ".join(self._curses_colors_valid_values)} but got: {value}")
        self._raw.curses_colors = value
        self._write()
    
    def cycle_curses_color_scheme(self):
        new_index = self._curses_colors_valid_values.index(self.curses_colors) + 1
        if new_index == len(self._curses_colors_valid_values):
            new_index = 0
        self.curses_colors = self._curses_colors_valid_values[new_index]

    @property
    def logos_exe(self) -> Optional[str]:
        # XXX: consider caching this value? This is a directory walk, and it's called by a wine user and logos_*_exe 
        return utils.find_installed_product(self.faithlife_product, self.wine_prefix)

    @property
    def wine_user(self) -> Optional[str]:
        path: Optional[str] = self.logos_exe
        if path is None:
            return None
        normalized_path: str = os.path.normpath(path)
        path_parts = normalized_path.split(os.sep)
        return path_parts[path_parts.index('users') + 1]

    @property
    def logos_cef_exe(self) -> Optional[str]:
        if self.wine_user is not None:
            return f'C:\\users\\{self.wine_user}\\AppData\\Local\\Logos\\System\\LogosCEF.exe'  # noqa: E501

    @property
    def logos_indexer_exe(self) -> Optional[str]:
        if self.wine_user is not None:
            return f'C:\\users\\{self.wine_user}\\AppData\\Local\\Logos\\System\\LogosIndexer.exe'  # noqa: E501

    @property
    def logos_login_exe(self) -> Optional[str]:
        if self.wine_user is not None:
            return f'C:\\users\\{self.wine_user}\\AppData\\Local\\Logos\\System\\Logos.exe'  # noqa: E501

    @property
    def skip_winetricks(self) -> bool:
        if self._overrides.winetricks_skip is not None:
            return self._overrides.winetricks_skip
        return False