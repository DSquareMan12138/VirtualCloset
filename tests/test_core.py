import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from virtual_closet import database as db
from virtual_closet.auth import hash_password, verify_password
from virtual_closet.recommendation import recommend
from virtual_closet.images import read_image

RESULT = {'attributes':{'Category':'Shirt','Color':'Black','Base pattern':'Solid'},
          'rankings':{'Category':['Shirt']},'embedding':[1.,0.]}

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'closet.db'
        db.initialize(self.path)
        self.a = db.register('alice','test-password-123',self.path)
        self.b = db.register('bobby','other-password-123',self.path)
    def tearDown(self):
        self.temp.cleanup()
    def test_accounts(self):
        self.assertIsNotNone(db.login('ALICE','test-password-123',self.path))
        self.assertIsNone(db.login('alice','wrong',self.path))
        self.assertIsNone(db.login('missing','wrong',self.path))
        with self.assertRaises(ValueError): db.register('alice','another-password',self.path)
        with self.assertRaises(ValueError): db.register('ab','another-password',self.path)
        first = hash_password('same-password-123')
        self.assertNotEqual(first,hash_password('same-password-123'))
        self.assertTrue(verify_password('same-password-123',first))
    def test_isolation_duplicates_and_deletion(self):
        a,b = self.a['id'],self.b['id']
        self.assertTrue(db.save_item(a,'shirt.jpg','hash',b'img',RESULT,self.path))
        self.assertFalse(db.save_item(a,'renamed.jpg','hash',b'img',RESULT,self.path))
        self.assertTrue(db.save_item(b,'shirt.jpg','hash',b'img',RESULT,self.path))
        item_id=db.list_items(a,self.path)[0]['id']
        self.assertFalse(db.delete_item(b,item_id,self.path))
        self.assertFalse(db.update_analysis(b,item_id,RESULT,self.path))
        self.assertEqual(len(db.list_items(a,self.path)),1)
        self.assertTrue(db.delete_item(a,item_id,self.path))
        self.assertEqual(len(db.list_items(b,self.path)),1)
        with self.assertRaises(sqlite3.IntegrityError):
            db.save_item(999,'bad','bad',b'img',RESULT,self.path)
    def test_image_rejection(self):
        with self.assertRaises(Exception):read_image(b'not an image')
    def test_outfit_composition(self):
        def item(i,c):
            return {'id':i,'attributes_json':json.dumps({'Category':c,'Color':'Black','Base pattern':'Solid'})}
        items=[item(1,'Shirt'),item(2,'Trousers'),item(3,'Coat'),item(4,'Shoes'),item(5,'Dress')]
        scores={i['id']:.25 for i in items}
        outfits,notes=recommend(items,scores,True,day='2026-10-19')
        self.assertTrue(outfits)
        for outfit in outfits:
            ids={i['id'] for i in outfit}
            self.assertIn(3,ids);self.assertIn(4,ids)
            self.assertTrue(({1,2}<=ids) != (5 in ids))
            self.assertFalse(5 in ids and (1 in ids or 2 in ids))
        self.assertEqual(recommend([items[0]],{1:.2})[0],[])
        self.assertEqual(recommend([], {})[0],[])
        self.assertEqual(recommend(items,scores,True,day='2026-10-19')[0],outfits)

class NewAccountTest(unittest.TestCase):
    def test_new_accounts_start_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'closet.db'
            db.initialize(path)

            first = db.register('first', 'test-password-123', path)
            self.assertEqual(db.list_items(first['id'], path), [])

            # An existing user's clothes must not enter a new account.
            db.save_item(
                first['id'], 'shirt.jpg', 'hash',
                b'img', RESULT, path
            )

            second = db.register('second', 'test-password-123', path)
            self.assertEqual(db.list_items(second['id'], path), [])
            self.assertEqual(len(db.list_items(first['id'], path)), 1)


if __name__ == '__main__':unittest.main()
