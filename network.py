import hashlib
import json
import logging
import os
import queue
import requests
import shutil
import sys
import threading
from base64 import b64encode
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import config
import msg
import utils


class Props():
    def __init__(self, uri=None):
        self.path = None
        self.size = None
        self.md5 = None
        if uri is not None:
            self.path = uri


class FileProps(Props):
    def __init__(self, f=None):
        super().__init__(f)
        if f is not None:
            self.path = Path(self.path)
            if self.path.is_file():
                self.get_size()
                # self.get_md5()

    def get_size(self):
        if self.path is None:
            return
        self.size = self.path.stat().st_size
        return self.size

    def get_md5(self):
        if self.path is None:
            return
        md5 = hashlib.md5()
        with self.path.open('rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                md5.update(chunk)
        self.md5 = b64encode(md5.digest()).decode('utf-8')
        logging.debug(f"{str(self.path)} MD5: {self.md5}")
        return self.md5


class UrlProps(Props):
    def __init__(self, url=None):
        super().__init__(url)
        self.headers = None
        if url is not None:
            self.get_headers()
            self.get_size()
            self.get_md5()

    def get_headers(self):
        if self.path is None:
            self.headers = None
        logging.debug(f"Getting headers from {self.path}.")
        try:
            h = {'Accept-Encoding': 'identity'}  # force non-compressed txfr
            r = requests.head(self.path, allow_redirects=True, headers=h)
        except requests.exceptions.ConnectionError:
            logging.critical("Failed to connect to the server.")
            return None
        except Exception as e:
            logging.error(e)
            return None
        except KeyboardInterrupt:
            print()
            msg.logos_error("Interrupted by Ctrl+C")
            return None
        self.headers = r.headers
        return self.headers

    def get_size(self):
        if self.headers is None:
            r = self.get_headers()
            if r is None:
                return
        content_length = self.headers.get('Content-Length')
        content_encoding = self.headers.get('Content-Encoding')
        if content_encoding is not None:
            logging.critical(f"The server requires receiving the file compressed as '{content_encoding}'.")  # noqa: E501
        logging.debug(f"{content_length=}")
        if content_length is not None:
            self.size = int(content_length)
        return self.size

    def get_md5(self):
        if self.headers is None:
            r = self.get_headers()
            if r is None:
                return
        if self.headers.get('server') == 'AmazonS3':
            content_md5 = self.headers.get('etag')
            if content_md5 is not None:
                # Convert from hex to base64
                content_md5_hex = content_md5.strip('"').strip("'")
                content_md5 = b64encode(bytes.fromhex(content_md5_hex)).decode()  # noqa: E501
        else:
            content_md5 = self.headers.get('Content-MD5')
        if content_md5 is not None:
            content_md5 = content_md5.strip('"').strip("'")
        logging.debug(f"{content_md5=}")
        if content_md5 is not None:
            self.md5 = content_md5
        return self.md5


def cli_download(uri, destination):
    message = f"Downloading '{uri}' to '{destination}'"
    logging.info(message)
    msg.logos_msg(message)

    # Set target.
    if destination != destination.rstrip('/'):
        target = os.path.join(destination, os.path.basename(uri))
        if not os.path.isdir(destination):
            os.makedirs(destination)
    elif os.path.isdir(destination):
        target = os.path.join(destination, os.path.basename(uri))
    else:
        target = destination
        dirname = os.path.dirname(destination)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)

    # Download from uri in thread while showing progress bar.
    cli_queue = queue.Queue()
    args = [uri]
    kwargs = {'q': cli_queue, 'target': target}
    t = threading.Thread(target=net_get, args=args, kwargs=kwargs, daemon=True)
    t.start()
    try:
        while t.is_alive():
            if cli_queue.empty():
                continue
            utils.write_progress_bar(cli_queue.get())
        print()
    except KeyboardInterrupt:
        print()
        msg.logos_error('Interrupted with Ctrl+C')


