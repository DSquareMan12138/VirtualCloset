import json
import sqlite3
from contextlib import contextmanager

from .config import DB_PATH, MODEL_ID, MODEL_VERSION
from .auth import normalize_username, hash_password, verify_password
from .metadata import clean_brand, saved_name
import re

@contextmanager
def connect(path=DB_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        with con:
            yield con
    finally:
        con.close()

def initialize(path=DB_PATH):
    with connect(path) as con:
        existing = con.execute("PRAGMA table_info(clothing_items)").fetchall()
        if existing and not any(r['name'] == 'embedding_json' for r in existing):
            raise RuntimeError("Old database detected. Use the new project folder; keep your old database as legacy_closet.db.")
        con.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS clothing_items (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            image_hash TEXT NOT NULL,
            image_data BLOB NOT NULL,
            attributes_json TEXT NOT NULL,
            rankings_json TEXT NOT NULL,
            embedding_json TEXT,
            model_id TEXT NOT NULL,
            model_version TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, image_hash)
        );
        ''')
        columns = {r["name"] for r in con.execute("PRAGMA table_info(clothing_items)")}
        additions = {"display_name": "TEXT", "brand": "TEXT",
                     "metadata_reviewed": "INTEGER NOT NULL DEFAULT 0", "cutout_data": "BLOB"}
        for name, definition in additions.items():
            if name not in columns:
                con.execute(f"ALTER TABLE clothing_items ADD COLUMN {name} {definition}")
        user_columns = {r["name"] for r in con.execute("PRAGMA table_info(users)")}
        if "background_color" not in user_columns:
            con.execute("ALTER TABLE users ADD COLUMN background_color TEXT NOT NULL DEFAULT '#ffffff'")
        con.execute("""UPDATE clothing_items SET display_name =
            CASE WHEN trim(filename) = '' THEN 'Clothing item' ELSE filename END
            WHERE display_name IS NULL OR trim(display_name) = ''""")

def register(username, password, path=DB_PATH):
    username = normalize_username(username)
    encoded = hash_password(password)

    with connect(path) as con:
        try:
            uid = con.execute(
                "INSERT INTO users(username,password_hash) VALUES (?,?)",
                (username, encoded),
            ).lastrowid
        except sqlite3.IntegrityError:
            raise ValueError("That username is already registered.") from None

        return {'id': uid, 'username': username}

def login(username, password, path=DB_PATH):
    with connect(path) as con:
        row = con.execute("SELECT * FROM users WHERE username=?", (username.strip().lower(),)).fetchone()
    # A dummy hash keeps the unknown-user path from skipping the expensive hash.
    dummy = 'pbkdf2_sha256$600000$' + '00'*16 + '$' + '00'*32
    valid = verify_password(password, row['password_hash'] if row else dummy)
    return {'id': row['id'], 'username': row['username']} if row and valid else None

def list_items(uid, path=DB_PATH):
    with connect(path) as con:
        return [dict(row) for row in con.execute("SELECT * FROM clothing_items WHERE user_id=? ORDER BY id DESC", (uid,))]

def exists(uid, image_hash, path=DB_PATH):
    with connect(path) as con:
        return con.execute("SELECT 1 FROM clothing_items WHERE user_id=? AND image_hash=?", (uid,image_hash)).fetchone() is not None

def save_item(uid, filename, image_hash, image_data, result, path=DB_PATH,
              *, name=None, brand=None, cutout_data=None, reviewed=False):
    brand = clean_brand(brand)
    name = saved_name(name, result["attributes"], brand)
    with connect(path) as con:
        cur = con.execute("""INSERT INTO clothing_items
            (user_id,filename,image_hash,image_data,attributes_json,rankings_json,
             embedding_json,model_id,model_version,display_name,brand,cutout_data,metadata_reviewed)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,image_hash) DO NOTHING""",
            (uid, filename, image_hash, image_data, json.dumps(result["attributes"]),
             json.dumps(result["rankings"]), json.dumps(result["embedding"]),
             MODEL_ID, MODEL_VERSION, name, brand, cutout_data, int(reviewed)))
        return cur.rowcount == 1

def update_analysis(uid, item_id, result, path=DB_PATH):
    with connect(path) as con:
        row = con.execute("SELECT * FROM clothing_items WHERE id=? AND user_id=?",
                          (item_id, uid)).fetchone()
        if row is None:
            return False
        attrs = dict(result["attributes"])
        if row["metadata_reviewed"]:
            existing = json.loads(row["attributes_json"])
            for key in ("Category", "Subcategory"):
                if key in existing:
                    attrs[key] = existing[key]
        return con.execute("""UPDATE clothing_items SET attributes_json=?, rankings_json=?,
            embedding_json=?, model_id=?, model_version=? WHERE id=? AND user_id=?""",
            (json.dumps(attrs), json.dumps(result["rankings"]), json.dumps(result["embedding"]),
             MODEL_ID, MODEL_VERSION, item_id, uid)).rowcount == 1

def rename_item(uid, item_id, name, path=DB_PATH):
    name = (name or "").strip()
    if not name:
        raise ValueError("Name cannot be blank.")
    with connect(path) as con:
        return con.execute("UPDATE clothing_items SET display_name=? WHERE id=? AND user_id=?",
                           (name, item_id, uid)).rowcount == 1

def delete_items(uid, item_ids, path=DB_PATH):
    with connect(path) as con:
        return sum(con.execute("DELETE FROM clothing_items WHERE id=? AND user_id=?",
                               (item_id, uid)).rowcount for item_id in set(item_ids))

def delete_item(uid, item_id, path=DB_PATH):
    return delete_items(uid, [item_id], path) == 1

def set_cutout(uid, item_id, cutout_data, path=DB_PATH):
    with connect(path) as con:
        return con.execute("UPDATE clothing_items SET cutout_data=? WHERE id=? AND user_id=?",
                           (cutout_data, item_id, uid)).rowcount == 1

def get_background(uid, path=DB_PATH):
    with connect(path) as con:
        row = con.execute("SELECT background_color FROM users WHERE id=?", (uid,)).fetchone()
        return row["background_color"] if row else "#ffffff"

def set_background(uid, color, path=DB_PATH):
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("Choose a valid background color.")
    with connect(path) as con:
        return con.execute("UPDATE users SET background_color=? WHERE id=?",
                           (color, uid)).rowcount == 1

