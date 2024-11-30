
import abc
import os
from typing import Optional

from ou_dedetai.constants import PROMPT_OPTION_DIRECTORY, PROMPT_OPTION_FILE


class App(abc.ABC):
    installer_step_count: int = 0
    """Total steps in the installer, only set the installation process has started."""
    installer_step: int = 1
    """Step the installer is on. Starts at 0"""

    def __init__(self, config, **kwargs) -> None:
        # This lazy load is required otherwise it would be a circular import
        from ou_dedetai.new_config import Config
        self.conf = Config(config, self)
        pass

    def ask(self, question: str, options: list[str]) -> str:
        """Asks the user a question with a list of supplied options

        Returns the option the user picked.

        If the internal ask function returns None, the process will exit with 1
        """
        passed_options: list[str] | str = options
        if len(passed_options) == 1 and (
            PROMPT_OPTION_DIRECTORY in passed_options
            or PROMPT_OPTION_FILE in passed_options
        ):
            # Set the only option to be the follow up prompt
            passed_options = options[0]
        elif passed_options is not None and self._exit_option is not None:
            passed_options = options + [self._exit_option]
        answer = self._ask(question, passed_options)
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

    def _config_updated(self) -> None:
        """A hook for any changes the individual apps want to do when the config changes
        """
        pass

    def is_installed(self) -> bool:
        """Returns whether the install was successful by
        checking if the installed exe exists and is executable"""
        if self.conf.logos_exe is not None:
            return os.access(self.conf.logos_exe, os.X_OK)
        return False

    # XXX: unused at present
    # @abc.abstractmethod
    # def update_progress(self, message: str, percent: Optional[int] = None):
    #     """Updates the progress of the current operation"""
    #     pass