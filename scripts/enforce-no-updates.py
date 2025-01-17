import sqlite3
from threading import Thread
from time import sleep
from typing import Optional
import inotify.adapters
from pathlib import Path

def find_logos_folder(wine_prefix: Path) -> Optional[Path]:
    glob = './data/wine64_bottle/drive_c/users/*/AppData/Local/Logos/'
    results = list(wine_prefix.glob(glob))
    if len(results) > 0:
        return results[0]
    return None


def find_logos_user_folder(wine_prefix: Path, folder: str) -> Optional[Path]:
    logos_folder = find_logos_folder(wine_prefix)
    if logos_folder is None:
        return None
    results = list(logos_folder.glob(f'./{folder}/*'))
    if len(results) > 0:
        return results[0]
    return None


def watch_db(path: str, sql_statements: list[str]) -> Thread:
    i = inotify.adapters.Inotify()
    i.add_watch(path)

    def execute_sql(cur):
        print(f"Executing statements: {sql_statements}")
        for statement in sql_statements:
            try:
                cur.execute(statement)
            # Database may be locked, keep trying later.
            except sqlite3.OperationalError:
                pass

    def handle_events():
        con = sqlite3.connect(path, autocommit=True)
        cur = con.cursor()

        # Execute once before we start the loop
        execute_sql(cur)
        swallow_one = True

        # Keep track of if we've added -wal and -shm are added yet
        # They may not exist when we start
        watching_wal_and_shm = False
        for event in i.event_gen(yield_nones=False):
            (_, type_names, _, _) = event
            # These files may not exist when it's executes for the first time
            if (
                not watching_wal_and_shm
                and Path(path + "-wal").exists()
                and Path(path + "-shm").exists()
            ):
                i.add_watch(path + "-wal")
                i.add_watch(path + "-shm")
                watching_wal_and_shm = True

            # print(f"Got inotify event: {event}")
            if 'IN_MODIFY' in type_names or 'IN_CLOSE_WRITE' in type_names:
                # XXX: this swallowing of one may not work with the -wal/-shm added as events too
                # Check to make sure that we aren't responding to our own write
                if swallow_one:
                    # print("Swallowed one inotify event")
                    swallow_one = False
                    continue
                execute_sql(cur)
                swallow_one = True
        # Shouldn't be possible to get here, but on the off-chance it happens, 
        # we'd like to know and cleanup
        print(f"Stopped watching {path}")
        cur.close()
        con.close()
    thread = Thread(target=handle_events, daemon=True)
    thread.start()
    return thread


# Setting for auto-download is found under: find_logos_user_folder(wine_prefix, 'Documents') / 'LocalUserPreferences/PreferencesManager.db'
# 
def disable_auto_download(wine_prefix: Path):
    logos_documents_folder = find_logos_user_folder(wine_prefix, 'Documents')
    if logos_documents_folder is None:
        raise Exception("Could not find logos documents folder")
    db_path = logos_documents_folder / 'LocalUserPreferences/PreferencesManager.db'
    sql = """UPDATE Preferences SET Data='<data OptIn="false" StartDownloadHour="0" StopDownloadHour="0" MarkNewResourcesAsCloud="true" />' WHERE Type='UpdateManagerPreferences'""" #noqa: E501
    watch_db(str(db_path), [sql])


# Installer is written to find_logos_user_folder(wine_prefix, 'Data') / 'UpdateManager/Installers/1/Logos-x64.msi'

# UpdateManager settings find_logos_user_folder(wine_prefix, 'Data') / 'UpdateManager/Updates.db'
# DELETE FROM Installers WHERE 1; DELETE FROM Updates WHERE Source='Application Update'
def remove_updates_from_db(wine_prefix: Path):
    logos_data_folder = find_logos_user_folder(wine_prefix, 'Data')
    if logos_data_folder is None:
        raise Exception("Could not find logos data folder")
    db_path = logos_data_folder / 'UpdateManager/Updates.db'
    sql = [
        "DELETE FROM Installers WHERE 1",
        "DELETE FROM Updates WHERE Source='Application Update'"
    ]
    watch_db(str(db_path), sql)


def _main():
    wine_prefix = Path('/home/user/LogosBible10_temp')
    if not wine_prefix.exists():
        raise Exception("Wine Prefix does not exist")
    remove_updates_from_db(wine_prefix)
    disable_auto_download(wine_prefix)
    # Loop forever
    while True:
        sleep(100000)

if __name__ == '__main__':
    _main()