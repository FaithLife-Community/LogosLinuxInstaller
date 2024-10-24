import abc
from typing import Optional

from ou_dedetai import config


class App(abc.ABC):
    def __init__(self, **kwargs) -> None:
        self.conf = Config(self)

    def ask(self, question: str, options: list[str]) -> str:
        """Askes the user a question with a list of supplied options

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

    def _hook_product_update(self, product: Optional[str]):
        """A hook for any changes the individual apps want to do when a platform changes"""
        pass

class Config:
    def __init__(self, app: App) -> None:
        self.app = app

    @property
    def faithlife_product(self) -> str:
        """Wrapper function that ensures that ensures the product is set
        
        if it's not then the user is prompted to choose one."""
        if not config.FLPRODUCT:
            question = "Choose which FaithLife product the script should install: "  # noqa: E501
            options = ["Logos", "Verbum"]
            config.FLPRODUCT = self.app.ask(question, options)
            self.app._hook_product_update(config.FLPRODUCT)
        return config.FLPRODUCT