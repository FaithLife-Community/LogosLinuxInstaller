import logging
import os
import shutil
import sys
from pathlib import Path

from ou_dedetai.app import App

from . import config
from . import constants
from . import msg
from . import network
from . import system
from . import utils
from . import wine


# XXX: ideally this function wouldn't be needed, would happen automatically by nature of config accesses
def ensure_product_choice(app: App):
    app.installer_step_count += 1
    app.status("Choose product…")
    logging.debug('- config.FLPRODUCT')

    logging.debug(f"> config.FLPRODUCT={app.conf.faithlife_product}")


# XXX: we don't need this install step anymore
def ensure_version_choice(app: App):
    app.installer_step_count += 1
    ensure_product_choice(app=app)
    app.installer_step += 1
    app.status("Choose version…")
    logging.debug('- config.TARGETVERSION')
    # Accessing this ensures it's set
    logging.debug(f"> config.TARGETVERSION={app.conf.faithlife_product_version=}")


# XXX: no longer needed
def ensure_release_choice(app: App):
    app.installer_step_count += 1
    ensure_version_choice(app=app)
    app.installer_step += 1
    app.status("Choose product release…")
    logging.debug('- config.TARGET_RELEASE_VERSION')
    logging.debug(f"> config.TARGET_RELEASE_VERSION={app.conf.faithlife_product_release}")


def ensure_install_dir_choice(app: App):
    app.installer_step_count += 1
    ensure_release_choice(app=app)
    app.installer_step += 1
    app.status("Choose installation folder…")
    logging.debug('- config.INSTALLDIR')
    # Accessing this sets install_dir and bin_dir
    app.conf.install_dir
    logging.debug(f"> config.INSTALLDIR={app.conf.install_dir=}")
    logging.debug(f"> config.APPDIR_BINDIR={app.conf.installer_binary_dir}")


def ensure_wine_choice(app: App):
    app.installer_step_count += 1
    ensure_install_dir_choice(app=app)
    app.installer_step += 1
    app.status("Choose wine binary…")
    logging.debug('- config.SELECTED_APPIMAGE_FILENAME')
    logging.debug('- config.RECOMMENDED_WINE64_APPIMAGE_URL')
    logging.debug('- config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME')
    logging.debug('- config.WINE_EXE')
    logging.debug('- config.WINEBIN_CODE')

    m = f"Preparing to process WINE_EXE. Currently set to: {app.conf.wine_binary}."  # noqa: E501
    logging.debug(m)

    logging.debug(f"> config.SELECTED_APPIMAGE_FILENAME={app.conf.wine_appimage_path}")
    logging.debug(f"> config.RECOMMENDED_WINE64_APPIMAGE_URL={app.conf.wine_appimage_recommended_url}") #noqa: E501
    logging.debug(f"> config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME={app.conf.wine_appimage_recommended_file_name}") # noqa: E501
    logging.debug(f"> config.WINEBIN_CODE={app.conf.wine_binary_code}")
    logging.debug(f"> {app.conf.wine_binary=}")


# XXX: this isn't needed anymore
def ensure_winetricks_choice(app: App):
    app.installer_step_count += 1
    ensure_wine_choice(app=app)
    app.installer_step += 1
    app.status("Choose winetricks binary…")
    logging.debug('- config.WINETRICKSBIN')
    # Accessing the winetricks_binary variable will do this.
    logging.debug(f"> config.WINETRICKSBIN={app.conf.winetricks_binary}")


# XXX: huh? What does this do?
def ensure_install_fonts_choice(app: App):
    app.installer_step_count += 1
    ensure_winetricks_choice(app=app)
    app.installer_step += 1
    app.status("Ensuring install fonts choice…")
    logging.debug('- config.SKIP_FONTS')

    logging.debug(f"> config.SKIP_FONTS={app.conf.skip_install_fonts}")


# XXX: huh? What does this do?
def ensure_check_sys_deps_choice(app: App):
    app.installer_step_count += 1
    ensure_install_fonts_choice(app=app)
    app.installer_step += 1
    app.status(
        "Ensuring check system dependencies choice…"
    )
    logging.debug('- config.SKIP_DEPENDENCIES')

    logging.debug(f"> config.SKIP_DEPENDENCIES={app.conf._overrides.winetricks_skip}")