def logos_reuse_download(
    SOURCEURL,
    FILE,
    TARGETDIR,
    app=None,
):
    DIRS = [
        config.INSTALLDIR,
        os.getcwd(),
        config.MYDOWNLOADS,
    ]
    FOUND = 1
    for i in DIRS:
        if i is not None:
            logging.debug(f"Checking {i} for {FILE}.")
            file_path = Path(i) / FILE
            if os.path.isfile(file_path):
                logging.info(f"{FILE} exists in {i}. Verifying properties.")
                if verify_downloaded_file(
                    SOURCEURL,
                    file_path,
                    app=app,
                ):
                    logging.info(f"{FILE} properties match. Using it…")
                    msg.logos_msg(f"Copying {FILE} into {TARGETDIR}")
                    try:
                        shutil.copy(os.path.join(i, FILE), TARGETDIR)
                    except shutil.SameFileError:
                        pass
                    FOUND = 0
                    break
                else:
                    logging.info(f"Incomplete file: {file_path}.")
    if FOUND == 1:
        file_path = os.path.join(config.MYDOWNLOADS, FILE)
        if config.DIALOG == 'tk' and app:
            # Ensure progress bar.
            app.stop_indeterminate_progress()
            # Start download.
            net_get(
                SOURCEURL,
                target=file_path,
                app=app,
            )
        else:
            cli_download(SOURCEURL, file_path)
        if verify_downloaded_file(
            SOURCEURL,
            file_path,
            app=app,
        ):
            msg.logos_msg(f"Copying: {FILE} into: {TARGETDIR}")
            try:
                shutil.copy(os.path.join(config.MYDOWNLOADS, FILE), TARGETDIR)
            except shutil.SameFileError:
                pass
        else:
            msg.logos_error(f"Bad file size or checksum: {file_path}")


def net_get(url, target=None, app=None, evt=None, q=None):

    # TODO:
    # - Check available disk space before starting download
    logging.debug(f"Download source: {url}")
    logging.debug(f"Download destination: {target}")
    target = FileProps(target)  # sets path and size attribs
    if app and target.path:
        app.status_q.put(f"Downloading {target.path.name}…")  # noqa: E501
        app.root.event_generate('<<UpdateStatus>>')
    parsed_url = urlparse(url)
    domain = parsed_url.netloc  # Gets the requested domain
    url = UrlProps(url)  # uses requests to set headers, size, md5 attribs
    if url.headers is None:
        logging.critical("Could not get headers.")
        return None

    # Initialize variables.
    local_size = 0
    total_size = url.size  # None or int
    logging.debug(f"File size on server: {total_size}")
    percent = None
    chunk_size = 100 * 1024  # 100 KB default
    if type(total_size) is int:
        # Use smaller of 2% of filesize or 2 MB for chunk_size.
        chunk_size = min([int(total_size / 50), 2 * 1024 * 1024])
    # Force non-compressed file transfer for accurate progress tracking.
    headers = {'Accept-Encoding': 'identity'}
    file_mode = 'wb'

    # If file exists and URL is resumable, set download Range.
    if target.path is not None and target.path.is_file():
        logging.debug(f"File exists: {str(target.path)}")
        local_size = target.get_size()
        logging.info(f"Current downloaded size in bytes: {local_size}")
        if url.headers.get('Accept-Ranges') == 'bytes':
            logging.debug("Server accepts byte range; attempting to resume download.")  # noqa: E501
            file_mode = 'ab'
            if type(url.size) is int:
                headers['Range'] = f'bytes={local_size}-{total_size}'
            else:
                headers['Range'] = f'bytes={local_size}-'

    logging.debug(f"{chunk_size=}; {file_mode=}; {headers=}")

    # Log download type.
    if 'Range' in headers.keys():
        message = f"Continuing download for {url.path}."
    else:
        message = f"Starting new download for {url.path}."
    logging.info(message)

    # Initiate download request.
    try:
        if target.path is None:  # return url content as text
            with requests.get(url.path, headers=headers) as r:
                if callable(r):
                    logging.error("Failed to retrieve data from the URL.")
                    return None

                try:
                    r.raise_for_status()
                except requests.exceptions.HTTPError as e:
                    if domain == "github.com":
                        if (
                            e.response.status_code == 403
                            or e.response.status_code == 429
                        ):
                            logging.error("GitHub API rate limit exceeded. Please wait before trying again.")  # noqa: E501
                    else:
                        logging.error(f"HTTP error occurred: {e.response.status_code}")  # noqa: E501
                    return None

                return r._content  # raw bytes
        else:  # download url to target.path
            with requests.get(url.path, stream=True, headers=headers) as r:
                with target.path.open(mode=file_mode) as f:
                    if file_mode == 'wb':
                        mode_text = 'Writing'
                    else:
                        mode_text = 'Appending'
                    logging.debug(f"{mode_text} data to file {target.path}.")
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        f.write(chunk)
                        local_size = target.get_size()
                        if type(total_size) is int:
                            percent = round(local_size / total_size * 100)
                            # if None not in [app, evt]:
                            if app:
                                # Send progress value to tk window.
                                app.get_q.put(percent)
                                if not evt:
                                    evt = app.get_evt
                                app.root.event_generate(evt)
                            elif q is not None:
                                # Send progress value to queue param.
                                q.put(percent)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error occurred during HTTP request: {e}")
        return None  # Return None values to indicate an error condition
    except Exception as e:
        msg.logos_error(e)
    except KeyboardInterrupt:
        print()
        msg.logos_error("Killed with Ctrl+C")


