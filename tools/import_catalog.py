"""Refresh the sourced Cars catalogue. Run manually, never during app startup.

Requires mwparserfromhell (requirements-import.txt). Only factual metadata is
exported; article prose is not copied. Raw API responses stay in a local cache.
"""
import argparse
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

import mwparserfromhell

BASE = 'https://pixarcars.fandom.com'
ROOT = Path(__file__).resolve().parents[1]
MEDIA = [
    ('cars', 'Cars', 'Film'), ('cars-2', 'Cars 2', 'Film'),
    ('cars-3', 'Cars 3', 'Film'), ('toons', 'Cars Toons', 'Serie'),
    ('road', 'Cars on the Road', 'Serie'),
    ('ghostlight', 'Hook und das Geisterlicht', 'Kurzfilm'),
    ('fritter', "Miss Fritter’s Racing Skoool", 'Kurzfilm'),
    ('popcorn', 'Pixar Popcorn · Cars-Kurzfilme', 'Serie'),
    ('bricktoons', 'LEGO Pixar: Bricktoons · Cars', 'Serie'),
]
CATEGORIES = {
    'cars': 'Cars characters', 'cars-2': 'Cars 2 characters',
    'cars-3': 'Cars 3 characters', 'road': 'Cars on the Road characters',
}
EPISODES = {
    'toons': ['Rescue Squad Mater', 'Mater the Greater', 'El Materdor',
              'Tokyo Mater', 'Unidentified Flying Mater', 'Monster Truck Mater',
              'Heavy Metal Mater', 'Moon Mater', 'Mater Private Eye',
              'Air Mater', 'Time Travel Mater', 'Hiccups', 'Bugged', 'Spinning',
              'The Radiator Springs 500½'],
    'ghostlight': ['Mater and the Ghostlight'],
    'fritter': ["Miss Fritter's Racing Skoool"],
    'popcorn': ['Dancing with the Cars', 'Unparalleled Parking'],
    'bricktoons': ["Trust Yer Ol' Pal, Mater"],
}


def plain(value):
    value = re.sub(r'<ref\b[^>]*>.*?</ref>|<ref\b[^>]*/>', '', str(value), flags=re.S)
    value = re.sub(r'<br\s*/?>', '; ', value, flags=re.I)
    return ' '.join(html.unescape(mwparserfromhell.parse(value).strip_code()).split()).strip()


class Wiki:
    def __init__(self, cache):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)

    def query(self, **params):
        params = {'action': 'query', 'format': 'json', **params}
        query = urllib.parse.urlencode(params)
        path = self.cache / (hashlib.sha256(query.encode()).hexdigest() + '.json')
        if path.exists():
            return json.loads(path.read_text())
        request = urllib.request.Request(BASE + '/api.php?' + query,
            headers={'User-Agent': 'CarsCatalog/1.0 (personal character directory)'})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=40) as response:
                    result = json.load(response)
                if 'error' in result:
                    raise RuntimeError(result['error'])
                path.write_text(json.dumps(result, ensure_ascii=False))
                time.sleep(0.15)
                return result
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)

    def members(self, category):
        continuation = {}
        result = []
        while True:
            data = self.query(list='categorymembers', cmtitle='Category:' + category,
                              cmlimit=500, **continuation)
            result.extend(data['query']['categorymembers'])
            if 'continue' not in data:
                return result
            continuation = data['continue']

    def pages(self, titles):
        result = {}
        titles = sorted(set(titles))
        for offset in range(0, len(titles), 25):
            data = self.query(titles='|'.join(titles[offset:offset + 25]), redirects=1,
                prop='pageimages|revisions', piprop='thumbnail', pithumbsize=600,
                pilimit=50, rvprop='content|ids', rvslots='main')
            result.update({p['title']: p for p in data['query']['pages'].values() if 'missing' not in p})
            # Preserve aliases as lookup keys so appearances follow redirects.
            for alias in data['query'].get('redirects', []):
                if alias['to'] in result:
                    result[alias['from']] = result[alias['to']]
            print('  pages', min(offset + 25, len(titles)), '/', len(titles), flush=True)
        return result