# XXX: should this be it's own step? faithlife_product_version is asked
def ensure_installation_config(app: App):
    app.installer_step_count += 1
    ensure_check_sys_deps_choice(app=app)
    app.installer_step += 1
    app.status("Ensuring installation config is set…")
    logging.debug('- config.LOGOS_ICON_URL')
    logging.debug('- config.LOGOS_VERSION')
    logging.debug('- config.LOGOS64_URL')

    logging.debug(f"> config.LOGOS_ICON_URL={app.conf.faithlife_product_icon_path}")
    logging.debug(f"> config.LOGOS_VERSION={app.conf.faithlife_product_version}")
    logging.debug(f"> config.LOGOS64_URL={app.conf.faithlife_installer_download_url}")

    app._install_started_hook()
    app.status("Install is running…")


def ensure_install_dirs(app: App):
    app.installer_step_count += 1
    ensure_installation_config(app=app)
    app.installer_step += 1
    app.status("Ensuring installation directories…")
    logging.debug('- config.INSTALLDIR')
    logging.debug('- config.WINEPREFIX')
    logging.debug('- data/bin')
    logging.debug('- data/wine64_bottle')
    wine_dir = Path("")

    bin_dir = Path(app.conf.installer_binary_dir)
    bin_dir.mkdir(parents=True, exist_ok=True)
    logging.debug(f"> {bin_dir} exists?: {bin_dir.is_dir()}")

    logging.debug(f"> config.INSTALLDIR={app.conf.installer_binary_dir}")
    logging.debug(f"> config.APPDIR_BINDIR={app.conf.installer_binary_dir}")

    wine_dir = Path(f"{app.conf.wine_prefix}")
    wine_dir.mkdir(parents=True, exist_ok=True)

    logging.debug(f"> {wine_dir} exists: {wine_dir.is_dir()}")
    logging.debug(f"> config.WINEPREFIX={app.conf.wine_prefix}")


def ensure_sys_deps(app: App):
    app.installer_step_count += 1
    ensure_install_dirs(app=app)
    app.installer_step += 1
    app.status("Ensuring system dependencies are met…")

    if not app.conf.skip_install_system_dependencies:
        utils.install_dependencies(app)
        logging.debug("> Done.")
    else:
        logging.debug("> Skipped.")


def ensure_appimage_download(app: App):
    app.installer_step_count += 1
    ensure_sys_deps(app=app)
    app.installer_step += 1
    if app.conf.faithlife_product_version != '9' and not str(app.conf.wine_binary).lower().endswith('appimage'):  # noqa: E501
        return
    app.status("Ensuring wine AppImage is downloaded…")

    downloaded_file = None
    appimage_path = app.conf.wine_appimage_path or app.conf.wine_appimage_recommended_file_name #noqa: E501
    filename = Path(appimage_path).name
    downloaded_file = utils.get_downloaded_file_path(app.conf.download_dir, filename)
    if not downloaded_file:
        downloaded_file = Path(f"{app.conf.download_dir}/{filename}")
    network.logos_reuse_download(
        app.conf.wine_appimage_recommended_url,
        filename,
        app.conf.download_dir,
        app=app,
    )
    if downloaded_file:
        logging.debug(f"> File exists?: {downloaded_file}: {Path(downloaded_file).is_file()}")  # noqa: E501


def ensure_wine_executables(app: App):
    app.installer_step_count += 1
    ensure_appimage_download(app=app)
    app.installer_step += 1
    app.status("Ensuring wine executables are available…")
    logging.debug('- config.WINESERVER_EXE')
    logging.debug('- wine')
    logging.debug('- wine64')
    logging.debug('- wineserver')

    create_wine_appimage_symlinks(app=app)

    # PATH is modified if wine appimage isn't found, but it's not modified
    # during a restarted installation, so shutil.which doesn't find the
    # executables in that case.
    logging.debug(f"> wine path: {app.conf.wine_binary}")
    logging.debug(f"> wine64 path: {app.conf.wine64_binary}")
    logging.debug(f"> wineserver path: {app.conf.wineserver_binary}")
    logging.debug(f"> winetricks path: {app.conf.winetricks_binary}")