def verify_downloaded_file(url, file_path, app=None, evt=None):
    if app:
        msg.status(f"Verifying {file_path}…", app)
        if config.DIALOG == "tk":
            app.root.event_generate('<<StartIndeterminateProgress>>')
            app.status_q.put(f"Verifying {file_path}…")
            app.root.event_generate('<<UpdateStatus>>')
    res = False
    txt = f"{file_path} is the wrong size."
    right_size = same_size(url, file_path)
    if right_size:
        txt = f"{file_path} has the wrong MD5 sum."
        right_md5 = same_md5(url, file_path)
        if right_md5:
            txt = f"{file_path} is verified."
            res = True
    logging.info(txt)
    if app:
        if config.DIALOG == "tk":
            if not evt:
                evt = app.check_evt
            app.root.event_generate(evt)
    return res


def same_md5(url, file_path):
    logging.debug(f"Comparing MD5 of {url} and {file_path}.")
    url_md5 = UrlProps(url).get_md5()
    logging.debug(f"{url_md5=}")
    if url_md5 is None:  # skip MD5 check if not provided with URL
        res = True
    else:
        file_md5 = FileProps(file_path).get_md5()
        logging.debug(f"{file_md5=}")
        res = url_md5 == file_md5
    return res


def same_size(url, file_path):
    logging.debug(f"Comparing size of {url} and {file_path}.")
    url_size = UrlProps(url).size
    if not url_size:
        return True
    file_size = FileProps(file_path).size
    logging.debug(f"{url_size=} B; {file_size=} B")
    res = url_size == file_size
    return res


def get_latest_release_data(releases_url):
    data = net_get(releases_url)
    if data:
        try:
            json_data = json.loads(data.decode())
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON response: {e}")
            return None

        if not isinstance(json_data, list) or len(json_data) == 0:
            logging.error("Invalid or empty JSON response.")
            return None
        else:
            return json_data
    else:
        logging.critical("Could not get latest release URL.")
        return None


def get_latest_release_url(json_data):
    release_url = None
    if json_data:
        release_url = json_data[0].get('assets')[0].get('browser_download_url')  # noqa: E501
        logging.info(f"Release URL: {release_url}")
    return release_url


