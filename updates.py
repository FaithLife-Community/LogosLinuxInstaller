from pathlib import Path

import config
from user import resource_updates
from user import login
from utils import logos_reuse_download


def get_available_updates(app=None):
    logos_dir = Path(config.LOGOS_EXE).expanduser().parent
    user_id = login.get_first_user_id(logos_dir)
    updates_data = resource_updates.get_updates_data(logos_dir, user_id)
    # NOTE: Quick operation, no thread or queue needed.
    # if app:
    #     app.updates_q.put(updates_data)
    # else:
    #     return updates_data
    return updates_data


def install_selected_updates(selected_updates, app=None):
    for u in selected_updates:
        update_resource(u, app=app)


def update_resource(update_data, app=None):
    dl_dir = Path('~/.local/state/Logos_on_Linux/updates').expanduser()
    dest_dir = update_data.get('dest_path').parent
    filename = update_data.get('dest_path').name
    if logos_reuse_download(
        update_data.get('url'),
        filename,
        dest_dir,
        app=app,
        download_dir=str(dl_dir)
    ):
        downloaded_file = dl_dir / filename
        downloaded_file.unlink()
