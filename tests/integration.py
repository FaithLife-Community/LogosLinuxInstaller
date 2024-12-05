"""Basic implementations of some rudimentary tests

Should be migrated into unittests once that branch is merged
"""
# FIXME: refactor into unittests

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Callable, Optional

REPOSITORY_ROOT_PATH = Path(__file__).parent.parent

@dataclass
class CommandFailedError(Exception):
    """Command Failed to execute"""
    command: list[str]
    stdout: str
    stderr: str

class TestFailed(Exception):
    pass

def run_cmd(*args, **kwargs) -> subprocess.CompletedProcess[str]:
    """Wrapper around subprocess.run that:
    - captures stdin/stderr
    - sets text mode
    - checks returncode before returning

    All other args are passed through to subprocess.run
    """
    if "stdout" not in kwargs:
        kwargs["stdout"] = subprocess.PIPE
    if "stderr" not in kwargs:
        kwargs["stderr"] = subprocess.PIPE
    kwargs["text"] = True
    output = subprocess.run(*args, **kwargs)
    try:
        output.check_returncode()
    except subprocess.CalledProcessError as e:
        raise CommandFailedError(
            command=args[0],
            stderr=output.stderr,
            stdout=output.stdout
        ) from e
    return output

class OuDedetai:
    _binary: Optional[str] = None
    _temp_dir: Optional[str] = None
    config: Optional[Path] = None
    install_dir: Optional[Path] = None
    log_level: str
    """Log level. One of:
    - quiet - warn+ - status
    - normal - warn+
    - verbose - info+
    - debug - debug
    """


    def __init__(self, isolate: bool = True, log_level: str = "quiet"):
        if isolate:
            self.isolate_files()
        self.log_level = log_level

    def isolate_files(self):
        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir)
        self._temp_dir = tempfile.mkdtemp()
        self.config = Path(self._temp_dir) / "config.json"
        self.install_dir = Path(self._temp_dir) / "install_dir"

    @classmethod
    def _source_last_update(cls) -> float:
        """Last updated time of any source code in seconds since epoch"""
        path = REPOSITORY_ROOT_PATH / "ou_dedetai"
        output: float = 0
        for root, _, files in os.walk(path):
            for file in files:
                file_m = os.stat(Path(root) / file).st_mtime
                if file_m > output:
                    output = file_m
        return output

    @classmethod
    def _oudedetai_binary(cls) -> str:
        """Return the path to the binary"""
        output = REPOSITORY_ROOT_PATH / "dist" / "oudedetai"
        # First check to see if we need to build.
        # If either the file doesn't exist, or it was last modified earlier than
        # the source code, rebuild.
        if (
            not output.exists()
            or cls._source_last_update() > os.stat(str(output)).st_mtime
        ):
            print("Building binary...")
            if output.exists():
                os.remove(str(output))
            run_cmd(f"{REPOSITORY_ROOT_PATH / "scripts" / "build-binary.sh"}")

            if not output.exists():
                raise Exception("Build process failed to yield binary")
            print("Built binary.")

        return str(output)

    def run(self, *args, **kwargs):
        if self._binary is None:
            self._binary = self._oudedetai_binary()
        if "env" not in kwargs:
            kwargs["env"] = {}
        env: dict[str, str] = {}
        if self.config:
            env["CONFIG_FILE"] = str(self.config)
        if self.install_dir:
            env["INSTALLDIR"] = str(self.install_dir)
        env["PATH"] = os.environ.get("PATH", "")
        env["HOME"] = os.environ.get("HOME", "")
        env["DISPLAY"] = os.environ.get("DISPLAY", "")
        kwargs["env"] = env
        log_level = ""
        if self.log_level == "debug":
            log_level = "--debug"
        elif self.log_level == "verbose":
            log_level = "--verbose"
        elif self.log_level == "quiet":
            log_level = "--quiet"
        args = ([self._binary, log_level] + args[0], *args[1:])
        # FIXME: Output to both stdout and PIPE (for debugging these tests)
        output = run_cmd(*args, **kwargs)

        # Output from the app indicates error/warning. Raise.
        if output.stderr:
            raise CommandFailedError(
                args[0],
                stdout=output.stdout,
                stderr=output.stderr
            )
        return output

    def clean(self):
        if self.install_dir and self.install_dir.exists():
            shutil.rmtree(self.install_dir)
        if self.config:
            os.remove(self.config)
        if self._temp_dir:
            shutil.rmtree(self._temp_dir)


def wait_for_true(callable: Callable[[], Optional[bool]], timeout: int = 10) -> bool:
    exception = None
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            if callable():
                return True
        except Exception as e:
            exception = e
        time.sleep(.1)
    if exception:
        raise exception
    return False


def wait_for_window(window_name: str, timeout: int = 10):
    """Waits for an Xorg window to open, raises exception if it doesn't"""
    def _window_open():
        output = run_cmd(["xwininfo", "-tree", "-root"])
        if output.stderr:
            raise Exception(f"xwininfo failed: {output.stdout}\n{output.stderr}")
        if window_name not in output.stdout:
            raise Exception(f"Could not find {window_name} in {output.stdout}")
        return True
    wait_for_true(_window_open, timeout=timeout)


def check_logos_open() -> None:
    """Raises an exception if Logos isn't open"""
    # Check with Xorg to see if there is a window running with the string logos.exe
    wait_for_window("logos.exe")



def test_run(ou_dedetai: OuDedetai):
    ou_dedetai.run(["--stop-installed-app"])

    # First launch Run the app. This assumes that logos is spawned before this completes
    ou_dedetai.run(["--run-installed-app"])

    wait_for_true(check_logos_open)

    ou_dedetai.run(["--stop-installed-app"])


def test_install() -> OuDedetai:
    ou_dedetai = OuDedetai(log_level="debug")
    ou_dedetai.run(["--install-app", "--assume-yes"])
    
    # To actually test the install we need to run it
    test_run(ou_dedetai)
    return ou_dedetai


def test_remove_install_dir(ou_dedetai: OuDedetai):
    if ou_dedetai.install_dir is None:
        raise ValueError("Can only test removing install dir on isolated install")
    ou_dedetai.run(["--remove-install-dir", "--assume-yes"])
    if ou_dedetai.install_dir.exists():
        raise TestFailed("Installation directory exists after --remove-install-dir")
    ou_dedetai.install_dir = None


def main():
    # FIXME: consider loop to run all of these in their supported distroboxes (https://distrobox.it/)
    ou_dedetai = test_install()
    test_remove_install_dir(ou_dedetai)
    
    ou_dedetai.clean()


    # Untested:
    # - run_indexing - Need to be logged in
    # - edit-config - would need to modify EDITOR for this, not a lot of value
    # --install-dependencies - would be easy enough to run this, but not a real test
    #   considering the machine the tests are running on probably already has it
    #   installed and it's already run in install-all
    # --update-self - we might be able to fake it into thinking we're an older version
    # --update-latest-appimage - we're already at latest as a result of install-app
    # --install-* - already effectively tested as a result of install-app, may be 
    #   difficult to confirm independently
    # --set-appimage - just needs to be implemented
    # --get-winetricks - no need to test independently, covered in install_app
    # --run-winetricks - needs a way to cleanup after this spawns
    # --toggle-app-logging - difficult to confirm
    # --create-shortcuts - easy enough, unsure the use of this, shouldn't this already
    #   be done? Nothing in here should change? The user can always re-run the entire
    #   process if they want to do this
    # --winetricks - unsure how'd we confirm it work

    # Final message
    print("Tests passed.")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
