from pathlib import Path

from . import dbs
from . import utils as userutils


def get_updates_data(logos_dir, user_id):
    updates_db = dbs.get_updates_db(logos_dir, user_id)
    catalog_db = dbs.get_catalog_db(logos_dir, user_id)
    resource_mgr_db = dbs.get_resource_mgr_db(logos_dir, user_id)
    available_updates = list_available_updates(updates_db)
    updates_data = []
    for row in available_updates:
        resource_id = row[0]
        url = row[4]
        size_int = row[5]
        record_id = dbs.get_record_id(catalog_db, resource_id)
        title = dbs.get_resource_title(catalog_db, record_id)
        # Get destination path.
        db_path = dbs.get_destination_path(resource_mgr_db, resource_id)
        logos_subpath = userutils.wine_path_to_logos_subpath(db_path)
        dest_path = Path(logos_dir) / logos_subpath
        updates_data.append(
            {
                'resource_id': resource_id,
                'title': title,
                'size': size_int,
                'url': url,
                'dest_path': dest_path,
            }
        )
    updates_data.sort(key=lambda x: x.get('title'))
    return updates_data


def list_available_updates(updates_db):
    updates = dbs.query_db(
        updates_db,
        "select * from Resources where LocalVersion != ServerVersion"
    )
    updates.sort()
    return updates