def get_latest_release_version_tag_name(json_data):
    release_tag_name = None
    if json_data:
        release_tag_name = json_data[0].get('tag_name')  # noqa: E501
        logging.info(f"Release URL Tag Name: {release_tag_name}")
    return release_tag_name


def set_logoslinuxinstaller_latest_release_config():
    releases_url = "https://api.github.com/repos/FaithLife-Community/LogosLinuxInstaller/releases"  # noqa: E501
    json_data = get_latest_release_data(releases_url)
    logoslinuxinstaller_url = get_latest_release_url(json_data)
    logoslinuxinstaller_tag_name = get_latest_release_version_tag_name(json_data)  # noqa: E501
    if logoslinuxinstaller_url is None:
        logging.critical("Unable to set LogosLinuxInstaller release without URL.")  # noqa: E501
        return
    config.LOGOS_LATEST_VERSION_URL = logoslinuxinstaller_url
    config.LOGOS_LATEST_VERSION_FILENAME = os.path.basename(logoslinuxinstaller_url)  # noqa: #501
    # Getting version relies on the the tag_name field in the JSON data. This
    # is already parsed down to vX.X.X. Therefore we must strip the v.
    config.LLI_LATEST_VERSION = logoslinuxinstaller_tag_name.lstrip('v')
    logging.info(f"{config.LLI_LATEST_VERSION}")


def set_recommended_appimage_config():
    releases_url = "https://api.github.com/repos/FaithLife-Community/wine-appimages/releases"  # noqa: E501
    if not config.RECOMMENDED_WINE64_APPIMAGE_URL:
        json_data = get_latest_release_data(releases_url)
        appimage_url = get_latest_release_url(json_data)
        if appimage_url is None:
            logging.critical("Unable to set recommended appimage config without URL.")  # noqa: E501
            return
        config.RECOMMENDED_WINE64_APPIMAGE_URL = appimage_url
    config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME = os.path.basename(config.RECOMMENDED_WINE64_APPIMAGE_URL)  # noqa: E501
    config.RECOMMENDED_WINE64_APPIMAGE_FILENAME = config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME.split(".AppImage")[0]  # noqa: E501
    # Getting version and branch rely on the filename having this format:
    #   wine-[branch]_[version]-[arch]
    parts = config.RECOMMENDED_WINE64_APPIMAGE_FILENAME.split('-')
    branch_version = parts[1]
    branch, version = branch_version.split('_')
    config.RECOMMENDED_WINE64_APPIMAGE_FULL_VERSION = f"v{version}-{branch}"
    config.RECOMMENDED_WINE64_APPIMAGE_VERSION = f"{version}"
    config.RECOMMENDED_WINE64_APPIMAGE_BRANCH = f"{branch}"


def check_for_updates():
    # We limit the number of times set_recommended_appimage_config is run in
    # order to avoid GitHub API limits. This sets the check to once every 12
    # hours.

    config.current_logos_version = utils.get_current_logos_version()
    utils.write_config(config.CONFIG_FILE)

    # TODO: Check for New Logos Versions. See #116.

    now = datetime.now().replace(microsecond=0)
    if config.CHECK_UPDATES:
        check_again = now
    elif config.LAST_UPDATED is not None:
        check_again = datetime.strptime(
            config.LAST_UPDATED.strip(),
            '%Y-%m-%dT%H:%M:%S'
        )
        check_again += timedelta(hours=12)
    else:
        check_again = now

    if now >= check_again:
        logging.debug("Running self-update.")

        set_logoslinuxinstaller_latest_release_config()
        set_recommended_appimage_config()

        config.LAST_UPDATED = now.isoformat()
        utils.write_config(config.CONFIG_FILE)
    else:
        logging.debug("Skipping self-update.")


def get_recommended_appimage():
    wine64_appimage_full_filename = Path(config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME)  # noqa: E501
    dest_path = Path(config.APPDIR_BINDIR) / wine64_appimage_full_filename
    if dest_path.is_file():
        return
    else:
        logos_reuse_download(
            config.RECOMMENDED_WINE64_APPIMAGE_URL,
            config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME,
            config.APPDIR_BINDIR)


