import logging
import os
import shutil
import sys
from pathlib import Path

import config
import msg
import utils
import wine

#TODO: Fix install progress if user returns to main menu?
# To replicate, start a TUI install, return/cancel on second step
# Then launch a new install


def ensure_product_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    update_install_feedback("Choose product…", app=app)
    logging.debug('- config.FLPRODUCT')
    logging.debug('- config.FLPRODUCTi')
    logging.debug('- config.VERBUM_PATH')

    if not config.FLPRODUCT:
        if app:
            utils.send_task(app, 'FLPRODUCT')
            if config.DIALOG == 'curses':
                app.product_e.wait()
            config.FLPRODUCT = app.product_q.get()

    if config.FLPRODUCT == 'Logos':
        config.FLPRODUCTi = 'logos4'
        config.VERBUM_PATH = "/"
    elif config.FLPRODUCT == 'Verbum':
        config.FLPRODUCTi = 'verbum'
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
        if app:
            utils.send_task(app, 'TARGETVERSION')
            if config.DIALOG == 'curses':
                app.version_e.wait()
            config.TARGETVERSION = app.version_q.get()

    logging.debug(f"> {config.TARGETVERSION=}")


def ensure_release_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_version_choice(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Choose product release…", app=app)
    logging.debug('- config.TARGET_RELEASE_VERSION')

    if not config.TARGET_RELEASE_VERSION:
        if app:
            utils.send_task(app, 'TARGET_RELEASE_VERSION')
            if config.DIALOG == 'curses':
                app.release_e.wait()
            config.TARGET_RELEASE_VERSION = app.release_q.get()
            logging.debug(f"{config.TARGET_RELEASE_VERSION=}")

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
        if app:
            if config.DIALOG == 'tk':
                config.INSTALLDIR = default
                config.APPDIR_BINDIR = f"{config.INSTALLDIR}/data/bin"
            elif config.DIALOG == 'curses':
                utils.send_task(app, 'INSTALLDIR')
                app.installdir_e.wait()
                config.INSTALLDIR = app.installdir_q.get()
                config.APPDIR_BINDIR = f"{config.INSTALLDIR}/data/bin"

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

    if config.WINE_EXE is None:
        utils.set_recommended_appimage_config()
        if app:
            utils.send_task(app, 'WINE_EXE')
            if config.DIALOG == 'curses':
                app.wine_e.wait()
            config.WINE_EXE = app.wine_q.get()

    # Set WINEBIN_CODE and SELECTED_APPIMAGE_FILENAME.
    logging.debug(f"Preparing to process WINE_EXE. Currently set to: {config.WINE_EXE}.")
    if config.WINE_EXE.lower().endswith('.appimage'):
        config.SELECTED_APPIMAGE_FILENAME = config.WINE_EXE
    if not config.WINEBIN_CODE:
        config.WINEBIN_CODE = utils.get_winebin_code_and_desc(config.WINE_EXE)[0]  # noqa: E501

    logging.debug(f"> {config.SELECTED_APPIMAGE_FILENAME=}")
    logging.debug(f"> {config.RECOMMENDED_WINE64_APPIMAGE_URL=}")
    logging.debug(f"> {config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME=}")
    logging.debug(f"> {config.RECOMMENDED_WINE64_APPIMAGE_FILENAME=}")
    logging.debug(f"> {config.WINEBIN_CODE=}")
    logging.debug(f"> {config.WINE_EXE=}")


def ensure_winetricks_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_wine_choice(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Choose winetricks binary…", app=app)
    logging.debug('- config.WINETRICKSBIN')

    if config.WINETRICKSBIN is None:
    # Check if local winetricks version available; else, download it.
        config.WINETRICKSBIN = f"{config.APPDIR_BINDIR}/winetricks"

        utils.send_task(app, 'WINETRICKSBIN')
        if config.DIALOG == 'curses':
            app.tricksbin_e.wait()
        winetricksbin = app.tricksbin_q.get()
        if not winetricksbin.startswith('Download'):
            config.WINETRICKSBIN = winetricksbin

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
    logos_icon_url = app_dir / 'img' / f"{config.FLPRODUCTi}-128-icon.png"
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

    if app:
        utils.send_task(app, 'INSTALL')


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
        config.APPDIR_BINDIR = f"{config.INSTALLDIR}/data/bin" #noqa: E501

    bin_dir = Path(config.APPDIR_BINDIR)
    bin_dir.mkdir(parents=True, exist_ok=True)
    logging.debug(f"> {bin_dir} exists: {bin_dir.is_dir()}")

    logging.debug(f"> {config.INSTALLDIR=}")
    logging.debug(f"> {config.APPDIR_BINDIR=}")

    config.WINEPREFIX = f"{config.INSTALLDIR}/data/wine64_bottle"
    wine_dir = Path(f"{config.WINEPREFIX}")
    wine_dir.mkdir(parents=True, exist_ok=True)

    logging.debug(f"> {wine_dir} exists: {wine_dir.is_dir()}")
    logging.debug(f"> {config.WINEPREFIX=}")

    if app:
        utils.send_task(app, 'INSTALLING')


def ensure_sys_deps(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_install_dirs(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Ensuring system dependencies are met…", app=app)

    if not config.SKIP_DEPENDENCIES:
        utils.check_dependencies(app)
        logging.debug("> Done.")
    else:
        logging.debug("> Skipped.")


def ensure_appimage_download(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_sys_deps(app=app)
    config.INSTALL_STEP += 1
    if config.TARGETVERSION != '9' and not config.WINE_EXE.lower().endswith('appimage'):  # noqa: E501
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
    utils.logos_reuse_download(
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
    if not os.access(config.WINE_EXE, os.X_OK):
        appdir_bindir = Path(config.APPDIR_BINDIR)
        os.environ['PATH'] = f"{config.APPDIR_BINDIR}:{os.getenv('PATH')}"
        # Ensure AppImage symlink.
        appimage_link = appdir_bindir / config.APPIMAGE_LINK_SELECTION_NAME
        appimage_file = Path(config.SELECTED_APPIMAGE_FILENAME)
        appimage_filename = Path(config.SELECTED_APPIMAGE_FILENAME).name
        if config.WINEBIN_CODE in ['AppImage', 'Recommended']:
            # Ensure appimage is copied to appdir_bindir.
            downloaded_file = utils.get_downloaded_file_path(appimage_filename)  # noqa: E501
            if not appimage_file.is_file():
                msg.logos_msg(f"Copying: {downloaded_file} into: {str(appdir_bindir)}")  # noqa: E501
                shutil.copy(downloaded_file, str(appdir_bindir))
            os.chmod(appimage_file, 0o755)
            appimage_filename = appimage_file.name
        elif config.WINEBIN_CODE in ["System", "Proton", "PlayOnLinux", "Custom"]:  # noqa: E501
            appimage_filename = "none.AppImage"
        else:
            msg.logos_error(f"WINEBIN_CODE error. WINEBIN_CODE is {config.WINEBIN_CODE}. Installation canceled!")

        appimage_link.unlink(missing_ok=True)  # remove & replace
        appimage_link.symlink_to(f"./{appimage_filename}")

        # Ensure wine executables symlinks.
        for name in ["wine", "wine64", "wineserver"]:
            p = appdir_bindir / name
            p.unlink(missing_ok=True)
            p.symlink_to(f"./{config.APPIMAGE_LINK_SELECTION_NAME}")

    # Set WINESERVER_EXE.
    config.WINESERVER_EXE = shutil.which('wineserver')

    logging.debug(f"> {config.WINESERVER_EXE=}")
    logging.debug(f"> wine path: {shutil.which('wine')}")
    logging.debug(f"> wine64 path: {shutil.which('wine64')}")
    logging.debug(f"> wineserver path: {shutil.which('wineserver')}")


def ensure_winetricks_executable(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_wine_executables(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback(
        "Ensuring winetricks executable is available…",
        app=app
    )

    if not os.access(config.WINETRICKSBIN, os.X_OK):
        tricksbin = Path(config.WINETRICKSBIN)
        tricksbin.unlink(missing_ok=True)
        # The choice of System winetricks was made previously. Here we are only
        # concerned about whether the downloaded winetricks is usable.
        msg.logos_msg("Downloading winetricks from the Internet…")
        utils.install_winetricks(
            tricksbin.parent,
            app=app
        )
    if config.WINETRICKSBIN:
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
    utils.logos_reuse_download(
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
    utils.logos_reuse_download(
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
    if not init_file.is_file():
        if config.TARGETVERSION == '9':
            utils.install_premade_wine_bottle(
                config.MYDOWNLOADS,
                f"{config.INSTALLDIR}/data",
            )
        else:
            if config.WINE_EXE:
                wine.initializeWineBottle()
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

    usr_reg = None
    sys_reg = None
    workdir = Path(f"{config.WORKDIR}")
    workdir.mkdir(parents=True, exist_ok=True)
    usr_reg = Path(f"{config.WINEPREFIX}/user.reg")
    sys_reg = Path(f"{config.WINEPREFIX}/system.reg")
    if not utils.grep(r'"winemenubuilder.exe"=""', usr_reg):
        reg_file = os.path.join(config.WORKDIR, 'disable-winemenubuilder.reg')
        with open(reg_file, 'w') as f:
            f.write(r'''REGEDIT4

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"winemenubuilder.exe"=""
''')
        wine.wine_reg_install(reg_file)

    if not utils.grep(r'"renderer"="gdi"', usr_reg):
        wine.winetricks_install("-q", "settings", "renderer=gdi")

    if not config.SKIP_FONTS and not utils.grep(r'"Tahoma \(TrueType\)"="tahoma.ttf"', sys_reg):  # noqa: E501
        wine.installFonts()

    if not utils.grep(r'"\*d3dcompiler_47"="native"', usr_reg):
        wine.installD3DCompiler()

    if not utils.grep(r'"ProductName"="Microsoft Windows 10"', sys_reg):
        args = ["settings", "win10"]
        if not config.WINETRICKS_UNATTENDED:
            args.insert(0, "-q")
        wine.winetricks_install(*args)

    if config.TARGETVERSION == '9':
        msg.logos_msg(f"Setting {config.FLPRODUCT}Bible Indexing to Vista Mode.")
        exe_args = [
            'add',
            f"HKCU\\Software\\Wine\\AppDefaults\\{config.FLPRODUCT}Indexer.exe",  # noqa: E501
            "/v", "Version",
            "/t", "REG_SZ",
            "/d", "vista", "/f",
            ]
        wine.run_wine_proc(config.WINE_EXE, exe='reg', exe_args=exe_args)
    logging.debug("> Done.")


def ensure_product_installed(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_winetricks_applied(app=app)
    config.INSTALL_STEP += 1
    update_install_feedback("Ensuring product is installed…", app=app)

    if not utils.find_installed_product():
        wine.install_msi()
        config.LOGOS_EXE = utils.find_installed_product()
        utils.send_task(app, 'DONE')
        if config.DIALOG == 'curses':
            app.finished_e.wait()

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
        parent = Path.home() / ".config" / "Logos_on_Linux"
        parent.mkdir(exist_ok=True, parents=True)
        if parent.is_dir():
            utils.write_config(config.CONFIG_FILE)
            logging.info(f"A config file was created at {config.CONFIG_FILE}.")
        else:
            msg.logos_warn(f"{str(parent)} does not exist. Failed to create config file.")  # noqa: E501
    else:
        logging.info(f"Config file exists at {config.CONFIG_FILE}.")
        # Compare existing config file contents with installer config.
        logging.info("Comparing its contents with current config.")
        current_config_file_dict = config.get_config_file_dict(config.CONFIG_FILE)  # noqa: E501
        different = False
        for key in config.core_config_keys:
            if current_config_file_dict.get(key) != config.__dict__.get(key):
                different = True
                break
        if different:
            if app:
                utils.send_task(app, 'CONFIG')
                if config.DIALOG == 'curses':
                    app.config_e.wait()
                    choice = app.config_q.get()
                    if choice == "Yes":
                        logging.info("Updating config file.")
                        utils.write_config(config.CONFIG_FILE)
                    else:
                        logging.info("Config file left unchanged.")
            elif msg.logos_acknowledge_question(
                f"Update config file at {config.CONFIG_FILE}?",
                "The existing config file was not overwritten."
            ):
                logging.info("Updating config file.")
                utils.write_config(config.CONFIG_FILE)
    utils.send_task(app, "TUI-UPDATE-MENU")
    logging.debug(f"> File exists?: {config.CONFIG_FILE}: {Path(config.CONFIG_FILE).is_file()}")  # noqa: E501


def ensure_launcher_executable(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_config_file(app=app)
    config.INSTALL_STEP += 1
    runmode = utils.get_runmode()
    if runmode != 'binary':
        return
    update_install_feedback(
        f"Copying launcher to {config.INSTALLDIR}…",
        app=app
    )

    # Copy executable to config.INSTALLDIR.
    launcher_exe = Path(f"{config.INSTALLDIR}/LogosLinuxInstaller")
    if launcher_exe.is_file():
        logging.debug("Removing existing launcher binary.")
        launcher_exe.unlink()
    logging.info(f"Creating launcher binary by copying this installer binary to {launcher_exe}.")  # noqa: E501
    shutil.copy(sys.executable, launcher_exe)
    logging.debug(f"> File exists?: {launcher_exe}: {launcher_exe.is_file()}")  # noqa: E501


def ensure_launcher_shortcuts(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_launcher_executable(app=app)
    config.INSTALL_STEP += 1
    runmode = utils.get_runmode()
    if runmode != 'binary':
        return
    update_install_feedback("Creating launcher shortcuts…", app=app)

    app_dir = Path(config.INSTALLDIR) / 'data'
    logos_icon_path = app_dir / config.LOGOS_ICON_FILENAME  # noqa: E501
    if not logos_icon_path.is_file():
        app_dir.mkdir(exist_ok=True)
        shutil.copy(config.LOGOS_ICON_URL, logos_icon_path)
    else:
        logging.info(f"Icon found at {logos_icon_path}.")

    desktop_files = [
        (
            f"{config.FLPRODUCT}Bible.desktop",
            f"""[Desktop Entry]
Name={config.FLPRODUCT}Bible
Comment=A Bible Study Library with Built-In Tools
Exec={config.INSTALLDIR}/LogosLinuxInstaller --run-installed-app
Icon={str(logos_icon_path)}
Terminal=false
Type=Application
Categories=Education;
"""
        ),
        (
            f"{config.FLPRODUCT}Bible-ControlPanel.desktop",
            f"""[Desktop Entry]
Name={config.FLPRODUCT}Bible Control Panel
Comment=Perform various tasks for {config.FLPRODUCT} app
Exec={config.INSTALLDIR}/LogosLinuxInstaller
Icon={str(logos_icon_path)}
Terminal=false
Type=Application
Categories=Education;
"""
        ),
    ]
    for f, c in desktop_files:
        create_desktop_file(f, c)
        fpath = Path.home() / '.local' / 'share' / 'applications' / f
        logging.debug(f"> File exists?: {fpath}: {fpath.is_file()}")


def update_install_feedback(text, app=None):
    percent = get_progress_pct(config.INSTALL_STEP, config.INSTALL_STEPS_COUNT)
    logging.debug(f"Install step {config.INSTALL_STEP} of {config.INSTALL_STEPS_COUNT}")  # noqa: E501
    msg.status(text, app=app)
    msg.progress(percent, app=app)


def get_progress_pct(current, total):
    return round(current * 100 / total)


def create_desktop_file(name, contents):
    launcher_path = Path(f"~/.local/share/applications/{name}").expanduser()
    if launcher_path.is_file():
        logging.info(f"Removing desktop launcher at {launcher_path}.")
        launcher_path.unlink()

    logging.info(f"Creating desktop launcher at {launcher_path}.")
    with launcher_path.open('w') as f:
        f.write(contents)
    os.chmod(launcher_path, 0o755)
