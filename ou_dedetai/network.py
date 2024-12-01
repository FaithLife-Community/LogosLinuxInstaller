import hashlib
import json
import logging
import os
import queue
from typing import Optional
import requests
import shutil
import sys
from base64 import b64encode
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from ou_dedetai import wine
from ou_dedetai.app import App

from . import config
from . import constants
from . import msg
from . import utils


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
            for chunk in iter(lambda: f.read(524288), b''):
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
        # XXX: should we have a more generic catch for KeyboardInterrupt rather than deep in this function? #noqa: E501
        # except KeyboardInterrupt:
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


def logos_reuse_download(
    sourceurl,
    file,
    targetdir,
    app: App,
):
    dirs = [
        app.conf.install_dir,
        os.getcwd(),
        app.conf.download_dir,
    ]
    found = 1
    for i in dirs:
        if i is not None:
            logging.debug(f"Checking {i} for {file}.")
            file_path = Path(i) / file
            if os.path.isfile(file_path):
                logging.info(f"{file} exists in {i}. Verifying properties.")
                if verify_downloaded_file(
                    sourceurl,
                    file_path,
                    app=app,
                ):
                    logging.info(f"{file} properties match. Using it…")
                    msg.status(f"Copying {file} into {targetdir}")
                    try:
                        shutil.copy(os.path.join(i, file), targetdir)
                    except shutil.SameFileError:
                        pass
                    found = 0
                    break
                else:
                    logging.info(f"Incomplete file: {file_path}.")
    if found == 1:
        file_path = os.path.join(app.conf.download_dir, file)
        # Start download.
        net_get(
            sourceurl,
            target=file_path,
            app=app,
        )
        if verify_downloaded_file(
            sourceurl,
            file_path,
            app=app,
        ):
            msg.status(f"Copying: {file} into: {targetdir}")
            try:
                shutil.copy(os.path.join(app.conf.download_dir, file), targetdir)
            except shutil.SameFileError:
                pass
        else:
            app.exit(f"Bad file size or checksum: {file_path}")


# FIXME: refactor to raise rather than return None
def net_get(url, target=None, app: Optional[App] = None, evt=None, q=None):
    # TODO:
    # - Check available disk space before starting download
    logging.debug(f"Download source: {url}")
    logging.debug(f"Download destination: {target}")
    target = FileProps(target)  # sets path and size attribs
    if app and target.path:
        app.status(f"Downloading {target.path.name}…")
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
                                # Send progress value to App
                                app.status("Downloading...", percent=percent)
                            elif q is not None:
                                # Send progress value to queue param.
                                q.put(percent)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error occurred during HTTP request: {e}")
        return None  # Return None values to indicate an error condition


def verify_downloaded_file(url, file_path, app: Optional[App]=None):
    if app:
        app.status(f"Verifying {file_path}…", 0)
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


def get_latest_release_data(repository):
    release_url = f"https://api.github.com/repos/{repository}/releases/latest"
    data = net_get(release_url)
    if data:
        try:
            json_data = json.loads(data.decode())
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON response: {e}")
            return None

        return json_data
    else:
        logging.critical("Could not get latest release URL.")
        return None


def get_first_asset_url(json_data) -> Optional[str]:
    release_url = None
    if json_data:
        # FIXME: Portential KeyError
        release_url = json_data.get('assets')[0].get('browser_download_url')
        logging.info(f"Release URL: {release_url}")
    return release_url


def get_tag_name(json_data) -> Optional[str]:
    tag_name = None
    if json_data:
        tag_name = json_data.get('tag_name')
        logging.info(f"Release URL Tag Name: {tag_name}")
    return tag_name


