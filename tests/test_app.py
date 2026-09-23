import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from app import ROOT, create_app, seed_database


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp.name) / 'cars.sqlite3')
        self.config = {'TESTING': True, 'DATABASE': self.database}
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_catalog_has_films_series_and_core_characters(self):
        data = self.client.get('/api/characters').get_json()
        self.assertGreater(data['total'], 700)
        self.assertEqual(len(data['items']), 24)
        self.assertEqual(data['items'][0]['name'], 'Lightning McQueen')
        for media in ('cars', 'cars-2', 'cars-3', 'road', 'toons', 'bricktoons'):
            with self.subTest(media=media):
                result = self.client.get('/api/characters', query_string={'media': media}).get_json()
                self.assertGreater(result['total'], 0)
                self.assertTrue(all(media in [m['id'] for m in item['media']] for item in result['items']))

    def test_alias_and_unicode_search(self):
        hook = self.client.get('/api/characters?q=Hook').get_json()['items']
        mater = self.client.get('/api/characters?q=Tow%20Mater').get_json()['items']
        self.assertTrue(any(item['name'] == 'Hook' for item in hook))
        self.assertTrue(any(item['name'] == 'Hook' for item in mater))
        result = self.client.get('/api/characters?q=zundapp').get_json()['items']
        self.assertTrue(any('Zündapp' in item['name'] for item in result))

    def test_named_pairs_are_individual_records(self):
        rows = json.loads((ROOT / 'catalog/characters.json').read_text())['characters']
        names = {r['name'] for r in rows}
        self.assertTrue({'Mia', 'Tia', 'Lisa', 'Louise', 'Victor Hugo', 'Todd', 'Maddy McGear'} <= names)
        self.assertNotIn('Mia and Tia', names)
        self.assertEqual(len(rows), len({r['id'] for r in rows}))

    def test_pagination_has_no_overlap(self):
        first = self.client.get('/api/characters?sort=name&limit=13').get_json()
        second = self.client.get('/api/characters?sort=name&limit=13&page=2').get_json()
        self.assertEqual(len(second['items']), 13)
        self.assertFalse({i['id'] for i in first['items']} & {i['id'] for i in second['items']})
        self.assertEqual(first['total'], second['total'])

    def test_user_input_is_parameterized(self):
        for query in ("' OR 1=1 --", '%', 'no-such-character-1234'):
            data = self.client.get('/api/characters', query_string={'q': query}).get_json()
            self.assertEqual(data['total'], 0)
        for params in ({'page': 0}, {'page': 'bad'}, {'limit': 200}, {'media': "' OR 1=1"},
                       {'sort': 'random; DROP TABLE characters'}, {'q': 'x' * 121}):
            self.assertEqual(self.client.get('/api/characters', query_string=params).status_code, 400)

    def test_restarts_preserve_database_and_custom_data(self):
        with sqlite3.connect(self.database) as db:
            db.execute("INSERT INTO metadata VALUES ('test_marker', 'keep me')")
            db.execute("UPDATE characters SET description='local edit' WHERE name='Hook'")
        app = create_app(self.config)
        self.assertEqual(app.test_client().get('/api/health').status_code, 200)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute("SELECT value FROM metadata WHERE key='test_marker'").fetchone()[0], 'keep me')
            self.assertEqual(db.execute("SELECT description FROM characters WHERE name='Hook'").fetchone()[0], 'local edit')
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_seed_update_is_atomic(self):
        catalog = json.loads((ROOT / 'catalog/characters.json').read_text())
        catalog['characters'][0]['media'] = ['nonexistent-media']
        bad_seed = Path(self.temp.name) / 'bad.json'
        bad_seed.write_text(json.dumps(catalog))
        count = self.client.get('/api/health').get_json()['characters']
        with self.assertRaises(sqlite3.IntegrityError):
            seed_database(self.database, bad_seed)
        self.assertEqual(self.client.get('/api/health').get_json()['characters'], count)

    def test_railway_volume_is_used_automatically(self):
        with patch.dict(os.environ, {'RAILWAY_VOLUME_MOUNT_PATH': self.temp.name, 'DATA_DIR': ''}):
            app = create_app({'TESTING': True})
            self.assertEqual(app.config['DATABASE'], self.database)
            self.assertTrue(app.test_client().get('/api/health').get_json()['persistent'])

    def test_private_files_are_not_public(self):
        for path in ('/.git/config', '/app.py', '/data/cars.sqlite3', '/catalog/characters.json', '/.env', '/../app.py'):
            self.assertEqual(self.client.get(path).status_code, 404)
        with self.client.get('/') as response:
            self.assertEqual(response.status_code, 200)
        with self.client.get('/style.css') as response:
            self.assertEqual(response.mimetype, 'text/css')
        self.assertEqual(self.client.post('/api/characters').status_code, 405)


if __name__ == '__main__':
    unittest.main()
