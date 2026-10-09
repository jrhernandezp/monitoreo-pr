import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from sources import collector, rss_feeds, renderer, state, scraper, newsapi_source
from sources.dates import PUERTO_RICO, parse_article_date

NOW = datetime(2026, 10, 8, 18, 0, tzinfo=PUERTO_RICO)


def article(title="Noticia de Carolina", date="2026-10-08 17:00", link="https://example.com/n"):
    return {"titular": title, "fecha": date, "enlace": link,
            "fuente": "Prueba", "municipios": ["Carolina"], "es_nueva": True}


class DatesAndDedupTests(unittest.TestCase):
    def test_utc_is_converted_to_puerto_rico(self):
        self.assertEqual(parse_article_date("2026-10-09T02:00:00Z").strftime("%Y-%m-%d %H:%M"), "2026-10-08 22:00")

    @patch("sources.collector.now_local", return_value=NOW)
    def test_filter_includes_every_day_not_just_endpoints(self, _):
        items = [article(date=f"2026-10-{day:02d} 12:00") for day in range(4, 10)]
        self.assertEqual(len(collector.filter_recent(items, 4)), 4)

    @patch("sources.collector.now_local", return_value=NOW)
    def test_future_and_unknown_dates_are_excluded(self, _):
        self.assertEqual(collector.filter_recent([article(date=""), article(date="2026-10-08 23:00")]), [])
        self.assertFalse(collector.is_recent_breaking(article("Emergencia en Carolina", "2026-10-08 23:00")))

    @patch("sources.collector.now_local", return_value=NOW)
    def test_known_age_and_date_only(self, _):
        self.assertEqual(collector.time_ago("2026-10-08 17:00"), "hace 1h")
        self.assertEqual(collector.time_ago("2026-10-08"), "2026-10-08")

    def test_tracking_links_and_municipalities_merge(self):
        a = article(link="https://example.com/n?utm_source=rss#fragment")
        b = article(link="https://example.com/n?utm_source=widget")
        b["municipios"] = ["Fajardo"]
        result = collector.deduplicate([a, b])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["municipios"], ["Carolina", "Fajardo"])

    def test_different_long_titles_stay_distinct(self):
        a, b = article("x" * 100 + " A"), article("x" * 100 + " B")
        self.assertNotEqual(collector.article_key(a), collector.article_key(b))

    def test_unsafe_or_missing_links_are_rejected(self):
        self.assertEqual(collector.deduplicate([article(link="javascript:alert(1)"), article(link="")]), [])

    def test_municipality_boundaries_and_accents(self):
        self.assertEqual(rss_feeds.mentions_municipio("Noticias de Rio Grande y Loiza"), ["Loíza", "Río Grande"])
        self.assertEqual(rss_feeds.mentions_municipio("culebras y carolinamar"), [])

    def test_foreign_carolina_names_do_not_match_local_municipality(self):
        for text in ["Trabajadores de la Carolina Classic Fair en Winston-Salem", "Noticias de Carolina del Norte", "South Carolina"]:
            self.assertEqual(rss_feeds.mentions_municipio(text), [])
        self.assertEqual(rss_feeds.mentions_municipio("Carolina, Puerto Rico recibe visitantes de Carolina del Norte"), ["Carolina"])

    def test_direct_link_replaces_google_duplicate_and_keeps_municipalities(self):
        google = article(link="https://news.google.com/rss/articles/test")
        direct = article(link="https://example.com/direct")
        direct["municipios"] = ["Fajardo"]
        result = collector.deduplicate([google, direct])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["enlace"], direct["enlace"])
        self.assertEqual(result[0]["municipios"], ["Carolina", "Fajardo"])