def get_logos_releases(app=None):
    # Use already-downloaded list if requested again.
    downloaded_releases = None
    if config.TARGETVERSION == '9' and config.LOGOS9_RELEASES:
        downloaded_releases = config.LOGOS9_RELEASES
    elif config.TARGETVERSION == '10' and config.LOGOS10_RELEASES:
        downloaded_releases = config.LOGOS10_RELEASES
    if downloaded_releases:
        logging.debug(f"Using already-downloaded list of v{config.TARGETVERSION} releases")  # noqa: E501
        if app:
            app.releases_q.put(downloaded_releases)
            app.root.event_generate(app.release_evt)
        return downloaded_releases

    msg.logos_msg(f"Downloading release list for {config.FLPRODUCT} {config.TARGETVERSION}…")  # noqa: E501
    # NOTE: This assumes that Verbum release numbers continue to mirror Logos.
    url = f"https://clientservices.logos.com/update/v1/feed/logos{config.TARGETVERSION}/stable.xml"  # noqa: E501

    response_xml_bytes = net_get(url)
    # if response_xml is None and None not in [q, app]:
    if response_xml_bytes is None:
        if app:
            app.releases_q.put(None)
            if config.DIALOG == 'tk':
                app.root.event_generate(app.release_evt)
        return None

    # Parse XML
    root = ET.fromstring(response_xml_bytes.decode('utf-8-sig'))

    # Define namespaces
    namespaces = {
        'ns0': 'http://www.w3.org/2005/Atom',
        'ns1': 'http://services.logos.com/update/v1/'
    }

    # Extract versions
    releases = []
    # Obtain all listed releases.
    for entry in root.findall('.//ns1:version', namespaces):
        release = entry.text
        releases.append(release)
        # if len(releases) == 5:
        #    break

    filtered_releases = utils.filter_versions(releases, 36, 1)
    logging.debug(f"Available releases: {', '.join(releases)}")
    logging.debug(f"Filtered releases: {', '.join(filtered_releases)}")

    if app:
        app.releases_q.put(filtered_releases)
        if config.DIALOG == 'tk':
            app.root.event_generate(app.release_evt)
        elif config.DIALOG == 'curses':
            app.releases_e.set()
    return filtered_releases


def update_lli_binary(app=None):
    lli_file_path = os.path.realpath(sys.argv[0])
    lli_download_path = Path(config.MYDOWNLOADS) / "LogosLinuxInstaller"
    temp_path = Path(config.MYDOWNLOADS) / "LogosLinuxInstaller.tmp"
    logging.debug(
        f"Updating Logos Linux Installer to latest version by overwriting: {lli_file_path}")  # noqa: E501

    # Remove existing downloaded file if different version.
    if lli_download_path.is_file():
        logging.info("Checking if existing LLI binary is latest version.")
        lli_download_ver = utils.get_lli_release_version(lli_download_path)
        if not lli_download_ver or lli_download_ver != config.LLI_LATEST_VERSION:  # noqa: E501
            logging.info(f"Removing \"{lli_download_path}\", version: {lli_download_ver}")  # noqa: E501
            # Remove incompatible file.
            lli_download_path.unlink()

    logos_reuse_download(
        config.LOGOS_LATEST_VERSION_URL,
        "LogosLinuxInstaller",
        config.MYDOWNLOADS,
        app=app,
    )
    shutil.copy(lli_download_path, temp_path)
    try:
        shutil.move(temp_path, lli_file_path)
    except Exception as e:
        logging.error(f"Failed to replace the binary: {e}")
        return

    os.chmod(sys.argv[0], os.stat(sys.argv[0]).st_mode | 0o111)
    logging.debug("Successfully updated Logos Linux Installer.")
    utils.restart_lli()