def wikitext(page):
    return page.get('revisions', [{}])[0].get('slots', {}).get('main', {}).get('*', '')


def character_links(page):
    result = set()
    # Some source pages contain malformed templates before the character list.
    # Read top-level section boundaries independently of template parsing.
    sections = re.finditer(r'^==\s*(Characters?|(?:Voice )?Cast)\s*==\s*\n(.*?)(?=^==[^=]|\Z)',
                           wikitext(page), re.M | re.S | re.I)
    for section in sections:
        for line in section[2].splitlines():
            if not line.lstrip().startswith('*') or re.search(r'trailer only|deleted|unused', line, re.I):
                continue
            if 'cast' in section[1].lower():
                if not re.search(r'\bas\b', line):
                    continue
                line = re.split(r'\bas\b', line, maxsplit=1)[-1]
            for link in mwparserfromhell.parse(line).filter_wikilinks():
                title = str(link.title).strip().split('#')[0]
                if ':' not in title and title:
                    result.add(title)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', default=str(ROOT / '.import-cache'))
    args = parser.parse_args()
    wiki = Wiki(args.cache)
    appearances = defaultdict(set)
    evidence = defaultdict(set)
    counts = {}
    for media_id, category in CATEGORIES.items():
        pending, seen, names = [category], set(), set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            for member in wiki.members(current):
                if member['ns'] == 0:
                    names.add(member['title'])
                    evidence[member['title']].add(BASE + '/wiki/' + urllib.parse.quote('Category:' + current.replace(' ', '_'), safe=':'))
                elif media_id == 'road' and member['ns'] == 14:
                    pending.append(member['title'].removeprefix('Category:'))
        for name in names:
            appearances[name].add(media_id)
        counts[media_id] = len(names)
        print(media_id, len(names), flush=True)

    episodes = wiki.pages([title for titles in EPISODES.values() for title in titles])
    for media_id, titles in EPISODES.items():
        for title in titles:
            if title not in episodes:
                raise RuntimeError('Episode missing: ' + title)
            names = character_links(episodes[title])
            if not names:
                raise RuntimeError('No character list: ' + title)
            for name in names:
                appearances[name].add(media_id)
                evidence[name].add(BASE + '/wiki/' + urllib.parse.quote(title.replace(' ', '_')))

    pages = wiki.pages(appearances.keys())
    combined = {}
    excluded = []
    for requested, works in appearances.items():
        page = pages.get(requested)
        if not page:
            excluded.append({'name': requested, 'reason': 'Seite fehlt'})
            continue
        text = wikitext(page)
        infoboxes = [t for t in mwparserfromhell.parse(text).filter_templates()
                     if str(t.name).strip().lower() in ('character infobox', 'character_infobox')]
        named_without_box = {'Brake Pad Betty', 'Little Horace Power', 'Hamilton',
                             'Tess Drive', 'Manny Fold', 'Marsk', 'The Great Manufacturer'}
        box_match = re.search(r'{{\s*(?:Character[ _]infobox|Infobox Character)\b', text, re.I)
        if (not infoboxes and not box_match and page['title'] not in named_without_box) or re.search(r'\[\[Category:Unnamed characters', text, re.I):
            excluded.append({'name': requested, 'reason': 'Keine benannte Einzelfigur / keine Figuren-Infobox'})
            continue
        title = page['title']
        fields = {}
        if infoboxes:
            fields = {str(p.name).strip().lower(): plain(p.value) for p in infoboxes[0].params}
        elif box_match:
            # Recover short fields from malformed community infoboxes.
            for key in ('make', 'full name'):
                match = re.search(r'\|\s*' + key + r'\s*=([^\n]+)', text[box_match.start():], re.I)
                if match:
                    fields[key] = plain(match[1])
        aliases = [requested] if requested != title else []
        german = re.search(r'^\*\s*German\s*:\s*(.+)$', text, re.M | re.I)
        if german:
            alias = plain(german[1]).split('(')[0].strip()
            if alias and len(alias) < 80:
                aliases.append(alias)
        for key in ('full name',):
            if fields.get(key) and len(fields[key]) < 100:
                aliases.append(fields[key])
        cats = re.findall(r'\[\[Category:([^\]|]+)', text)
        kind = 'Figur'
        for cat, label in [('Race cars', 'Rennwagen'), ('Piston Cup racers', 'Rennwagen'),
                           ('Trucks', 'Truck'), ('Pickup trucks', 'Pickup'), ('Planes', 'Flugzeug'),
                           ('Helicopters', 'Hubschrauber'), ('Pitties', 'Boxencrew'),
                           ('Monster trucks', 'Monstertruck'), ('Tow trucks', 'Abschleppwagen')]:
            if cat in cats:
                kind = label
        key = str(page['pageid'])
        image_url = page.get('thumbnail', {}).get('source')
        if image_url and re.search(r'No[_ ]Image|Image[_ ]Needed|Placeholder', image_url, re.I):
            image_url = None
        if key not in combined:
            combined[key] = dict(id='wiki-' + key, name=title, aliases=[], type=kind,
                model=fields.get('make', '')[:180], image=image_url,
                description='', media=[], sources=[],
                source_url=BASE + '/wiki/' + urllib.parse.quote(title.replace(' ', '_')),
                revision=page.get('revisions', [{}])[0].get('revid'))
        row = combined[key]
        row['media'] = sorted(set(row['media']) | works)
        row['aliases'] = sorted(set(row['aliases'] + aliases) - {title})
        row['sources'] = sorted(set(row['sources']) | evidence[requested])

    rows = sorted(combined.values(), key=lambda r: r['name'].casefold())
    overrides = json.loads((ROOT / 'catalog' / 'overrides.json').read_text())
    for row in rows:
        update = overrides.get(row['name'], {})
        row['aliases'] = sorted(set(row['aliases'] + update.get('aliases', [])))
        row.update({k: v for k, v in update.items() if k != 'aliases'})
        if not row['description']:
            row['description'] = 'Im Cars-Figurenverzeichnis erfasst.'

    # Joint articles become individually searchable characters, sharing their
    # documented group image. Unnamed collectives are not individual characters.
    individual_rows = []
    existing_names = {row['name'] for row in rows}
    for row in rows:
        if row['name'] in {'Tractors', 'Dinoco Girls', 'Falcon Hawks', 'Road Rumblers (group)'}:
            excluded.append({'name': row['name'], 'reason': 'Gruppe statt benannter Einzelfigur'})
            continue
        if re.search(r'\s(?:and|&)\s', row['name']):
            names = [name.strip(' ,') for name in re.split(r',\s*|\s+(?:and|&)\s+', row['name']) if name.strip(' ,')]
            for name in names:
                if name in existing_names:
                    continue
                item = {**row, 'id': row['id'] + '-' + hashlib.sha256(name.encode()).hexdigest()[:8],
                        'name': name, 'aliases': [],
                        'description': 'Gemeinsamer Quellenartikel und gemeinsames Bild: ' + row['name'] + '.'}
                individual_rows.append(item)
        else:
            individual_rows.append(row)
    rows = sorted(individual_rows, key=lambda row: row['name'].casefold())

    used = {m for row in rows for m in row['media']}
    catalog = dict(updated=date.today().isoformat(), source=BASE,
        license='CC BY-SA (Wiki-Metadaten); Bilder gemäß jeweiliger Quelldatei, überwiegend Disney/Pixar',
        scope='Benannte Figuren der drei Cars-Filme, Cars Toons, Cars on the Road und ergänzender Kurzfilme laut verknüpften Wiki-Kategorien und Figurenlisten. Community-Daten, keine offizielle Vollständigkeitsgarantie.',
        media=[dict(id=i, title=t, kind=k) for i, t, k in MEDIA if i in used],
        characters=rows)
    (ROOT / 'catalog' / 'characters.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    report = dict(category_candidates=counts, total=len(rows), with_image=sum(bool(r['image']) for r in rows), excluded=excluded)
    (ROOT / 'catalog' / 'import-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('RESULT', len(rows), 'characters;', report['with_image'], 'images;', len(excluded), 'excluded', flush=True)


if __name__ == '__main__':
    main()
