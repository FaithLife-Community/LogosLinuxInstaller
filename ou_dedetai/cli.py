import queue
import threading

from . import control
from . import installer
from . import logos
from . import wine
from . import utils


class CLI:
    def __init__(self):
        self.running: bool = True
        self.choice_q = queue.Queue()
        self.input_q = queue.Queue()
        self.input_event = threading.Event()
        self.choice_event = threading.Event()
        self.logos = logos.LogosManager(app=self)

    def backup(self):
        control.backup(app=self)

    def create_shortcuts(self):
        installer.create_launcher_shortcuts()

    def edit_config(self):
        control.edit_config()

    def get_winetricks(self):
        control.set_winetricks()

    def install_app(self):
        self.thread = utils.start_thread(
            installer.ensure_launcher_shortcuts,
            app=self
        )
        self.user_input_processor()

    def install_d3d_compiler(self):
        wine.install_d3d_compiler()

    def install_dependencies(self):
        utils.install_dependencies(app=self)

    def install_fonts(self):
        wine.install_fonts()

    def install_icu(self):
        wine.enforce_icu_data_files()

    def remove_index_files(self):
        control.remove_all_index_files()

    def remove_install_dir(self):
        control.remove_install_dir()

    def remove_library_catalog(self):
        control.remove_library_catalog()

    def restore(self):
        control.restore(app=self)

    def run_indexing(self):
        self.logos.index()

    def run_installed_app(self):
        self.logos.start()

    def run_winetricks(self):
        wine.run_winetricks()

    def set_appimage(self):
        utils.set_appimage_symlink(app=self)

    def stop(self):
        self.running = False

    def toggle_app_logging(self):
        self.logos.switch_logging()

    def update_latest_appimage(self):
        utils.update_to_latest_recommended_appimage()

    def update_self(self):
        utils.update_to_latest_lli_release()

    def winetricks(self):
        import config
        wine.run_winetricks_cmd(*config.winetricks_args)

    def user_input_processor(self, evt=None):
        while self.running:
            prompt = None
            question = None
            options = None
            choice = None
            # Wait for next input queue item.
            self.input_event.wait()
            self.input_event.clear()
            prompt = self.input_q.get()
            if prompt is None:
                return
            if prompt is not None and isinstance(prompt, tuple):
                question = prompt[0]
                options = prompt[1]
            if question is not None and options is not None:
                # Convert options list to string.
                default = options[0]
                options[0] = f"{options[0]} [default]"
                optstr = ', '.join(options)
                choice = input(f"{question}: {optstr}: ")
                if len(choice) == 0:
                    choice = default
            if choice is not None and choice.lower() == 'exit':
                self.running = False
            if choice is not None:
                self.choice_q.put(choice)
                self.choice_event.set()


# NOTE: These subcommands are outside the CLI class so that the class can be
# instantiated at the moment the subcommand is run. This lets any CLI-specific
# code get executed along with the subcommand.
def backup():
    CLI().backup()


def create_shortcuts():
    CLI().create_shortcuts()


def edit_config():
    CLI().edit_config()


def get_winetricks():
    CLI().get_winetricks()


def install_app():
    CLI().install_app()


def install_d3d_compiler():
    CLI().install_d3d_compiler()


def install_dependencies():
    CLI().install_dependencies()


def install_fonts():
    CLI().install_fonts()


def install_icu():
    CLI().install_icu()


def remove_index_files():
    CLI().remove_index_files()


def remove_install_dir():
    CLI().remove_install_dir()


def remove_library_catalog():
    CLI().remove_library_catalog()


def restore():
    CLI().restore()


def run_indexing():
    CLI().run_indexing()


def run_installed_app():
    CLI().run_installed_app()


def run_winetricks():
    CLI().run_winetricks()


def set_appimage():
    CLI().set_appimage()


def toggle_app_logging():
    CLI().toggle_app_logging()


def update_latest_appimage():
    CLI().update_latest_appimage()


def update_self():
    CLI().update_self()


def winetricks():
    CLI().winetricks()
