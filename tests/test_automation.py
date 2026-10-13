"""Pruebas de fallos y salidas de la automatización RSS."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import update_news
from sources import rss_feeds, state


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        for name in ('logo-observador.jpg', 'icon.png', 'privacidad.html'):
            (self.root / name).write_bytes(b'asset')
        (self.root / 'index.html').write_text('anterior', encoding='utf-8')
        self.statefile = self.root / 'data' / 'state.json'
        self.statefile.parent.mkdir()
        self.statefile.write_text('{"seen": []}', encoding='utf-8')
        self.now = datetime(2026, 10, 13, 1, 0, tzinfo=ZoneInfo('America/Puerto_Rico'))
        for target, value in [('update_news.ROOT', self.root), ('sources.state.STATE_FILE', self.statefile)]:
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)

    def run_update(self, articles, statuses):
        with patch('update_news.fetch_all', return_value=(articles, statuses)), \
             patch('update_news.now_local', return_value=self.now), \
             patch('sources.collector.now_local', return_value=self.now), \
             patch('sources.renderer.now_local', return_value=self.now):
            update_news.main()

    def test_total_failure_preserves_html_and_state(self):
        before = self.statefile.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'Todas las fuentes'):
            self.run_update([], {'Radio Isla': '❌ Sin conexión'})
        self.assertEqual((self.root / 'index.html').read_text(), 'anterior')
        self.assertEqual(self.statefile.read_bytes(), before)
        self.assertFalse((self.root / '_site').exists())

    def test_render_failure_does_not_mark_seen_or_replace_html(self):
        before = self.statefile.read_bytes()
        with patch('update_news.generate_html', side_effect=RuntimeError('plantilla')):
            with self.assertRaisesRegex(RuntimeError, 'plantilla'):
                self.run_update([], {'Radio Isla': '✅ OK'})
        self.assertEqual(self.statefile.read_bytes(), before)
        self.assertEqual((self.root / 'index.html').read_text(), 'anterior')

    def test_publication_has_identical_urls_json_and_only_public_files(self):
        article = {'titular': 'Noticia en Fajardo', 'enlace': 'https://radioisla.tv/noticia/',
                   'fuente': 'Radio Isla', 'fecha': '2026-10-12 23:30',
                   'municipios': ['Fajardo'], 'tipo': 'RSS'}
        self.run_update([article], {'Radio Isla': '✅ OK'})
        site = self.root / '_site'
        self.assertEqual((site / 'index.html').read_bytes(), (site / 'dashboard.html').read_bytes())
        public = json.loads((site / 'noticias.json').read_text())
        self.assertEqual(public['schema_version'], 1)
        self.assertTrue(public['generated_at'].endswith('-04:00'))
        self.assertEqual(len(public['articles']), 1)
        self.assertEqual(set(p.name for p in site.iterdir()), {
            'index.html', 'dashboard.html', 'noticias.json', '.nojekyll',
            'logo-observador.jpg', 'icon.png', 'privacidad.html'})
        self.assertNotIn('seen', public)

    def test_empty_valid_source_does_not_invent_news(self):
        self.run_update([], {'Radio Isla': '✅ OK'})
        public = json.loads((self.root / 'noticias.json').read_text())
        self.assertEqual(public['articles'], [])

    def test_corrupt_state_is_recoverable(self):
        self.statefile.write_text('{roto', encoding='utf-8')
        self.run_update([], {'Radio Isla': '✅ OK'})
        self.assertIsInstance(state.load_state()['seen'], list)

    def test_public_json_recovers_news_after_cache_eviction(self):
        article = {'titular': 'Noticia en Fajardo', 'enlace': 'https://radioisla.tv/noticia/',
                   'fuente': 'Radio Isla', 'fecha': '2026-10-12 23:30',
                   'municipios': ['Fajardo'], 'tipo': 'RSS'}
        (self.root / 'noticias.json').write_text(json.dumps({
            'schema_version': 1, 'articles': [article]}))
        self.run_update([], {'Radio Isla': '❌ Caída', 'NotiCel': '✅ OK'})
        public = json.loads((self.root / 'noticias.json').read_text())
        self.assertEqual(len(public['articles']), 1)
        self.assertTrue(public['articles'][0]['conservada'])
        self.assertFalse(public['articles'][0]['es_nueva'])

    def test_budget_failure_preserves_previous_outputs(self):
        before = self.statefile.read_bytes()
        with patch('update_news.generate_html', return_value='<!doctype html>' + 'x' * 600000 + '</html>'):
            with self.assertRaisesRegex(RuntimeError, 'presupuesto'):
                self.run_update([], {'Radio Isla': '✅ OK'})
        self.assertEqual((self.root / 'index.html').read_text(), 'anterior')
        self.assertEqual(self.statefile.read_bytes(), before)

    def test_truncated_xml_is_not_success(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return b'<rss version="2.0"><channel><title>Fajardo</title>'
        with patch('sources.rss_feeds.urllib.request.urlopen', return_value=Response()), \
             patch('time.sleep'):
            articles, status = rss_feeds.fetch_rss('Prueba', 'https://radioisla.tv/feed/')
        self.assertEqual(articles, [])
        self.assertNotEqual(status, 'ok')

    def test_oversized_feed_is_rejected(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return b'x' * size
        with patch('sources.rss_feeds.urllib.request.urlopen', return_value=Response()), \
             patch('time.sleep'):
            articles, status = rss_feeds.fetch_rss('Prueba', 'https://radioisla.tv/feed/')
        self.assertEqual(articles, [])
        self.assertIn('demasiado grande', status)


if __name__ == '__main__':
    unittest.main()
