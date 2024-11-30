
import abc
import logging
import os
import sys
from typing import Optional

from ou_dedetai.constants import PROMPT_OPTION_DIRECTORY, PROMPT_OPTION_FILE


class App(abc.ABC):
    installer_step_count: int = 0
    """Total steps in the installer, only set the installation process has started."""
    installer_step: int = 1
    """Step the installer is on. Starts at 0"""

    def __init__(self, config, **kwargs) -> None:
        # This lazy load is required otherwise it would be a circular import
        from ou_dedetai.config import Config
        self.conf = Config(config, self)
        from ou_dedetai.logos import LogosManager
        self.logos = LogosManager(app=self)
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

    def approve_or_exit(self, question: str, context: Optional[str] = None):
        """Asks the user a question, if they refuse, shutdown"""
        if not self.approve(question, context):
            self.exit(f"User refused the prompt: {question}")

    def approve(self, question: str, context: Optional[str] = None) -> bool:
        """Asks the user a y/n question"""
        question = f"{context}\n" if context is not None else "" + question
        options = ["Yes", "No"]
        return self.ask(question, options) == "Yes"

    def exit(self, reason: str, intended:bool=False):
        """Exits the application cleanly with a reason"""
        self.logos.end_processes()
        if intended:
            sys.exit(0)
        else:
            logging.error(f"Cannot continue because {reason}")
            sys.exit(1)

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

    def is_installed(self) -> bool:
        """Returns whether the install was successful by
        checking if the installed exe exists and is executable"""
        if self.conf.logos_exe is not None:
            return os.access(self.conf.logos_exe, os.X_OK)
        return False

    def status(self, message: str, percent: Optional[int] = None):
        """A status update"""
        print(f"{message}")

    @property
    def superuser_command(self) -> str:
        """Command when root privileges are needed.

        Raises:
            SuperuserCommandNotFound

        May be sudo or pkexec for example"""
        from ou_dedetai.system import get_superuser_command
        return get_superuser_command()
    
    # Start hooks
    def _config_updated_hook(self) -> None:
        """Function run when the config changes"""

    def _install_complete_hook(self):
        """Function run when installation is complete."""

    def _install_started_hook(self):
        """Function run when installation first begins."""