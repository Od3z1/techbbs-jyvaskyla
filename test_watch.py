import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import watch


def page(location, status='Myydään', extra=''):
    return f'<h1><span class="label">{status}</span></h1><article class="message--post"><div class="message-body">Hinta: 50 € Tuote ostettu: 2025 Paikkakunta: {location} Toimitustapa: Nouto {extra}</div></article>'


class Tests(unittest.TestCase):
    def test_city_spellings(self):
        for city in ['jkl', 'JKL', 'JkL', 'Jyväskylä', 'jyväskylä', 'JYVÄSKYLÄ', 'Jyvaskyla', 'JYVASKYLA']:
            with self.subTest(city=city):
                result = watch.details(page(city), 'Näytönohjain')
                self.assertIsNotNone(result)
                self.assertEqual(result['price'], '50 €')

    def test_title_spellings_when_location_missing(self):
        html = '<h1><span class="label">Myydään</span></h1><div class="message--post"><div class="message-body">Hinta: 50 €</div></div>'
        for city in ['[JKL]', '(jkl)', '*JYVÄSKYLÄ*', 'Jyvaskyla']:
            self.assertIsNotNone(watch.details(html, 'RTX 3060 ' + city))

    def test_actual_location_overrides_title(self):
        self.assertIsNone(watch.details(page('Tampere'), 'Tuote [JKL]'))

    def test_delivery_is_not_location(self):
        self.assertIsNone(watch.details(page('Laukaa / toimitus Jyväskylään'), 'Tuote'))
        self.assertIsNone(watch.details(page('Tampere', extra='Myös toimitus Jyväskylään'), 'Tuote'))

    def test_sold_excluded(self):
        for status in ['Myyty', 'Ostettu', 'Vaihdettu', 'Lahjoitettu']:
            self.assertIsNone(watch.details(page('JKL', status), 'Tuote JKL'))

    def test_all_requested_types(self):
        for status in ['Myydään', 'Ostetaan', 'Vaihdetaan', 'Lahjoitetaan', 'Annetaan']:
            with self.subTest(status=status):
                self.assertIsNotNone(watch.details(page('jkl', status), 'Tuote'))

    def test_block_page_fails(self):
        with self.assertRaises(RuntimeError):
            watch.rows_from('<html>Access denied</html>')

    def test_missing_prefix_does_not_break_list(self):
        html = '<div class="structItem--thread"><div class="structItem-title"><a data-tp-primary="on">Tuote</a></div><div class="structItem-startDate"><a href="/threads/tuote.684030/"><time data-timestamp="1792749105"></time></a></div></div>'
        rows, _ = watch.rows_from(html)
        self.assertEqual(rows[0]['status'], '')
        self.assertNotIn(rows[0]['status'], watch.ACTIVE)

    def test_removed_prefix_on_thread_is_skipped(self):
        html = page('JKL').replace('<span class="label">Myydään</span>', '')
        self.assertIsNone(watch.details(html, 'Tuote JKL'))

    def test_thread_url_without_title_slug(self):
        html = '<div class="structItem--thread"><div class="structItem-title"><span class="label">Lahjoitetaan</span><a data-tp-primary="on">Tuote JKL</a></div><div class="structItem-startDate"><a href="/threads/123456/"><time data-timestamp="2000"></time></a></div></div>'
        rows, _ = watch.rows_from(html)
        self.assertEqual(rows[0]['id'], '123456')

    def test_duplicate_and_failed_push(self):
        row = dict(id='2', url='https://bbs.io-tech.fi/threads/test.2/', title='GPU JKL', created=2000, status='Myydään')
        with tempfile.TemporaryDirectory() as d, patch.object(watch, 'STATE', Path(d)/'state.json'), patch.object(watch, 'rows_from', return_value=([row], False)), patch.object(watch.Web, 'get', return_value=page('JKL')):
            watch.save({'watermark': 1900, 'seen': {}})
            with patch.object(watch, 'notify', side_effect=RuntimeError('push failed')):
                with self.assertRaises(RuntimeError):
                    watch.run()
            self.assertNotIn('2', json.loads(watch.STATE.read_text())['seen'])
            with patch.object(watch, 'notify') as send:
                watch.run()
                watch.run()
                self.assertEqual(send.call_count, 1)


if __name__ == '__main__':
    unittest.main()