def ensure_winetricks_executable(app: App):
    app.installer_step_count += 1
    ensure_wine_executables(app=app)
    app.installer_step += 1
    app.status("Ensuring winetricks executable is available…")

    app.status("Downloading winetricks from the Internet…")
    system.install_winetricks(app.conf.installer_binary_dir, app=app)

    logging.debug(f"> {app.conf.winetricks_binary} is executable?: {os.access(app.conf.winetricks_binary, os.X_OK)}")  # noqa: E501
    return 0


def ensure_premade_winebottle_download(app: App):
    app.installer_step_count += 1
    ensure_winetricks_executable(app=app)
    app.installer_step += 1
    if app.conf.faithlife_product_version != '9':
        return
    app.status(f"Ensuring {constants.LOGOS9_WINE64_BOTTLE_TARGZ_NAME} bottle is downloaded…")  # noqa: E501

    downloaded_file = utils.get_downloaded_file_path(app.conf.download_dir, constants.LOGOS9_WINE64_BOTTLE_TARGZ_NAME)  # noqa: E501
    if not downloaded_file:
        downloaded_file = Path(app.conf.download_dir) / app.conf.faithlife_installer_name #noqa: E501
    network.logos_reuse_download(
        constants.LOGOS9_WINE64_BOTTLE_TARGZ_URL,
        constants.LOGOS9_WINE64_BOTTLE_TARGZ_NAME,
        app.conf.download_dir,
        app=app,
    )
    # Install bottle.
    bottle = Path(app.conf.wine_prefix)
    if not bottle.is_dir():
        # FIXME: this code seems to be logos 9 specific, why is it here?
        utils.install_premade_wine_bottle(
            app.conf.download_dir,
            f"{app.conf.install_dir}/data"
        )

    logging.debug(f"> '{downloaded_file}' exists?: {Path(downloaded_file).is_file()}")  # noqa: E501


def ensure_product_installer_download(app: App):
    app.installer_step_count += 1
    ensure_premade_winebottle_download(app=app)
    app.installer_step += 1
    app.status(f"Ensuring {app.conf.faithlife_product} installer is downloaded…")

    downloaded_file = utils.get_downloaded_file_path(app.conf.download_dir, app.conf.faithlife_installer_name) #noqa: E501
    if not downloaded_file:
        downloaded_file = Path(app.conf.download_dir) / app.conf.faithlife_installer_name #noqa: E501
    network.logos_reuse_download(
        app.conf.faithlife_installer_download_url,
        app.conf.faithlife_installer_name,
        app.conf.download_dir,
        app=app,
    )
    # Copy file into install dir.
    installer = Path(f"{app.conf.install_dir}/data/{app.conf.faithlife_installer_name}")
    if not installer.is_file():
        shutil.copy(downloaded_file, installer.parent)

    logging.debug(f"> '{downloaded_file}' exists?: {Path(downloaded_file).is_file()}")  # noqa: E501


def ensure_wineprefix_init(app: App):
    app.installer_step_count += 1
    ensure_product_installer_download(app=app)
    app.installer_step += 1
    app.status("Ensuring wineprefix is initialized…")

    init_file = Path(f"{app.conf.wine_prefix}/system.reg")
    logging.debug(f"{init_file=}")
    if not init_file.is_file():
        logging.debug(f"{init_file} does not exist")
        if app.conf.faithlife_product_version == '9':
            utils.install_premade_wine_bottle(
                app.conf.download_dir,
                f"{app.conf.install_dir}/data",
            )
        else:
            logging.debug("Initializing wineprefix.")
            process = wine.initializeWineBottle(app.conf.wine64_binary, app)
            system.wait_pid(process)
            # wine.light_wineserver_wait()
            wine.wineserver_wait(app)
            logging.debug("Wine init complete.")
    logging.debug(f"> {init_file} exists?: {init_file.is_file()}")


