import logging
import os
import shutil
import sys
from pathlib import Path

from . import config
from . import msg
from . import network
from . import system
from . import utils
from . import wine


def ensure_product_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    update_install_feedback("Choose product…", app=app)
    logging.debug('- config.FLPRODUCT')
    logging.debug('- config.FLPRODUCTi')
    logging.debug('- config.VERBUM_PATH')

    if not config.FLPRODUCT:
        if config.DIALOG == 'cli':
            app.input_q.put(
                (
                    "Choose which FaithLife product the script should install: ",  # noqa: E501
                    ["Logos", "Verbum", "Exit"]
                )
            )
            app.input_event.set()
            app.choice_event.wait()
            app.choice_event.clear()
            config.FLPRODUCT = app.choice_q.get()
        else:
            utils.send_task(app, 'FLPRODUCT')
            if config.DIALOG == 'curses':
                app.product_e.wait()
            config.FLPRODUCT = app.product_q.get()
    else:
        if config.DIALOG == 'curses' and app:
            app.set_product(config.FLPRODUCT)

    config.FLPRODUCTi = get_flproducti_name(config.FLPRODUCT)
    if config.FLPRODUCT == 'Logos':
        config.VERBUM_PATH = "/"
    elif config.FLPRODUCT == 'Verbum':
        config.VERBUM_PATH = "/Verbum/"

    logging.debug(f"> {config.FLPRODUCT=}")
    logging.debug(f"> {config.FLPRODUCTi=}")
    logging.debug(f"> {config.VERBUM_PATH=}")


