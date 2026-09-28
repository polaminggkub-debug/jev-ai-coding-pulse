"""Generated pages share explicit, responsive navigation and source-only detail."""
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest

import build
import reads


class NavigationParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_nav = False
        self.anchor = None
        self.links = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "nav" and attributes.get("aria-label") == "Pulse pages":
            self.in_nav = True
        elif self.in_nav and tag == "a":
            self.anchor = {"href": attributes.get("href"),
                           "current": attributes.get("aria-current"), "text": ""}

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor["text"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor is not None:
            self.links.append(self.anchor)
            self.anchor = None
        elif tag == "nav" and self.in_nav:
            self.in_nav = False


class GeneratedNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        source = root / "mentions.json"
        source.write_text("[]", encoding="utf-8")
        cls.pulse = root / "pulse.html"
        cls.sources = root / "sources.html"
        cls.reads = root / "reads.html"
        build.build(source, cls.pulse)
        reads.build(root / "empty-data", cls.reads, now="2026-09-28T00:00:00Z")
        cls.pages = {
            "index.html": cls.pulse.read_text(encoding="utf-8"),
            "reads.html": cls.reads.read_text(encoding="utf-8"),
            "sources.html": cls.sources.read_text(encoding="utf-8"),
        }

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_every_page_has_all_links_and_highlights_its_current_page(self):
        for current, page in self.pages.items():
            with self.subTest(page=current):
                parser = NavigationParser()
                parser.feed(page)
                self.assertEqual(
                    [(link["href"], link["text"].strip()) for link in parser.links],
                    [("index.html", "Rankings"), ("reads.html", "Worth reading"),
                     ("sources.html", "Sources & communities")],
                )
                active = [link["href"] for link in parser.links if link["current"] == "page"]
                self.assertEqual(active, [current])
                self.assertRegex(page, r'<meta name="viewport" content="width=device-width,initial-scale=1">')
                self.assertRegex(page, r'\.page-nav\s*\{[^}]*\bflex-wrap:\s*wrap\b')

    def test_source_chart_and_heatmap_live_only_on_the_sources_page(self):
        rankings = self.pages["index.html"]
        sources = self.pages["sources.html"]
        for moved_id in ("source-filter", "source-chart", "reddit-communities", "community-heatmap"):
            self.assertNotIn(f'id="{moved_id}"', rankings)
            self.assertIn(f'id="{moved_id}"', sources)
        self.assertIn("The source filter changes the charts on this page only.", sources)
        self.assertIn("GitHub issues are bug reports — not counted in main score.", sources)
        self.assertIn('<option value="github">GitHub</option>', sources)
        self.assertIn('id="trend-alerts"', rankings)
        self.assertIn('id="use-today"', rankings)
        self.assertIn('id="chart"', rankings)
        self.assertIn('id="search"', rankings)
        self.assertNotIn('id="trend-alerts"', sources)
        self.assertNotIn('id="use-today"', sources)

        ranking_meta = json.loads(rankings.split('id="pulse-meta" type="application/json">')[1]
                                  .split("</script>")[0])
        source_meta = json.loads(sources.split('id="pulse-meta" type="application/json">')[1]
                                 .split("</script>")[0])
        self.assertEqual(ranking_meta.get("page", "rankings"), "rankings")
        self.assertEqual(source_meta.get("page"), "sources")


if __name__ == "__main__":
    unittest.main()