def ensure_winetricks_applied(app: App):
    app.installer_step_count += 1
    ensure_wineprefix_init(app=app)
    app.installer_step += 1
    app.status("Ensuring winetricks & other settings are applied…")
    logging.debug('- disable winemenubuilder')
    logging.debug('- settings renderer=gdi')
    logging.debug('- corefonts')
    logging.debug('- tahoma')
    logging.debug('- settings fontsmooth=rgb')
    logging.debug('- d3dcompiler_47')

    if not app.conf.skip_winetricks:
        usr_reg = None
        sys_reg = None
        usr_reg = Path(f"{app.conf.wine_prefix}/user.reg")
        sys_reg = Path(f"{app.conf.wine_prefix}/system.reg")

        # FIXME: consider supplying progresses to these sub-steps

        if not utils.grep(r'"winemenubuilder.exe"=""', usr_reg):
            app.status("Disabling winemenubuilder…")
            wine.disable_winemenubuilder(app, app.conf.wine64_binary)

        if not utils.grep(r'"renderer"="gdi"', usr_reg):
            app.status("Setting Renderer to GDI…")
            wine.set_renderer(app, "gdi")

        if not utils.grep(r'"FontSmoothingType"=dword:00000002', usr_reg):
            app.status("Setting Font Smooting to RGB…")
            wine.install_font_smoothing(app)

        if not app.conf.skip_install_fonts and not utils.grep(r'"Tahoma \(TrueType\)"="tahoma.ttf"', sys_reg):  # noqa: E501
            app.status("Installing fonts…")
            wine.install_fonts(app)

        if not utils.grep(r'"\*d3dcompiler_47"="native"', usr_reg):
            app.status("Installing D3D…")
            wine.install_d3d_compiler(app)

        if not utils.grep(r'"ProductName"="Microsoft Windows 10"', sys_reg):
            app.status(f"Setting {app.conf.faithlife_product} to Win10 Mode…")
            wine.set_win_version(app, "logos", "win10")

        # NOTE: Can't use utils.grep check here because the string
        # "Version"="win10" might appear elsewhere in the registry.
        app.status(f"Setting {app.conf.faithlife_product} Bible Indexing to Win10 Mode…")  # noqa: E501
        wine.set_win_version(app, "indexer", "win10")
        # wine.light_wineserver_wait()
        wine.wineserver_wait(app)
    logging.debug("> Done.")


def ensure_icu_data_files(app: App):
    app.installer_step_count += 1
    ensure_winetricks_applied(app=app)
    app.installer_step += 1
    app.status("Ensuring ICU data files are installed…")
    logging.debug('- ICU data files')

    wine.enforce_icu_data_files(app=app)

    logging.debug('> ICU data files installed')


def ensure_product_installed(app: App):
    app.installer_step_count += 1
    ensure_icu_data_files(app=app)
    app.installer_step += 1
    app.status(f"Ensuring {app.conf.faithlife_product} is installed…")

    if not app.is_installed():
        process = wine.install_msi(app)
        system.wait_pid(process)

    # Clean up temp files, etc.
    utils.clean_all()

    logging.debug(f"> Product path: config.LOGOS_EXE={app.conf.logos_exe}")


def ensure_config_file(app: App):
    app.installer_step_count += 1
    ensure_product_installed(app=app)
    app.installer_step += 1
    app.status("Ensuring config file is up-to-date…")

    app.status("Install has finished.", 100)

    app._install_complete_hook()


def ensure_launcher_executable(app: App):
    app.installer_step_count += 1
    ensure_config_file(app=app)
    app.installer_step += 1
    runmode = system.get_runmode()
    if runmode == 'binary':
        app.status(f"Copying launcher to {app.conf.install_dir}…")

        # Copy executable into install dir.
        launcher_exe = Path(f"{app.conf.install_dir}/{constants.BINARY_NAME}")
        if launcher_exe.is_file():
            logging.debug("Removing existing launcher binary.")
            launcher_exe.unlink()
        logging.info(f"Creating launcher binary by copying this installer binary to {launcher_exe}.")  # noqa: E501
        shutil.copy(sys.executable, launcher_exe)
        logging.debug(f"> File exists?: {launcher_exe}: {launcher_exe.is_file()}")  # noqa: E501
    else:
        app.status(
            "Running from source. Skipping launcher creation."
        )


def ensure_launcher_shortcuts(app: App):
    app.installer_step_count += 1
    ensure_launcher_executable(app=app)
    app.installer_step += 1
    app.status("Creating launcher shortcuts…")
    runmode = system.get_runmode()
    if runmode == 'binary':
        app.status("Creating launcher shortcuts…")
        create_launcher_shortcuts(app)
    else:
        # FIXME: Is this because it's hard to find the python binary?
        app.status(
            "Running from source. Skipping launcher creation.",
        )