def ensure_version_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_product_choice(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Choose version…", app=app)
    logging.debug('- config.TARGETVERSION')
    if not config.TARGETVERSION:
        if config.DIALOG == 'cli':
            app.input_q.put(
                (
                    f"Which version of {config.FLPRODUCT} should the script install?: ",  # noqa: E501
                    ["10", "9", "Exit"]
                )
            )
            app.input_event.set()
            app.choice_event.wait()
            app.choice_event.clear()
            config.TARGETVERSION = app.choice_q.get()
        else:
            utils.send_task(app, 'TARGETVERSION')
            if config.DIALOG == 'curses':
                app.version_e.wait()
            config.TARGETVERSION = app.version_q.get()
    else:
        if config.DIALOG == 'curses' and app:
            app.set_version(config.TARGETVERSION)

    logging.debug(f"> {config.TARGETVERSION=}")


def ensure_release_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_version_choice(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Choose product release…", app=app)
    logging.debug('- config.TARGET_RELEASE_VERSION')

    if not config.TARGET_RELEASE_VERSION:
        if config.DIALOG == 'cli':
            utils.start_thread(
                network.get_logos_releases,
                daemon_bool=True,
                app=app
            )
            app.input_event.set()
            app.choice_event.wait()
            app.choice_event.clear()
            config.TARGET_RELEASE_VERSION = app.choice_q.get()
        else:
            utils.send_task(app, 'TARGET_RELEASE_VERSION')
            if config.DIALOG == 'curses':
                app.release_e.wait()
            config.TARGET_RELEASE_VERSION = app.release_q.get()
            logging.debug(f"{config.TARGET_RELEASE_VERSION=}")
    else:
        if config.DIALOG == 'curses' and app:
            app.set_release(config.TARGET_RELEASE_VERSION)

    logging.debug(f"> {config.TARGET_RELEASE_VERSION=}")


def ensure_install_dir_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_release_choice(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback(
        "Choose installation folder…",
        app=app
    )
    logging.debug('- config.INSTALLDIR')

    default = f"{str(Path.home())}/{config.FLPRODUCT}Bible{config.TARGETVERSION}"  # noqa: E501
    if not config.INSTALLDIR:
        if config.DIALOG == 'cli':
            default = f"{str(Path.home())}/{config.FLPRODUCT}Bible{config.TARGETVERSION}"  # noqa: E501
            question = f"Where should {config.FLPRODUCT} files be installed to?: "  # noqa: E501
            app.input_q.put(
                (
                    question,
                    [default, "Type your own custom path", "Exit"]
                )
            )
            app.input_event.set()
            app.choice_event.wait()
            app.choice_event.clear()
            config.INSTALLDIR = app.choice_q.get()
        elif config.DIALOG == 'tk':
            config.INSTALLDIR = default
        elif config.DIALOG == 'curses':
            utils.send_task(app, 'INSTALLDIR')
            app.installdir_e.wait()
            config.INSTALLDIR = app.installdir_q.get()
        config.APPDIR_BINDIR = f"{config.INSTALLDIR}/data/bin"
    else:
        if config.DIALOG == 'curses' and app:
            app.set_installdir(config.INSTALLDIR)

    logging.debug(f"> {config.INSTALLDIR=}")
    logging.debug(f"> {config.APPDIR_BINDIR=}")


def ensure_wine_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_install_dir_choice(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Choose wine binary…", app=app)
    logging.debug('- config.SELECTED_APPIMAGE_FILENAME')
    logging.debug('- config.RECOMMENDED_WINE64_APPIMAGE_URL')
    logging.debug('- config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME')
    logging.debug('- config.RECOMMENDED_WINE64_APPIMAGE_FILENAME')
    logging.debug('- config.WINE_EXE')
    logging.debug('- config.WINEBIN_CODE')

    if utils.get_wine_exe_path() is None:
        network.set_recommended_appimage_config()
        if config.DIALOG == 'cli':
            options = utils.get_wine_options(
                utils.find_appimage_files(config.TARGET_RELEASE_VERSION),
                utils.find_wine_binary_files(config.TARGET_RELEASE_VERSION)
            )
            app.input_q.put(
                (
                    f"Which Wine AppImage or binary should the script use to install {config.FLPRODUCT} v{config.TARGET_RELEASE_VERSION} in {config.INSTALLDIR}?: ",  # noqa: E501
                    options
                )
            )
            app.input_event.set()
            app.choice_event.wait()
            app.choice_event.clear()
            config.WINE_EXE = utils.get_relative_path(
                utils.get_config_var(app.choice_q.get()),
                config.INSTALLDIR
            )
        else:
            utils.send_task(app, 'WINE_EXE')
            if config.DIALOG == 'curses':
                app.wine_e.wait()
                config.WINE_EXE = app.wines_q.get()
            # GUI uses app.wines_q for list of available, then app.wine_q
            # for the user's choice of specific binary.
            elif config.DIALOG == 'tk':
                config.WINE_EXE = app.wine_q.get()

    else:
        if config.DIALOG == 'curses' and app:
            app.set_wine(utils.get_wine_exe_path())

    # Set WINEBIN_CODE and SELECTED_APPIMAGE_FILENAME.
    m = f"Preparing to process WINE_EXE. Currently set to: {utils.get_wine_exe_path()}."  # noqa: E501
    logging.debug(m)
    if str(utils.get_wine_exe_path()).lower().endswith('.appimage'):
        config.SELECTED_APPIMAGE_FILENAME = str(utils.get_wine_exe_path())
    if not config.WINEBIN_CODE:
        config.WINEBIN_CODE = utils.get_winebin_code_and_desc(utils.get_wine_exe_path())[0]  # noqa: E501

    logging.debug(f"> {config.SELECTED_APPIMAGE_FILENAME=}")
    logging.debug(f"> {config.RECOMMENDED_WINE64_APPIMAGE_URL=}")
    logging.debug(f"> {config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME=}")
    logging.debug(f"> {config.RECOMMENDED_WINE64_APPIMAGE_FILENAME=}")
    logging.debug(f"> {config.WINEBIN_CODE=}")
    logging.debug(f"> {utils.get_wine_exe_path()=}")


def ensure_winetricks_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_wine_choice(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Choose winetricks binary…", app=app)
    logging.debug('- config.WINETRICKSBIN')

    if config.WINETRICKSBIN is None:
        # Check if local winetricks version available; else, download it.
        config.WINETRICKSBIN = f"{config.APPDIR_BINDIR}/winetricks"

        winetricks_options = utils.get_winetricks_options()

        if config.DIALOG == 'cli':
            app.input_q.put(
                (
                    f"Should the script use the system's local winetricks or download the latest winetricks from the Internet? The script needs to set some Wine options that {config.FLPRODUCT} requires on Linux.",  # noqa: E501
                    winetricks_options
                )
            )
            app.input_event.set()
            app.choice_event.wait()
            app.choice_event.clear()
            winetricksbin = app.choice_q.get()
        else:
            utils.send_task(app, 'WINETRICKSBIN')
            if config.DIALOG == 'curses':
                app.tricksbin_e.wait()
            winetricksbin = app.tricksbin_q.get()

        if not winetricksbin.startswith('Download'):
            config.WINETRICKSBIN = winetricksbin
        else:
            config.WINETRICKSBIN = winetricks_options[0]

    logging.debug(f"> {config.WINETRICKSBIN=}")


def ensure_install_fonts_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_winetricks_choice(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Ensuring install fonts choice…", app=app)
    logging.debug('- config.SKIP_FONTS')

    logging.debug(f"> {config.SKIP_FONTS=}")


def ensure_check_sys_deps_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_install_fonts_choice(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback(
        "Ensuring check system dependencies choice…",
        app=app
    )
    logging.debug('- config.SKIP_DEPENDENCIES')

    logging.debug(f"> {config.SKIP_DEPENDENCIES=}")


def ensure_installation_config(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_check_sys_deps_choice(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Ensuring installation config is set…", app=app)
    logging.debug('- config.LOGOS_ICON_URL')
    logging.debug('- config.LOGOS_ICON_FILENAME')
    logging.debug('- config.LOGOS_VERSION')
    logging.debug('- config.LOGOS64_MSI')
    logging.debug('- config.LOGOS64_URL')

    # Set icon variables.
    app_dir = Path(__file__).parent
    flproducti = get_flproducti_name(config.FLPRODUCT)
    logos_icon_url = app_dir / 'img' / f"{flproducti}-128-icon.png"
    config.LOGOS_ICON_URL = str(logos_icon_url)
    config.LOGOS_ICON_FILENAME = logos_icon_url.name
    config.LOGOS64_URL = f"https://downloads.logoscdn.com/LBS{config.TARGETVERSION}{config.VERBUM_PATH}Installer/{config.TARGET_RELEASE_VERSION}/{config.FLPRODUCT}-x64.msi"  # noqa: E501

    config.LOGOS_VERSION = config.TARGET_RELEASE_VERSION
    config.LOGOS64_MSI = Path(config.LOGOS64_URL).name

    logging.debug(f"> {config.LOGOS_ICON_URL=}")
    logging.debug(f"> {config.LOGOS_ICON_FILENAME=}")
    logging.debug(f"> {config.LOGOS_VERSION=}")
    logging.debug(f"> {config.LOGOS64_MSI=}")
    logging.debug(f"> {config.LOGOS64_URL=}")

    if config.DIALOG in ['curses', 'dialog', 'tk']:
        utils.send_task(app, 'INSTALL')
    else:
        msg.logos_msg("Install is running…")


def ensure_install_dirs(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_installation_config(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Ensuring installation directories…", app=app)
    logging.debug('- config.INSTALLDIR')
    logging.debug('- config.WINEPREFIX')
    logging.debug('- data/bin')
    logging.debug('- data/wine64_bottle')
    wine_dir = Path("")

    if config.INSTALLDIR is None:
        config.INSTALLDIR = f"{os.getenv('HOME')}/{config.FLPRODUCT}Bible{config.TARGETVERSION}"  # noqa: E501

    config.APPDIR_BINDIR = f"{config.INSTALLDIR}/data/bin"
    bin_dir = Path(config.APPDIR_BINDIR)
    bin_dir.mkdir(parents=True, exist_ok=True)
    logging.debug(f"> {bin_dir} exists?: {bin_dir.is_dir()}")

    logging.debug(f"> {config.INSTALLDIR=}")
    logging.debug(f"> {config.APPDIR_BINDIR=}")

    config.WINEPREFIX = f"{config.INSTALLDIR}/data/wine64_bottle"
    wine_dir = Path(f"{config.WINEPREFIX}")
    wine_dir.mkdir(parents=True, exist_ok=True)

    logging.debug(f"> {wine_dir} exists: {wine_dir.is_dir()}")
    logging.debug(f"> {config.WINEPREFIX=}")

    if config.DIALOG in ['curses', 'dialog', 'tk']:
        utils.send_task(app, 'INSTALLING')


def ensure_sys_deps(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_install_dirs(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Ensuring system dependencies are met…", app=app)

    if not config.SKIP_DEPENDENCIES:
        utils.install_dependencies(app)
        if config.DIALOG == "curses":
            app.installdeps_e.wait()
        logging.debug("> Done.")
    else:
        logging.debug("> Skipped.")


def ensure_appimage_download(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_sys_deps(app=app)
    config.INSTALL_STEP += 1
    if config.TARGETVERSION != '9' and not str(utils.get_wine_exe_path()).lower().endswith('appimage'):  # noqa: E501
        return
    update_install_feedback(
        "Ensuring wine AppImage is downloaded…",
        app=app
    )

    downloaded_file = None
    filename = Path(config.SELECTED_APPIMAGE_FILENAME).name
    downloaded_file = utils.get_downloaded_file_path(filename)
    if not downloaded_file:
        downloaded_file = Path(f"{config.MYDOWNLOADS}/{filename}")
    network.logos_reuse_download(
        config.RECOMMENDED_WINE64_APPIMAGE_URL,
        filename,
        config.MYDOWNLOADS,
        app=app,
    )
    if downloaded_file:
        logging.debug(f"> File exists?: {downloaded_file}: {Path(downloaded_file).is_file()}")  # noqa: E501


def ensure_wine_executables(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_appimage_download(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback(
        "Ensuring wine executables are available…",
        app=app
    )
    logging.debug('- config.WINESERVER_EXE')
    logging.debug('- wine')
    logging.debug('- wine64')
    logging.debug('- wineserver')

    # Add APPDIR_BINDIR to PATH.
    if not os.access(utils.get_wine_exe_path(), os.X_OK):
        msg.status("Creating wine appimage symlinks…", app=app)
        create_wine_appimage_symlinks(app=app)

    # Set WINESERVER_EXE.
    config.WINESERVER_EXE = f"{config.APPDIR_BINDIR}/wineserver"

    # PATH is modified if wine appimage isn't found, but it's not modified
    # during a restarted installation, so shutil.which doesn't find the
    # executables in that case.
    logging.debug(f"> {config.WINESERVER_EXE=}")
    logging.debug(f"> wine path: {config.APPDIR_BINDIR}/wine")
    logging.debug(f"> wine64 path: {config.APPDIR_BINDIR}/wine64")
    logging.debug(f"> wineserver path: {config.APPDIR_BINDIR}/wineserver")
    logging.debug(f"> winetricks path: {config.APPDIR_BINDIR}/winetricks")


def ensure_winetricks_executable(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_wine_executables(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback(
        "Ensuring winetricks executable is available…",
        app=app
    )

    if config.WINETRICKSBIN is None or config.WINETRICKSBIN.startswith('Download'):  # noqa: E501
        config.WINETRICKSBIN = f"{config.APPDIR_BINDIR}/winetricks"  # default
    if not os.access(config.WINETRICKSBIN, os.X_OK):
        # Either previous system winetricks is no longer accessible, or the
        # or the user has chosen to download it.
        msg.status("Downloading winetricks from the Internet…", app=app)
        system.install_winetricks(config.APPDIR_BINDIR, app=app)

    logging.debug(f"> {config.WINETRICKSBIN} is executable?: {os.access(config.WINETRICKSBIN, os.X_OK)}")  # noqa: E501
    return 0


def ensure_premade_winebottle_download(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_winetricks_executable(app=app)
    config.INSTALL_STEP += 1
    if config.TARGETVERSION != '9':
        return
    update_install_feedback(
        f"Ensuring {config.LOGOS9_WINE64_BOTTLE_TARGZ_NAME} bottle is downloaded…",  # noqa: E501
        app=app
    )

    downloaded_file = utils.get_downloaded_file_path(config.LOGOS9_WINE64_BOTTLE_TARGZ_NAME)  # noqa: E501
    if not downloaded_file:
        downloaded_file = Path(config.MYDOWNLOADS) / config.LOGOS_EXECUTABLE
    network.logos_reuse_download(
        config.LOGOS9_WINE64_BOTTLE_TARGZ_URL,
        config.LOGOS9_WINE64_BOTTLE_TARGZ_NAME,
        config.MYDOWNLOADS,
        app=app,
    )
    # Install bottle.
    bottle = Path(f"{config.INSTALLDIR}/data/wine64_bottle")
    if not bottle.is_dir():
        utils.install_premade_wine_bottle(
            config.MYDOWNLOADS,
            f"{config.INSTALLDIR}/data"
        )

    logging.debug(f"> '{downloaded_file}' exists?: {Path(downloaded_file).is_file()}")  # noqa: E501


def ensure_product_installer_download(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_premade_winebottle_download(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback(
        f"Ensuring {config.FLPRODUCT} installer is downloaded…",
        app=app
    )

    config.LOGOS_EXECUTABLE = f"{config.FLPRODUCT}_v{config.LOGOS_VERSION}-x64.msi"  # noqa: E501
    downloaded_file = utils.get_downloaded_file_path(config.LOGOS_EXECUTABLE)
    if not downloaded_file:
        downloaded_file = Path(config.MYDOWNLOADS) / config.LOGOS_EXECUTABLE
    network.logos_reuse_download(
        config.LOGOS64_URL,
        config.LOGOS_EXECUTABLE,
        config.MYDOWNLOADS,
        app=app,
    )
    # Copy file into INSTALLDIR.
    installer = Path(f"{config.INSTALLDIR}/data/{config.LOGOS_EXECUTABLE}")
    if not installer.is_file():
        shutil.copy(downloaded_file, installer.parent)

    logging.debug(f"> '{downloaded_file}' exists?: {Path(downloaded_file).is_file()}")  # noqa: E501


def ensure_wineprefix_init(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_product_installer_download(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Ensuring wineprefix is initialized…", app=app)

    init_file = Path(f"{config.WINEPREFIX}/system.reg")
    logging.debug(f"{init_file=}")
    if not init_file.is_file():
        logging.debug(f"{init_file} does not exist")
        if config.TARGETVERSION == '9':
            utils.install_premade_wine_bottle(
                config.MYDOWNLOADS,
                f"{config.INSTALLDIR}/data",
            )
        else:
            logging.debug("Initializing wineprefix.")
            process = wine.initializeWineBottle()
            wine.wait_pid(process)
            # wine.light_wineserver_wait()
            wine.wineserver_wait()
            logging.debug("Wine init complete.")
    logging.debug(f"> {init_file} exists?: {init_file.is_file()}")


def ensure_winetricks_applied(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_wineprefix_init(app=app)
    config.INSTALL_STEP += 1
    status = "Ensuring winetricks & other settings are applied…"
    update_install_feedback(status, app=app)
    logging.debug('- disable winemenubuilder')
    logging.debug('- settings renderer=gdi')
    logging.debug('- corefonts')
    logging.debug('- tahoma')
    logging.debug('- settings fontsmooth=rgb')
    logging.debug('- d3dcompiler_47')

    if not config.SKIP_WINETRICKS:
        usr_reg = None
        sys_reg = None
        workdir = Path(f"{config.WORKDIR}")
        workdir.mkdir(parents=True, exist_ok=True)
        usr_reg = Path(f"{config.WINEPREFIX}/user.reg")
        sys_reg = Path(f"{config.WINEPREFIX}/system.reg")

        if not utils.grep(r'"winemenubuilder.exe"=""', usr_reg):
            msg.status("Disabling winemenubuilder…", app)
            wine.disable_winemenubuilder()

        if not utils.grep(r'"renderer"="gdi"', usr_reg):
            msg.status("Setting Renderer to GDI…", app)
            wine.set_renderer("gdi")

        if not utils.grep(r'"FontSmoothingType"=dword:00000002', usr_reg):
            msg.status("Setting Font Smooting to RGB…", app)
            wine.install_font_smoothing()

        if not config.SKIP_FONTS and not utils.grep(r'"Tahoma \(TrueType\)"="tahoma.ttf"', sys_reg):  # noqa: E501
            msg.status("Installing fonts…", app)
            wine.install_fonts()

        if not utils.grep(r'"\*d3dcompiler_47"="native"', usr_reg):
            msg.status("Installing D3D…", app)
            wine.install_d3d_compiler()

        if not utils.grep(r'"ProductName"="Microsoft Windows 10"', sys_reg):
            msg.status(f"Setting {config.FLPRODUCT} to Win10 Mode…", app)
            wine.set_win_version("logos", "win10")

        # NOTE: Can't use utils.grep check here because the string
        # "Version"="win10" might appear elsewhere in the registry.
        msg.logos_msg(f"Setting {config.FLPRODUCT} Bible Indexing to Win10 Mode…")  # noqa: E501
        wine.set_win_version("indexer", "win10")
        # wine.light_wineserver_wait()
        wine.wineserver_wait()
    logging.debug("> Done.")


def ensure_icu_data_files(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_winetricks_applied(app=app)
    config.INSTALL_STEP += 1
    status = "Ensuring ICU data files are installed…"
    update_install_feedback(status, app=app)
    logging.debug('- ICU data files')

    wine.enforce_icu_data_files(app=app)

    if config.DIALOG == "curses":
        app.install_icu_e.wait()

    logging.debug('> ICU data files installed')


def ensure_product_installed(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_icu_data_files(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback(
        f"Ensuring {config.FLPRODUCT} is installed…",
        app=app
    )

    if not utils.find_installed_product():
        process = wine.install_msi()
        wine.wait_pid(process)
        config.LOGOS_EXE = utils.find_installed_product()
        config.current_logos_version = config.TARGET_RELEASE_VERSION

    wine.set_logos_paths()

    # Clean up temp files, etc.
    utils.clean_all()

    logging.debug(f"> Product path: {config.LOGOS_EXE}")


def ensure_config_file(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_product_installed(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Ensuring config file is up-to-date…", app=app)

    if not Path(config.CONFIG_FILE).is_file():
        logging.info(f"No config file at {config.CONFIG_FILE}")
        create_config_file()
    else:
        logging.info(f"Config file exists at {config.CONFIG_FILE}.")
        if config_has_changed():
            if config.DIALOG == 'cli':
                if msg.logos_acknowledge_question(
                    f"Update config file at {config.CONFIG_FILE}?",
                    "The existing config file was not overwritten.",
                    ""
                ):
                    logging.info("Updating config file.")
                    utils.write_config(config.CONFIG_FILE)
            else:
                utils.send_task(app, 'CONFIG')
                if config.DIALOG == 'curses':
                    app.config_e.wait()

    if config.DIALOG == 'cli':
        msg.logos_msg("Install has finished.")
    else:
        utils.send_task(app, 'DONE')

    logging.debug(f"> File exists?: {config.CONFIG_FILE}: {Path(config.CONFIG_FILE).is_file()}")  # noqa: E501


def ensure_launcher_executable(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_config_file(app=app)
    config.INSTALL_STEP += 1
    runmode = system.get_runmode()
    if runmode == 'binary':
        update_install_feedback(
            f"Copying launcher to {config.INSTALLDIR}…",
            app=app
        )

        # Copy executable to config.INSTALLDIR.
        launcher_exe = Path(f"{config.INSTALLDIR}/{config.name_binary}")
        if launcher_exe.is_file():
            logging.debug("Removing existing launcher binary.")
            launcher_exe.unlink()
        logging.info(f"Creating launcher binary by copying this installer binary to {launcher_exe}.")  # noqa: E501
        shutil.copy(sys.executable, launcher_exe)
        logging.debug(f"> File exists?: {launcher_exe}: {launcher_exe.is_file()}")  # noqa: E501
    else:
        update_install_feedback(
            "Running from source. Skipping launcher creation.",
            app=app
        )


def ensure_launcher_shortcuts(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_launcher_executable(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Creating launcher shortcuts…", app=app)
    create_launcher_shortcuts()

    if config.DIALOG == 'cli':
        # Signal CLI.user_input_processor to stop.
        app.input_q.put(None)
        app.input_event.set()
        # Signal CLI itself to stop.
        app.stop()


def update_install_feedback(text, app=None):
    percent = get_progress_pct(config.INSTALL_STEP, config.INSTALL_STEPS_COUNT)
    logging.debug(f"Install step {config.INSTALL_STEP} of {config.INSTALL_STEPS_COUNT}")  # noqa: E501
    msg.progress(percent, app=app)
    msg.status(text, app=app)


def get_progress_pct(current, total):
    return round(current * 100 / total)


def create_wine_appimage_symlinks(app=None):
    appdir_bindir = Path(config.APPDIR_BINDIR)
    os.environ['PATH'] = f"{config.APPDIR_BINDIR}:{os.getenv('PATH')}"
    # Ensure AppImage symlink.
    appimage_link = appdir_bindir / config.APPIMAGE_LINK_SELECTION_NAME
    appimage_file = Path(config.SELECTED_APPIMAGE_FILENAME)
    appimage_filename = Path(config.SELECTED_APPIMAGE_FILENAME).name
    if config.WINEBIN_CODE in ['AppImage', 'Recommended']:
        # Ensure appimage is copied to appdir_bindir.
        downloaded_file = utils.get_downloaded_file_path(appimage_filename)
        if not appimage_file.is_file():
            msg.status(
                f"Copying: {downloaded_file} into: {appdir_bindir}",
                app=app
            )
            shutil.copy(downloaded_file, str(appdir_bindir))
        os.chmod(appimage_file, 0o755)
        appimage_filename = appimage_file.name
    elif config.WINEBIN_CODE in ["System", "Proton", "PlayOnLinux", "Custom"]:
        appimage_filename = "none.AppImage"
    else:
        msg.logos_error(
            f"WINEBIN_CODE error. WINEBIN_CODE is {config.WINEBIN_CODE}. Installation canceled!",  # noqa: E501
            app=app
        )

    appimage_link.unlink(missing_ok=True)  # remove & replace
    appimage_link.symlink_to(f"./{appimage_filename}")

    # Ensure wine executables symlinks.
    for name in ["wine", "wine64", "wineserver", "winetricks"]:
        p = appdir_bindir / name
        p.unlink(missing_ok=True)
        p.symlink_to(f"./{config.APPIMAGE_LINK_SELECTION_NAME}")


def get_flproducti_name(product_name) -> str:
    lname = product_name.lower()
    if lname == 'logos':
        return 'logos4'
    elif lname == 'verbum':
        return lname


def create_config_file():
    config_dir = Path(config.DEFAULT_CONFIG_PATH).parent
    config_dir.mkdir(exist_ok=True, parents=True)
    if config_dir.is_dir():
        utils.write_config(config.CONFIG_FILE)
        logging.info(f"A config file was created at {config.CONFIG_FILE}.")
    else:
        msg.logos_warn(f"{config_dir} does not exist. Failed to create config file.")  # noqa: E501


def config_has_changed():
    # Compare existing config file contents with installer config.
    logging.info("Comparing its contents with current config.")
    current_config_file_dict = config.get_config_file_dict(config.CONFIG_FILE)
    changed = False

    for key in config.core_config_keys:
        if current_config_file_dict.get(key) != config.__dict__.get(key):
            changed = True
            break
    return changed


def create_desktop_file(name, contents):
    launcher_path = Path(f"~/.local/share/applications/{name}").expanduser()
    if launcher_path.is_file():
        logging.info(f"Removing desktop launcher at {launcher_path}.")
        launcher_path.unlink()

    logging.info(f"Creating desktop launcher at {launcher_path}.")
    with launcher_path.open('w') as f:
        f.write(contents)
    os.chmod(launcher_path, 0o755)


def create_launcher_shortcuts():
    # Set variables for use in launcher files.
    flproduct = config.FLPRODUCT
    installdir = Path(config.INSTALLDIR)
    m = "Can't create launchers"
    if flproduct is None:
        reason = "because the FaithLife product is not defined."
        msg.logos_warning(f"{m} {reason}")  # noqa: E501
        return
    flproducti = get_flproducti_name(flproduct)
    src_dir = Path(__file__).parent
    logos_icon_src = src_dir / 'img' / f"{flproducti}-128-icon.png"
    app_icon_src = src_dir / 'img' / 'icon.png'

    if installdir is None:
        reason = "because the installation folder is not defined."
        msg.logos_warning(f"{m} {reason}")
        return
    if not installdir.is_dir():
        reason = "because the installation folder does not exist."
        msg.logos_warning(f"{m} {reason}")
        return
    app_dir = Path(installdir) / 'data'
    logos_icon_path = app_dir / logos_icon_src.name
    app_icon_path = app_dir / app_icon_src.name

    if system.get_runmode() == 'binary':
        lli_executable = f"{installdir}/{config.name_binary}"
    else:
        script = Path(sys.argv[0]).expanduser().resolve()
        repo_dir = None
        for p in script.parents:
            for c in p.iterdir():
                if c.name == '.git':
                    repo_dir = p
                    break
        # Find python in virtual environment.
        py_bin = next(repo_dir.glob('*/bin/python'))
        if not py_bin.is_file():
            msg.logos_warning("Could not locate python binary in virtual environment.")  # noqa: E501
            return
        lli_executable = f"env DIALOG=tk {py_bin} {script}"

    for (src, path) in [(app_icon_src, app_icon_path), (logos_icon_src, logos_icon_path)]:  # noqa: E501
        if not path.is_file():
            app_dir.mkdir(exist_ok=True)
            shutil.copy(src, path)
        else:
            logging.info(f"Icon found at {path}.")

    # Set launcher file names and content.
    desktop_files = [
        (
            f"{flproduct}Bible.desktop",
            f"""[Desktop Entry]
Name={flproduct}Bible
Comment=A Bible Study Library with Built-In Tools
Exec={lli_executable} --run-installed-app
Icon={logos_icon_path}
Terminal=false
Type=Application
StartupWMClass={flproduct.lower()}.exe
Categories=Education;
Keywords={flproduct};Logos;Bible;Control;
"""
        ),
        (
            f"{config.name_binary}.desktop",
            f"""[Desktop Entry]
Name={config.name_app}
GenericName=FaithLife Wine App Installer
Comment=Manages FaithLife Bible Software via Wine
Exec={lli_executable}
Icon={app_icon_path}
Terminal=false
Type=Application
StartupWMClass={config.name_binary}
Categories=Education;
Keywords={flproduct};Logos;Bible;Control;
"""
        ),
    ]

    # Create the files.
    for file_name, content in desktop_files:
        create_desktop_file(file_name, content)
        fpath = Path.home() / '.local' / 'share' / 'applications' / file_name
        logging.debug(f"> File exists?: {fpath}: {fpath.is_file()}")