class FeedTests(unittest.TestCase):
    def fetch(self, xml, limit=8):
        with patch("sources.rss_feeds.urllib.request.urlopen", return_value=io.BytesIO(xml.encode())), patch("sources.rss_feeds.now_local", return_value=NOW):
            return rss_feeds.fetch_rss("Test", "https://example.com/feed", limit)

    def test_html_error_is_not_a_successful_feed(self):
        items, status = self.fetch("<html><body>Access denied</body></html>")
        self.assertEqual(items, [])
        self.assertNotEqual(status, "ok")

    def test_valid_empty_feed_is_success(self):
        _, status = self.fetch('<rss version="2.0"><channel><title>Test</title></channel></rss>')
        self.assertEqual(status, "ok")

    def test_rss_timezone_and_relevant_quota(self):
        xml = '<rss version="2.0"><channel><title>Test</title>'
        for title in ["Noticia de otro lugar", "Noticia en Carolina"]:
            xml += f'<item><title>{title}</title><link>https://example.com/{len(title)}</link><pubDate>Thu, 08 Oct 2026 21:00:00 GMT</pubDate></item>'
        items, status = self.fetch(xml + '</channel></rss>', 1)
        self.assertEqual(status, "ok")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["fecha"], "2026-10-08 17:00")

    def test_missing_publication_date_is_not_fabricated(self):
        items, _ = self.fetch('<rss version="2.0"><channel><title>Test</title><item><title>Carolina</title><link>https://example.com/n</link></item></channel></rss>')
        self.assertEqual(items, [])

    def test_google_publisher_suffix_merges_with_direct_news(self):
        xml = '<rss version="2.0"><channel><title>Test</title><item><title>Noticia de Carolina - El Nuevo Día</title><link>https://news.google.com/rss/articles/test</link><source url="https://example.com">El Nuevo Día</source><pubDate>Thu, 08 Oct 2026 21:00:00 GMT</pubDate></item></channel></rss>'
        with patch("sources.rss_feeds.urllib.request.urlopen", return_value=io.BytesIO(xml.encode())), patch("sources.rss_feeds.now_local", return_value=NOW):
            items, _ = rss_feeds.fetch_rss("GN", "https://news.google.com/rss/search?q=Carolina")
        self.assertEqual(items[0]["titular"], "Noticia de Carolina")
        self.assertEqual(len(collector.deduplicate([article(), *items])), 1)

    def test_direct_feed_does_not_strip_publisher_text(self):
        xml = '<rss version="2.0"><channel><title>Test</title><item><title>Noticia de Carolina - El Nuevo Día</title><link>https://example.com/n</link><source>El Nuevo Día</source><pubDate>Thu, 08 Oct 2026 21:00:00 GMT</pubDate></item></channel></rss>'
        items, _ = self.fetch(xml)
        self.assertEqual(items[0]["titular"], "Noticia de Carolina - El Nuevo Día")

    @patch.dict("os.environ", {"NEWS_API_KEY": ""})
    def test_missing_api_key_is_a_warning(self):
        _, status = newsapi_source.fetch_newsapi(return_status=True)
        self.assertIn("⚠️", status)

    def test_unknown_scrape_date_stays_unknown(self):
        self.assertEqual(scraper.parse_date("not a date"), "")
        self.assertEqual(scraper.parse_date("October 8, 2026"), "2026-10-08")
        self.assertEqual(scraper.parse_date("February 30, 2026"), "")

    def test_scraping_http_failure_has_error_status(self):
        statuses = {}
        with patch("sources.scraper.requests.get") as request:
            request.return_value.status_code = 503
            scraper.scrape_carolina787(status=statuses)
        self.assertIn("❌", statuses["Carolina787 (Scraping)"])


