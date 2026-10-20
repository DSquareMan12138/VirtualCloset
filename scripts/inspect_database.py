import sqlite3
from contextlib import closing
from virtual_closet.config import DB_PATH

if __name__ == '__main__':
    with closing(sqlite3.connect(DB_PATH.as_uri()+'?mode=ro',uri=True)) as con:
        for row in con.execute('''SELECT clothing_items.id, users.username, filename, attributes_json
            FROM clothing_items JOIN users ON users.id=clothing_items.user_id'''):
            print(row)
