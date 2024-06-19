import sqlite3
from contextlib import closing


def query_db(db_filepath, query, variables=()):
    with closing(sqlite3.connect(db_filepath)) as connection:
        with closing(connection.cursor()) as cursor:
            if variables:
                rows = cursor.execute(query, variables).fetchall()
            else:
                rows = cursor.execute(query).fetchall()
            return rows


def get_db_from_path(db_path):
    return db_path if db_path.is_file() else None


def get_catalog_db(logos_dir, user_id):
    catalog_db_path = logos_dir / 'Data' / user_id / 'LibraryCatalog' / 'catalog.db'  # noqa: E501
    return get_db_from_path(catalog_db_path)


def get_resource_mgr_db(logos_dir, user_id):
    resource_mgr_db = logos_dir / 'Data' / user_id / 'ResourceManager' / 'ResourceManager.db'  # noqa: E501
    return get_db_from_path(resource_mgr_db)


def get_updates_db(logos_dir, user_id):
    updates_db_path = logos_dir / 'Data' / user_id / 'UpdateManager' / 'Updates.db'  # noqa: E501
    return get_db_from_path(updates_db_path)


def get_record_id(catalog_db, resource_id):
    record_id = None
    rows = query_db(
        catalog_db,
        "select RecordId, ResourceID from Records where ResourceId=?",
        variables=(resource_id,)
    )
    if len(rows) == 1:
        record_id = rows[0][0]
    return record_id


def get_resource_title(catalog_db, record_id):
    title = None
    rows = query_db(
        catalog_db,
        "select RecordId, Title from Records where RecordId=?",
        variables=(record_id,)
    )
    if len(rows) == 1:
        title = rows[0][1]
    return title


def get_destination_path(resource_mgr_db, resource_id):
    dest_path = None
    rows = query_db(
        resource_mgr_db,
        "select ResourceId, Location from Resources where ResourceId=?",
        variables=(resource_id,)

    )
    if len(rows) == 1:
        dest_path = rows[0][1]
    return dest_path