class RenderingAndStateTests(unittest.TestCase):
    @patch("sources.collector.now_local", return_value=NOW)
    def test_breaking_banner_time_updates_like_table_time(self, _):
        from bs4 import BeautifulSoup
        html = renderer.generate_html([article("Emergencia en Carolina")], {}, {})
        banner_time = BeautifulSoup(html, "html.parser").select_one(".breaking-section .time-ago[data-date]")
        self.assertIsNotNone(banner_time)
        self.assertEqual(banner_time["data-date"], "2026-10-08T17:00:00-04:00")

    def test_untrusted_text_is_escaped_and_dates_have_offsets(self):
        item = article('<img src=x onerror=alert(1)> Carolina')
        html = renderer.generate_html([item], {}, {}, [{"fuente": "<script>bad</script>", "posts": [{"texto": "<img src=x onerror=alert(1)>", "fecha": "<b>x</b>"}]}])
        self.assertIn("&lt;img", html)
        self.assertNotIn("<script>bad</script>", html)
        self.assertIn("2026-10-08T17:00:00-04:00", html)
        self.assertNotIn("time_ago", item)

    def test_empty_dashboard_renders(self):
        html = renderer.generate_html([], {}, {})
        self.assertIn("No se encontraron resultados", html)
        self.assertNotIn("{{", html)

    def test_malformed_state_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            for raw in ['[]', 'null', '{broken', '{"seen":null}', '{"seen":[null,3,"valid"]}']:
                path.write_text(raw)
                with patch.object(state, "STATE_FILE", path):
                    loaded = state.load_state()
                    self.assertIsInstance(loaded["seen"], list)
                    self.assertTrue(all(isinstance(key, str) for key in loaded["seen"]))

    def test_failed_atomic_replace_preserves_old_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.html"
            path.write_text("old")
            with patch("sources.state.os.replace", side_effect=OSError("disk error")):
                with self.assertRaises(OSError):
                    state.write_text_atomic(path, "new")
            self.assertEqual(path.read_text(), "old")
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_total_source_failure_preserves_existing_dashboard(self):
        import dashboard
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.html"
            path.write_text("last good page")
            with patch.object(dashboard, "OUTPUT_FILE", path), patch.object(dashboard, "collect_all", return_value=([], {"Test": "❌ Timeout"}, [])), patch.object(dashboard, "load_state", return_value={}), patch.object(dashboard, "save_state") as save:
                with self.assertRaises(RuntimeError):
                    dashboard.main()
                self.assertEqual(path.read_text(), "last good page")
                save.assert_not_called()

    def test_successful_generation_saves_complete_html_and_seen_state(self):
        import dashboard
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.html"
            with patch.object(dashboard, "OUTPUT_FILE", path), patch.object(dashboard, "collect_all", return_value=([article()], {"Test": "✅ OK"}, [])), patch.object(dashboard, "filter_recent", side_effect=lambda a, **_: a), patch.object(dashboard, "load_state", return_value={}), patch.object(dashboard, "save_state") as save:
                dashboard.main()
                self.assertIn("Noticia de Carolina", path.read_text())
                self.assertIn(collector.article_key(article()), save.call_args.args[0]["seen"])

    def test_renderer_failure_does_not_save_seen_state(self):
        import dashboard
        with patch.object(dashboard, "collect_all", return_value=([article()], {"Test": "✅ OK"}, [])), patch.object(dashboard, "filter_recent", side_effect=lambda a, **_: a), patch.object(dashboard, "load_state", return_value={}), patch.object(dashboard, "generate_html", side_effect=RuntimeError("template error")), patch.object(dashboard, "save_state") as save:
            with self.assertRaises(RuntimeError):
                dashboard.main()
            save.assert_not_called()


