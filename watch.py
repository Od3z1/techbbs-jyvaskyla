"""One polling pass. No login, no notification until after initial baseline."""
import argparse
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = 'https://bbs.io-tech.fi'
LIST = BASE + '/forums/myydaan-ja-ostetaan.80/'
SOURCES = {
    'kauppa': LIST,
    'vaihdetaan': BASE + '/forums/vaihdetaan.46/',
    'lahjoitetaan': BASE + '/forums/lahjoitetaan.47/',
}
ACTIVE = {'Myydään', 'Ostetaan', 'Vaihdetaan', 'Lahjoitetaan', 'Annetaan'}
CITY = re.compile(r'\b(?:jyväskylä|jyvaskyla|jkl)\b', re.I)
STATE = Path(os.environ.get('STATE_FILE', 'state.json'))


def rows_from(html):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for row in soup.select('.structItem--thread'):
        if 'is-sticky' in row.get('class', []):
            continue
        title = row.select_one('.structItem-title a[data-tp-primary]')
        link = row.select_one('.structItem-startDate a')
        date = row.select_one('.structItem-startDate time')
        label = row.select_one('.structItem-title .label')
        if not all((title, link, date)):
            raise RuntimeError('Ilmoituslistan rakenne muuttui.')
        url = urljoin(BASE, link['href'])
        match = re.search(r'[./](\d+)/', url)
        if not match:
            raise RuntimeError('Ketjun tunnistetta ei löytynyt.')
        rows.append(dict(id=match[1], url=url, title=title.get_text(' ', strip=True),
                         created=int(date['data-timestamp']),
                         status=label.get_text(strip=True) if label else ''))
    if not rows:
        raise RuntimeError('Ilmoituslistaa ei löytynyt; tilaa ei nollata.')
    return rows, bool(soup.select_one('a.pageNav-jump--next'))


def details(html, title):
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('.message--post .message-body')
    heading = soup.select_one('h1 .label')
    if body is None:
        raise RuntimeError('Ilmoituksen rakenne muuttui tai pääsy estettiin.')
    if heading is None:
        return None  # A seller can remove the prefix after the list was fetched.
    if heading.get_text(strip=True) not in ACTIVE:
        return None
    for quote in body.select('blockquote'):
        quote.decompose()
    text = body.get_text(' ', strip=True)
    location = re.search(r'(?:Paikkakunta(?:\s*\([^)]*\))?|Sijainti)\s*:\s*(.*?)(?=\s*(?:Toimitustapa|Maksutapa|Kuva|Lisätiedot)\s*:|$)', text, re.I)
    # Explicit location overrides title, so "delivery to Jyväskylä" is not a match.
    if location:
        place = location.group(1).strip()
        if not CITY.search(place) or re.search(r'\b(?:toimitus|kuljetus|tuonti)\b.*jyväskyl', place, re.I):
            return None
    elif CITY.search(title):
        place = 'Jyväskylä (otsikon perusteella)'
    else:
        return None
    price = re.search(r'(?:Hintapyyntö|Hinta)\s*:\s*(.*?)(?=\s*(?:Tuote ostettu|Kuitti|Muuta huomioitavaa|Paikkakunta|Sijainti|Toimitustapa)\s*[:(]|$)', text, re.I)
    return {'location': place[:160], 'price': price.group(1).strip()[:180] if price else 'Katso ilmoitus'}


class Web:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'TechBBS-Jyvaskyla-Watch/1.0 (personal classified alerts)'
        self.last = 0

    def get(self, url, **kwargs):
        time.sleep(max(0, 1.0 - (time.monotonic() - self.last)))
        response = self.session.get(url, timeout=30, **kwargs)
        self.last = time.monotonic()
        response.raise_for_status()  # No bypass or aggressive retries on blocking/429.
        return response.text


def notify(title, message, url=LIST):
    topic = os.environ.get('NTFY_TOPIC', '').strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,128}', topic):
        raise RuntimeError('Aseta NTFY_TOPIC salaisuudeksi (pitkä satunnainen kanavanimi).')
    headers = {}
    if os.environ.get('NTFY_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['NTFY_TOKEN']
    r = requests.post('https://ntfy.sh/', headers=headers, json={
        'topic': topic, 'title': title[:200], 'message': message,
        'click': url, 'tags': ['shopping_cart']}, timeout=30)
    r.raise_for_status()


def save(state):
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(STATE)


def run(dry=False, list_url=LIST):
    web = Web()
    first, has_next = rows_from(web.get(list_url, params={'order': 'post_date', 'direction': 'desc'}))
    if not STATE.exists():
        if not dry:
            # Validate destination and confirm initialization with a single push.
            notify('TechBBS-vahti käynnistetty', 'Jyväskylän uusien ilmoitusten seuranta on aloitettu tässä osiossa.', list_url)
            save({'watermark': max(r['created'] for r in first),
                  'seen': {r['id']: r['created'] for r in first}})
        print(f'Alustus: {len(first)} nykyistä ilmoitusta, ei vanhojen tuotteiden ilmoituksia.')
        return
    state = json.loads(STATE.read_text())
    cutoff = state['watermark'] - 600
    rows = first[:]
    page = 1
    batch = first
    while min(r['created'] for r in batch) >= cutoff and has_next:
        page += 1
        if page > 30:
            raise RuntimeError('Yli 30 sivun katkos. Vesileimaa ei siirretä; tarkista tilanne käsin.')
        batch, has_next = rows_from(web.get(list_url, params={'order': 'post_date', 'direction': 'desc', 'page': page}))
        rows.extend(batch)
    count = 0
    for row in sorted(rows, key=lambda r: r['created']):
        if row['created'] < cutoff or row['id'] in state['seen']:
            continue
        if row['status'] in ACTIVE:
            found = details(web.get(row['url']), row['title'])
            if found:
                msg = f"{found['price']}\n{found['location']}\n{row['url']}"
                if dry:
                    print(row['title'], msg)
                else:
                    notify(f"{row['status']}: {row['title']}", msg, row['url'])
                count += 1
        state['seen'][row['id']] = row['created']
        if not dry:
            save(state)  # Keep successes even if a later notification fails.
    state['watermark'] = max(state['watermark'], max(r['created'] for r in rows))
    state['seen'] = {k: v for k, v in state['seen'].items() if v >= state['watermark'] - 86400}
    if not dry:
        save(state)
    print(f'Tarkistettu {len(rows)} ketjua; uusia Jyväskylän osumia {count}.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--test-push', action='store_true')
    args = parser.parse_args()
    if args.test_push:
        notify('TechBBS-testiviesti', 'Push-ilmoitukset toimivat. Avaa TechBBS napauttamalla.')
    else:
        original_state = STATE
        failures = []
        for source, list_url in SOURCES.items():
            STATE = original_state if source == 'kauppa' else original_state.with_name(f'{original_state.stem}-{source}.json')
            print(f'Osio: {source}')
            try:
                run(args.dry_run, list_url)
            except Exception as exc:
                # Don't log request exceptions: a push endpoint may contain secrets.
                print(f'Osion {source} tarkistus epäonnistui ({type(exc).__name__}). Tarkista asetukset ja sivuston saatavuus.')
                if isinstance(exc, RuntimeError):
                    print(f'Syy: {exc}')
                failures.append(source)
        if failures:
            raise SystemExit(1)