def get_oudedetai_latest_release_config(channel: str = "stable") -> tuple[str, str]:
    """Get latest release information
    
    Returns:
        url
        version
    """
    if channel == "stable":
        repo = "FaithLife-Community/LogosLinuxInstaller"
    else:
        repo = "FaithLife-Community/test-builds"
    json_data = get_latest_release_data(repo)
    oudedetai_url = get_first_asset_url(json_data)
    if oudedetai_url is None:
        logging.critical(f"Unable to set {constants.APP_NAME} release without URL.")  # noqa: E501
        raise ValueError("Failed to find latest installer version")
    # Getting version relies on the the tag_name field in the JSON data. This
    # is already parsed down to vX.X.X. Therefore we must strip the v.
    latest_version = get_tag_name(json_data).lstrip('v')
    logging.info(f"config.LLI_LATEST_VERSION={latest_version}")

    return oudedetai_url, latest_version


def get_recommended_appimage_url() -> str:
    repo = "FaithLife-Community/wine-appimages"
    json_data = get_latest_release_data(repo)
    appimage_url = get_first_asset_url(json_data)
    if appimage_url is None:
        # FIXME: changed this to raise an exception as we can't continue.
        raise ValueError("Unable to set recommended appimage config without URL.")  # noqa: E501
    return appimage_url


def get_recommended_appimage(app: App):
    wine64_appimage_full_filename = Path(app.conf.wine_appimage_recommended_file_name)  # noqa: E501
    dest_path = Path(app.conf.installer_binary_dir) / wine64_appimage_full_filename
    if dest_path.is_file():
        return
    else:
        logos_reuse_download(
            app.conf.wine_appimage_recommended_url,
            app.conf.wine_appimage_recommended_file_name,
            app.conf.installer_binary_dir,
            app=app
        )

def get_logos_releases(app: App) -> list[str]:
    # TODO: Use already-downloaded list if requested again.
    msg.status(f"Downloading release list for {app.conf.faithlife_product} {app.conf.faithlife_product_version}…")  # noqa: E501
    # NOTE: This assumes that Verbum release numbers continue to mirror Logos.
    if app.conf.faithlife_product_release_channel == "beta":
        url = "https://clientservices.logos.com/update/v1/feed/logos10/beta.xml"  # noqa: E501
    else:
        url = f"https://clientservices.logos.com/update/v1/feed/logos{app.conf.faithlife_product_version}/stable.xml"  # noqa: E501
    
    response_xml_bytes = net_get(url)
    if response_xml_bytes is None:
        raise Exception("Failed to get logos releases")

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

    # Disabled filtering: with Logos 30+, all versions are known to be working.
    # Keeping code if it needs to be reactivated.
    # filtered_releases = utils.filter_versions(releases, 36, 1)
    # logging.debug(f"Available releases: {', '.join(releases)}")
    # logging.debug(f"Filtered releases: {', '.join(filtered_releases)}")
    filtered_releases = releases

    return filtered_releases


def update_lli_binary(app: App):
    lli_file_path = os.path.realpath(sys.argv[0])
    lli_download_path = Path(app.conf.download_dir) / constants.BINARY_NAME
    temp_path = Path(app.conf.download_dir) / f"{constants.BINARY_NAME}.tmp"
    logging.debug(
        f"Updating {constants.APP_NAME} to latest version by overwriting: {lli_file_path}")  # noqa: E501

    # Remove existing downloaded file if different version.
    if lli_download_path.is_file():
        logging.info("Checking if existing LLI binary is latest version.")
        lli_download_ver = utils.get_lli_release_version(lli_download_path)
        if not lli_download_ver or lli_download_ver != app.conf.app_latest_version:  # noqa: E501
            logging.info(f"Removing \"{lli_download_path}\", version: {lli_download_ver}")  # noqa: E501
            # Remove incompatible file.
            lli_download_path.unlink()

    logos_reuse_download(
        app.conf.app_latest_version_url,
        constants.BINARY_NAME,
        app.conf.download_dir,
        app=app,
    )
    shutil.copy(lli_download_path, temp_path)
    try:
        shutil.move(temp_path, lli_file_path)
    except Exception as e:
        logging.error(f"Failed to replace the binary: {e}")
        return

    os.chmod(sys.argv[0], os.stat(sys.argv[0]).st_mode | 0o111)
    logging.debug(f"Successfully updated {constants.APP_NAME}.")
    utils.restart_lli()