class ReliabilityTests(unittest.TestCase):
    @patch("sources.collector.now_local", return_value=NOW)
    def test_partial_failure_retains_recent_verified_news_with_original_time(self, _):
        old = dict(article(), ultima_verificacion="2026-10-08T16:00:00-04:00")
        stored = {"article_cache": [old], "source_health": {"Prueba": {"last_success": old["ultima_verificacion"]}}}
        result = collector.preserve_failed_sources([], {"Prueba": "❌ HTTP 429", "Otra": "✅ OK"}, stored)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["conservada"])
        self.assertEqual(result[0]["fecha"], old["fecha"])
        self.assertEqual(result[0]["ultima_verificacion"], old["ultima_verificacion"])
        self.assertEqual(stored["source_health"]["Prueba"]["last_success"], old["ultima_verificacion"])
        self.assertEqual(stored["source_health"]["Prueba"]["retained"], 1)

    @patch("sources.collector.now_local", return_value=NOW)
    def test_success_with_zero_articles_does_not_restore_old_news(self, _):
        stored = {"article_cache": [article()]}
        self.assertEqual(collector.preserve_failed_sources([], {"Prueba": "✅ OK"}, stored), [])
        self.assertEqual(stored["source_health"]["Prueba"]["count"], 0)
        self.assertEqual(stored["source_health"]["Prueba"]["last_success"], NOW.isoformat())

    @patch("sources.collector.now_local", return_value=NOW)
    def test_cache_expiration_and_corruption_do_not_break_collection(self, _):
        stored = {"article_cache": [None, {}, article(date="2026-10-06 12:00"), article(date="2026-10-09 12:00"), article(link="javascript:alert(1)")], "source_health": {"Prueba": None}}
        self.assertEqual(collector.preserve_failed_sources([], {"Prueba": "❌ Timeout"}, stored), [])

    @patch("sources.collector.now_local", return_value=NOW)
    def test_fresh_duplicate_wins_and_all_source_counts_are_kept(self, _):
        stored = {"article_cache": [article()]}
        fresh = dict(article(), fuente="Otra")
        result = collector.preserve_failed_sources([fresh], {"Prueba": "❌ Timeout", "Otra": "✅ OK"}, stored)
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["conservada"])
        self.assertEqual(stored["source_health"]["Otra"]["count"], 1)
        merged = collector.deduplicate([article(), fresh])
        stored = {}
        collector.preserve_failed_sources(merged, {"Prueba": "✅ OK", "Otra": "✅ OK"}, stored)
        self.assertEqual(stored["source_health"]["Otra"]["count"], 1)
        self.assertEqual(stored["source_health"]["Prueba"]["count"], 1)

    @patch("sources.collector.now_local", return_value=NOW)
    def test_rss_group_failure_restores_individual_sources(self, _):
        stored = {"article_cache": [dict(article(), tipo="RSS")]}
        result = collector.preserve_failed_sources([], {"RSS - General": "❌ Timeout"}, stored)
        self.assertTrue(result[0]["conservada"])

    def test_explicit_foreign_context_and_artist_do_not_match(self):
        for value in ["Soge Culebra estrena una canción", "San Juan, Argentina", "La Ceiba, Honduras", "Río Grande do Sul", "Río Grande, Texas", "Carolina Panthers"]:
            self.assertEqual(rss_feeds.mentions_municipio(value), [])
        self.assertEqual(rss_feeds.mentions_municipio("San Juan, Puerto Rico recibe visitantes de San Juan, Argentina"), ["San Juan"])
        self.assertTrue(rss_feeds.is_relevant_title("Carolina recibe visitantes de China"))

    @patch("sources.collector.now_local", return_value=NOW)
    def test_health_details_are_escaped_and_cached_news_are_not_breaking(self, _):
        from bs4 import BeautifulSoup
        stored = {"last_successful_collection": NOW.isoformat(), "source_health": {"Prueba": {"last_success": NOW.isoformat(), "count": None, "retained": 1}}}
        item = dict(article("Emergencia en Carolina"), conservada=True, ultima_verificacion=NOW.isoformat())
        html = renderer.generate_html([item], {"Prueba": "❌ <script>bad</script>"}, stored)
        soup = BeautifulSoup(html, "html.parser")
        self.assertEqual(soup.select_one("#freshnessNotice")["data-collected-at"], NOW.isoformat())
        self.assertIsNotNone(soup.select_one(".badge-retained"))
        self.assertIsNone(soup.select_one(".breaking-section"))
        self.assertNotIn("<script>bad</script>", html)
        self.assertIn("Sin dato", soup.select_one(".health-details").get_text())

    def test_weekly_reset_preserves_cache_and_health(self):
        import dashboard
        stored = {"seen": ["old"], "session_date": "2026-10-01", "article_cache": [article()]}
        with tempfile.TemporaryDirectory() as directory, patch.object(dashboard, "OUTPUT_FILE", Path(directory) / "index.html"), patch.object(dashboard, "now_local", return_value=NOW), patch("sources.collector.now_local", return_value=NOW), patch.object(dashboard, "should_reset_weekly", return_value=True), patch.object(dashboard, "load_state", return_value=stored), patch.object(dashboard, "collect_all", return_value=([], {"Prueba": "❌ Timeout", "Otra": "✅ OK"}, [])), patch.object(dashboard, "save_state") as save:
            dashboard.main()
            saved = save.call_args.args[0]
            self.assertTrue(saved["article_cache"][0]["conservada"])
            self.assertFalse(saved["article_cache"][0]["es_nueva"])
            self.assertEqual(saved["last_successful_collection"], NOW.isoformat())


if __name__ == "__main__":
    unittest.main()