def install(app: App):
    """Entrypoint for installing"""
    ensure_launcher_shortcuts(app)


def get_progress_pct(current, total):
    return round(current * 100 / total)


def create_wine_appimage_symlinks(app: App):
    app.status("Creating wine appimage symlinks…")
    appdir_bindir = Path(app.conf.installer_binary_dir)
    os.environ['PATH'] = f"{app.conf.installer_binary_dir}:{os.getenv('PATH')}"
    # Ensure AppImage symlink.
    appimage_link = appdir_bindir / app.conf.wine_appimage_link_file_name
    if app.conf.wine_binary_code not in ['AppImage', 'Recommended'] or app.conf.wine_appimage_path is None: #noqa: E501
        logging.debug("No need to symlink non-appimages")
        return

    appimage_file = Path(app.conf.wine_appimage_path)
    appimage_filename = Path(app.conf.wine_appimage_path).name
    # Ensure appimage is copied to appdir_bindir.
    downloaded_file = utils.get_downloaded_file_path(app.conf.download_dir, appimage_filename) #noqa: E501
    if downloaded_file is None:
        logging.critical("Failed to get a valid wine appimage")
        return
    if Path(downloaded_file).parent != appdir_bindir:
        app.status(f"Copying: {downloaded_file} into: {appdir_bindir}")
        shutil.copy(downloaded_file, appdir_bindir)
    os.chmod(appimage_file, 0o755)
    appimage_filename = appimage_file.name

    appimage_link.unlink(missing_ok=True)  # remove & replace
    appimage_link.symlink_to(f"./{appimage_filename}")

    # NOTE: if we symlink "winetricks" then the log is polluted with:
    # "Executing: cd /tmp/.mount_winet.../bin"
    (appdir_bindir / "winetricks").unlink(missing_ok=True)

    # Ensure wine executables symlinks.
    for name in ["wine", "wine64", "wineserver"]:
        p = appdir_bindir / name
        p.unlink(missing_ok=True)
        p.symlink_to(f"./{app.conf.wine_appimage_link_file_name}")


def create_desktop_file(name, contents):
    launcher_path = Path(f"~/.local/share/applications/{name}").expanduser()
    if launcher_path.is_file():
        logging.info(f"Removing desktop launcher at {launcher_path}.")
        launcher_path.unlink()
    # Ensure the parent directory exists
    launcher_path.parent.mkdir(parents=True, exist_ok=True)

    logging.info(f"Creating desktop launcher at {launcher_path}.")
    with launcher_path.open('w') as f:
        f.write(contents)
    os.chmod(launcher_path, 0o755)


def create_launcher_shortcuts(app: App):
    # Set variables for use in launcher files.
    flproduct = app.conf.faithlife_product
    installdir = Path(app.conf.install_dir)
    logos_icon_src = constants.APP_IMAGE_DIR / f"{flproduct}-128-icon.png"
    app_icon_src = constants.APP_IMAGE_DIR / 'icon.png'

    if not installdir.is_dir():
        app.exit("Can't create launchers because the installation folder does not exist.")
    app_dir = Path(installdir) / 'data'
    logos_icon_path = app_dir / logos_icon_src.name
    app_icon_path = app_dir / app_icon_src.name

    if system.get_runmode() == 'binary':
        lli_executable = f"{installdir}/{constants.BINARY_NAME}"
    else:
        script = Path(sys.argv[0]).expanduser().resolve()
        repo_dir = None
        for p in script.parents:
            for c in p.iterdir():
                if c.name == '.git':
                    repo_dir = p
                    break
        if repo_dir is None:
            app.exit("Could not find .git directory from arg 0")  # noqa: E501
        # Find python in virtual environment.
        py_bin = next(repo_dir.glob('*/bin/python'))
        if not py_bin.is_file():
            app.exit("Could not locate python binary in virtual environment.")  # noqa: E501
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
            f"{constants.BINARY_NAME}.desktop",
            f"""[Desktop Entry]
Name={constants.APP_NAME}
GenericName=FaithLife Wine App Installer
Comment=Manages FaithLife Bible Software via Wine
Exec={lli_executable}
Icon={app_icon_path}
Terminal=false
Type=Application
StartupWMClass={constants.BINARY_NAME}
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
