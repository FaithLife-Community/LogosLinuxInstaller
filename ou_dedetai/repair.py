"""File and logic dedicated to diagnosing problems with installations
and applying fixes as needed
"""

from enum import Enum, auto
import logging
from pathlib import Path
import time
from typing import Callable, Optional

import ou_dedetai
from ou_dedetai.app import App
import ou_dedetai.cli
from ou_dedetai.config import EphemeralConfiguration, PersistentConfiguration
import ou_dedetai.config
import ou_dedetai.constants
import ou_dedetai.gui_app
import ou_dedetai.installer
import ou_dedetai.msg
import ou_dedetai.system
import ou_dedetai.utils

class FailureType(Enum):
    FailedUpgrade = auto()


def detect_broken_install(
    logos_appdata_dir: Optional[str],
    faithlife_product: Optional[str]
) -> Optional[FailureType]:
    if (
        not logos_appdata_dir
        or not Path(logos_appdata_dir).exists()
        or not faithlife_product
    ):
        logging.debug("Application not installed, no need to attempt repairs")
        return None

    logos_app_dir = Path(logos_appdata_dir)
    # Check to see if there is a Logos.exe in the System dir but not in the top-level
    # This is a symptom of a failed in-app upgrade
    if (
        (logos_app_dir / "System" / (faithlife_product + ".exe")).exists()
        and not (logos_app_dir / (faithlife_product + ".exe")).exists()
    ):
        return FailureType.FailedUpgrade
    return None


# FIXME: This logic doesn't belong here, but it's not used anywhere else
# As running the control panel in addition to the base python app logic
# are distinct operations
# It's possible to add a control panel function to app and make this generic
def run_under_app(ephemeral_config: EphemeralConfiguration, func: Callable[[App], None]): #noqa: E501
    dialog = ephemeral_config.dialog or ou_dedetai.system.get_dialog()
    if dialog == 'tk':
        return ou_dedetai.gui_app.control_panel_app(ephemeral_config, func)
    else:
        app = ou_dedetai.cli.CLI(ephemeral_config)
        func(app)

def detect_and_recover(ephemeral_config: EphemeralConfiguration):
    persistent_config = PersistentConfiguration.load_from_path(ephemeral_config.config_path) #noqa: E501
    if (
        persistent_config.install_dir is None
        or persistent_config.faithlife_product is None
    ):
        # Couldn't find enough information to install
        return
    wine_prefix = ou_dedetai.config.get_wine_prefix_path(persistent_config.install_dir)
    wine_user = ou_dedetai.config.get_wine_user(wine_prefix)
    if wine_user is None:
        return
    logos_appdata_dir = ou_dedetai.config.get_logos_appdata_dir(
        wine_prefix,
        wine_user,
        persistent_config.faithlife_product
    )
    detected_failure = detect_broken_install(
        logos_appdata_dir,
        persistent_config.faithlife_product
    )
    if not detected_failure:
        return

    if detected_failure == FailureType.FailedUpgrade:
        logging.info(f"{persistent_config.faithlife_product_release=}") #noqa: E501
        # Ensure that the target release is unset before installing
        # This will force the user to install the latest version
        # rather than the version they initially installed at (which may be very old)
        persistent_config.faithlife_product_release = None
        persistent_config.write_config()

        def _run(app: App):
            app.status(f"Recovering {persistent_config.faithlife_product} after failed upgrade") #noqa: E501
            # Wait for a second so user can see this message
            time.sleep(1)
            ou_dedetai.installer.install(app)
            app.status(f"Recovery attempt of {app.conf.faithlife_product} complete")
        run_under_app(ephemeral_config, _run)

    # FIXME: Read the LogosCrash.log and suggest other recovery methods
    # and ensure it's fresh by comparing against LogosError.log

    # FIXME: find symptoms of a botched first-time update, and delete everything to get
    # user back to login screen (or back to first time at least)