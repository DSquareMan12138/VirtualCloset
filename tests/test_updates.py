import ast
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from PIL import Image
from virtual_closet import database as db
from virtual_closet.images import thumbnail_bytes, read_rgba, display_image
from virtual_closet.metadata import automatic_name, reviewed_attributes, saved_name, clean_brand
from virtual_closet.recommendation import recommend, signature

RESULT = {"attributes": {"Category": "Shirt", "Subcategory": "oxford shirt", "Color": "Blue",
                          "Base pattern": "Solid"}, "rankings": {}, "embedding": [1., 0.]}

class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "closet.db"
        db.initialize(self.path)
        self.a = db.register("alice", "test-password", self.path)["id"]
        self.b = db.register("bobby", "test-password", self.path)["id"]

    def tearDown(self):
        self.temp.cleanup()

    def add(self, uid=None, digest="hash", **kwargs):
        db.save_item(uid or self.a, "original.jpg", digest, b"original", RESULT,
                     self.path, **kwargs)
        return db.list_items(uid or self.a, self.path)[0]

    def test_reviewed_metadata_survives_reanalysis(self):
        row = self.add(name="My favorite", brand=" Nike ", reviewed=True)
        changed = dict(RESULT, attributes={"Category": "Dress", "Subcategory": "slip dress"})
        db.update_analysis(self.a, row["id"], changed, self.path)
        result = db.list_items(self.a, self.path)[0]
        self.assertEqual(result["display_name"], "My favorite")
        self.assertEqual(result["brand"], "Nike")
        self.assertEqual(json.loads(result["attributes_json"])["Category"], "Shirt")
        self.assertEqual(json.loads(result["attributes_json"])["Subcategory"], "oxford shirt")

    def test_owner_scoped_rename_delete_and_cutout(self):
        row = self.add()
        other = self.add(self.b)
        self.assertFalse(db.rename_item(self.b, row["id"], "Stolen", self.path))
        self.assertFalse(db.set_cutout(self.b, row["id"], b"cut", self.path))
        self.assertTrue(db.rename_item(self.a, row["id"], " New name ", self.path))
        with self.assertRaises(ValueError):
            db.rename_item(self.a, row["id"], "  ", self.path)
        self.assertEqual(db.delete_items(self.a, [row["id"], other["id"], row["id"]], self.path), 1)
        self.assertEqual(len(db.list_items(self.b, self.path)), 1)

    def test_original_image_and_theme_are_preserved(self):
        row = self.add(cutout_data=b"cutout")
        db.set_background(self.a, "#112233", self.path)
        db.initialize(self.path)
        row = db.list_items(self.a, self.path)[0]
        self.assertEqual(row["image_data"], b"original")
        self.assertEqual(row["cutout_data"], b"cutout")
        self.assertEqual(db.get_background(self.a, self.path), "#112233")
        self.assertEqual(db.get_background(self.b, self.path), "#ffffff")

    def test_blank_brand_and_name_saved(self):
        row = self.add(name=" ", brand="  ")
        self.assertIsNone(row["brand"])
        self.assertEqual(row["display_name"], "Blue oxford shirt")

    def test_migration_of_previous_schema(self):
        # Reproduce the prior schema with no new columns.
        old = Path(self.temp.name) / "old.db"
        with sqlite3.connect(old) as con:
            con.executescript("""
                CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT NOT NULL UNIQUE,
                  password_hash TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE clothing_items(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),
                  filename TEXT NOT NULL,image_hash TEXT NOT NULL,image_data BLOB NOT NULL,
                  attributes_json TEXT NOT NULL,rankings_json TEXT NOT NULL,embedding_json TEXT,
                  model_id TEXT NOT NULL,model_version TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(user_id,image_hash));
                INSERT INTO users(id,username,password_hash) VALUES(7,'existing','password-hash');
                INSERT INTO clothing_items VALUES(9,7,'Existing name','abc',X'0102','{}','{}','[1,0]',
                  'model','v1','2026-01-01');
            """)
        con.close()
        db.initialize(old)
        db.initialize(old)
        item = db.list_items(7, old)[0]
        self.assertEqual(item["id"], 9)
        self.assertEqual(item["display_name"], "Existing name")
        self.assertEqual(item["image_data"], bytes([1, 2]))
        with db.connect(old) as con:
            self.assertEqual(con.execute("SELECT password_hash FROM users").fetchone()[0], "password-hash")

