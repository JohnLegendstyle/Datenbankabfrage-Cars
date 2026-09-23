"""Cars catalogue: Flask API backed by a persistent SQLite database."""
import hashlib
import json
import math
import os
import sqlite3
import unicodedata
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                   if not unicodedata.combining(c))


def seed_database(path, catalog_path):
    """Upsert a versioned seed atomically; never replace the database file."""
    raw = Path(catalog_path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    catalog = json.loads(raw)
    if not catalog.get('characters'):
        raise ValueError('The catalogue must contain characters.')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    try:
        db.execute('PRAGMA foreign_keys = ON')
        db.execute('PRAGMA journal_mode = WAL')
        db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS media (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, aliases TEXT NOT NULL,
                type TEXT NOT NULL, model TEXT NOT NULL, description TEXT NOT NULL,
                image TEXT, source_url TEXT NOT NULL, revision INTEGER,
                sources TEXT NOT NULL, search_text TEXT NOT NULL,
                sort_name TEXT NOT NULL, featured INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS appearances (
                character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                media_id TEXT NOT NULL REFERENCES media(id),
                PRIMARY KEY (character_id, media_id)
            );
            CREATE INDEX IF NOT EXISTS appearances_media ON appearances(media_id, character_id);
            CREATE INDEX IF NOT EXISTS characters_sort ON characters(active, sort_name);
        ''')
        db.execute('BEGIN IMMEDIATE')
        previous = db.execute("SELECT value FROM metadata WHERE key = 'seed_hash'").fetchone()
        if previous and previous[0] == digest:
            db.commit()
            return
        for item in catalog['media']:
            db.execute('INSERT INTO media VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET title=excluded.title, kind=excluded.kind',
                       (item['id'], item['title'], item['kind']))
        # Old source entries are hidden, not destroyed. User-created rows remain.
        db.execute("UPDATE characters SET active = 0 WHERE id LIKE 'wiki-%'")
        favorite_order = ['Lightning McQueen', 'Hook', 'Sally Carrera', 'Doc Hudson',
                          'Cruz Ramirez', 'Jackson Storm', 'Ivy']
        for item in catalog['characters']:
            search = normalize(' '.join([item['name'], *item['aliases'], item['type'], item['model']]))
            featured = 100 - favorite_order.index(item['name']) if item['name'] in favorite_order else 0
            db.execute('''INSERT INTO characters
                (id, name, aliases, type, model, description, image, source_url, revision, sources, search_text, sort_name, featured, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, aliases=excluded.aliases, type=excluded.type,
                model=excluded.model, description=excluded.description, image=excluded.image,
                source_url=excluded.source_url, revision=excluded.revision, sources=excluded.sources,
                search_text=excluded.search_text, sort_name=excluded.sort_name, featured=excluded.featured, active=1
                ''', (item['id'], item['name'], json.dumps(item['aliases'], ensure_ascii=False),
                      item['type'], item['model'], item['description'], item['image'],
                      item['source_url'], item.get('revision'), json.dumps(item['sources']),
                      search, normalize(item['name']), featured))
            db.execute('DELETE FROM appearances WHERE character_id = ?', (item['id'],))
            db.executemany('INSERT INTO appearances VALUES (?, ?)', [(item['id'], media) for media in item['media']])
        for key, value in [('seed_hash', digest), ('updated', catalog['updated']), ('scope', catalog['scope'])]:
            db.execute('INSERT INTO metadata VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    volume = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
    data_dir = Path(os.environ.get('DATA_DIR') or volume or ROOT / 'data')
    app.config.update(DATABASE=str(data_dir / 'cars.sqlite3'),
                      CATALOG=str(ROOT / 'catalog' / 'characters.json'))
    if config:
        app.config.update(config)
    seed_database(app.config['DATABASE'], app.config['CATALOG'])
    if os.environ.get('RAILWAY_ENVIRONMENT_ID') and not volume:
        app.logger.warning('No Railway volume attached. The catalogue works, but the database is not persistent across deployments. Mount a volume at /data.')

    def get_db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'], timeout=10)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys = ON')
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        db = g.pop('db', None)
        if db is not None:
            db.close()

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' https://lumiere-a.akamaihd.net https://static.wikia.nocookie.net https://images.squarespace-cdn.com; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/')
    @app.get('/index.html')
    def index():
        return send_from_directory(ROOT, 'index.html')

    @app.get('/style.css')
    def stylesheet():
        return send_from_directory(ROOT, 'style.css')

    @app.get('/script.js')
    def script():
        return send_from_directory(ROOT, 'script.js')

    @app.get('/api/health')
    def health():
        count = get_db().execute('SELECT COUNT(*) FROM characters WHERE active=1').fetchone()[0]
        persistent = bool(volume and Path(app.config['DATABASE']).resolve().is_relative_to(Path(volume).resolve()))
        return jsonify(status='ok', database='sqlite', characters=count, persistent=persistent)

    @app.get('/api/media')
    def media():
        db = get_db()
        rows = db.execute('''SELECT m.id, m.title, m.kind, COUNT(c.id) AS count
            FROM media m JOIN appearances a ON a.media_id=m.id
            JOIN characters c ON c.id=a.character_id AND c.active=1
            GROUP BY m.id ORDER BY m.rowid''').fetchall()
        metadata = dict(db.execute('SELECT key, value FROM metadata'))
        return jsonify(media=[dict(row) for row in rows],
                       updated=metadata.get('updated'), scope=metadata.get('scope'))

    @app.get('/api/characters')
    def characters():
        query = request.args.get('q', '').strip()
        media_id = request.args.get('media', '')
        sort = request.args.get('sort', 'featured')
        if len(query) > 120:
            return jsonify(error='Bitte höchstens 120 Zeichen eingeben.'), 400
        try:
            page = int(request.args.get('page', '1'))
            limit = int(request.args.get('limit', '24'))
            if page < 1 or page > 100000 or limit < 1 or limit > 60:
                raise ValueError()
        except ValueError:
            return jsonify(error='Ungültige Seitennummer oder Seitengröße.'), 400
        orders = {'featured': 'c.featured DESC, c.sort_name, c.id',
                  'name': 'c.sort_name, c.id', 'name-desc': 'c.sort_name DESC, c.id'}
        if sort not in orders:
            return jsonify(error='Ungültige Sortierung.'), 400
        db = get_db()
        clauses, values = ['c.active=1'], []
        for word in normalize(query).split():
            clauses.append('instr(c.search_text, ?) > 0')
            values.append(word)
        if media_id:
            if not db.execute('SELECT 1 FROM media WHERE id=?', (media_id,)).fetchone():
                return jsonify(error='Unbekannter Film oder unbekannte Serie.'), 400
            clauses.append('EXISTS (SELECT 1 FROM appearances a WHERE a.character_id=c.id AND a.media_id=?)')
            values.append(media_id)
        where = ' AND '.join(clauses)
        total = db.execute('SELECT COUNT(*) FROM characters c WHERE ' + where, values).fetchone()[0]
        rows = db.execute('SELECT c.* FROM characters c WHERE ' + where + ' ORDER BY ' + orders[sort] + ' LIMIT ? OFFSET ?',
                          [*values, limit, (page - 1) * limit]).fetchall()
        items = []
        for row in rows:
            item = {key: row[key] for key in ('id', 'name', 'type', 'model', 'description', 'image', 'source_url', 'revision')}
            item['aliases'] = json.loads(row['aliases'])
            item['media'] = [dict(m) for m in db.execute('''SELECT m.id, m.title FROM appearances a
                JOIN media m ON m.id=a.media_id WHERE a.character_id=? ORDER BY m.rowid''', (row['id'],))]
            items.append(item)
        catalog_total = db.execute('SELECT COUNT(*) FROM characters WHERE active=1').fetchone()[0]
        return jsonify(items=items, total=total, catalog_total=catalog_total,
                       page=page, pages=math.ceil(total / limit), limit=limit)

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=int(os.environ.get('PORT', 8000)), debug=False)
