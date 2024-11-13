import abc
from pathlib import Path
from typing import Optional

from ou_dedetai import config, network, utils
from ou_dedetai.installer import update_install_feedback


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

class Config:
    """Set of configuration values. 
    
    If the user hasn't selected a particular value yet, they will be prompted in their UI."""

    def __init__(self, app: App) -> None:
        self.app = app
    
    def _ask_if_not_found(self, config_key: str, question: str, options: list[str], dependent_config_keys: Optional[list[str]] = None) -> str:
        # XXX: should this also update the feedback?
        if not getattr(config, config_key):
            if dependent_config_keys is not None:
                for dependent_config_key in dependent_config_keys:
                    setattr(config, dependent_config_key, None)
            setattr(config, config_key, self.app.ask(question, options))
            self.app._hook()
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
        options = [default]
        # XXX: This also needs to allow the user to put in their own custom path
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
    
    