class NamingAndImageTests(unittest.TestCase):
    def test_name_and_category_rules(self):
        attrs = RESULT["attributes"]
        self.assertEqual(automatic_name(attrs, "Nike"), "Nike Blue oxford shirt")
        corrected = reviewed_attributes(attrs, "Shoes")
        self.assertEqual(corrected["Subcategory"], "Other / unspecified")
        self.assertEqual(automatic_name(corrected), "Blue Shoes")
        self.assertEqual(saved_name(" Mine ", corrected, "Nike"), "Mine")
        self.assertEqual(automatic_name({}), "Clothing item")
        self.assertIsNone(clean_brand("  "))
        self.assertEqual(reviewed_attributes(attrs, " ")["Category"], "Uncategorized")

    def test_transparency_and_theme_do_not_recolor_garment(self):
        image = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
        image.putpixel((0, 0), (255, 0, 0, 255))
        raw = thumbnail_bytes(image)
        self.assertEqual(read_rgba(raw).getpixel((1, 0))[3], 0)
        for color, expected in [("#ffffff", (255,255,255)), ("#000000", (0,0,0))]:
            out = display_image(raw, color)
            self.assertEqual(out.getpixel((0, 0)), (255,0,0))
            self.assertEqual(out.getpixel((1, 0)), expected)

    def test_upload_removes_background_before_recognition_and_does_not_save(self):
        # Execute the actual upload handler with instrumented model/image boundaries.
        source = Path(__file__).resolve().parents[1] / "app.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "analyze_files")
        events = []
        fake_st = Mock()
        fake_st.session_state = {}
        fake_db = Mock()
        fake_db.exists.return_value = False
        model = Mock()
        def cut(raw):
            events.append(("cutout", raw))
            return b"transparent"
        def white(raw):
            self.assertEqual(raw, b"transparent")
            events.append(("white", raw))
            return "white composite"
        def analyze(image):
            self.assertEqual(image, "white composite")
            events.append(("recognize", image))
            return RESULT
        model.analyze.side_effect = analyze
        scope = {"st": fake_st, "db": fake_db, "image_hash": lambda raw: "digest",
                 "remove_background": cut, "read_image": white, "get_model": lambda: model,
                 "logging": Mock(), "uuid": __import__("uuid")}
        exec(compile(ast.Module(body=[func], type_ignores=[]), str(source), "exec"), scope)
        photo = Mock()
        photo.name = "photo.png"
        photo.getvalue.return_value = b"original"
        scope["analyze_files"](1, [photo])
        self.assertEqual([x[0] for x in events], ["cutout", "white", "recognize"])
        fake_db.save_item.assert_not_called()
        self.assertEqual(len(fake_st.session_state["review"]), 1)

class RecommendationTests(unittest.TestCase):
    def items(self, categories):
        return [{"id": n, "attributes_json": json.dumps({"Category": c, "Color": "Black",
                 "Base pattern": "Solid"})} for n,c in enumerate(categories, 1)]

    def test_three_unique_and_refresh_excludes_previous(self):
        items = self.items(["Shirt"]*3 + ["Trousers"]*3 + ["Shoes", "Custom category"])
        first, _ = recommend(items, {}, day="fixed", variant=0)
        second, _ = recommend(items, {}, day="fixed", variant=1, exclude=map(signature, first))
        self.assertEqual(len(first), 3)
        self.assertEqual(len(second), 3)
        self.assertEqual(len(set(map(signature, first))), 3)
        self.assertFalse(set(map(signature, first)) & set(map(signature, second)))
        self.assertFalse(any(8 in signature(o) for o in first + second))

    def test_shortage_does_not_duplicate_outfits(self):
        items = self.items(["Dress"])
        first, notes = recommend(items, {})
        self.assertEqual(len(first), 1)
        self.assertTrue(any("clothing-only" in n for n in notes))
        second, notes = recommend(items, {}, exclude=map(signature, first))
        self.assertEqual(len(second), 1)
        self.assertTrue(any("previous" in n for n in notes))

if __name__ == "__main__":
    unittest.main()

