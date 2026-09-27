"""Offline tests for the standalone reads page builder."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import reads
from test_curator import NOW, five_praises, add_thread
import curator


class ReadsPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "data"
        self.output = Path(self.temp.name) / "reads.html"

    def tearDown(self):
        self.temp.cleanup()

    def test_build_embeds_curated_page_and_uses_local_styles_and_scripts(self):
        add_thread(self.root, "page", five_praises("page"), score=26, comments=11)
        curator.curate(self.root,
            lambda *_: {"s": {"choice": "yes", "probabilities": {"yes": 0.8}}}, now=NOW)

        with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            self.assertEqual(reads.build(self.root, self.output, now=NOW), 1)
        page = self.output.read_text(encoding="utf-8")
        payload = json.loads(page.split('id="reads-data" type="application/json">')[1]
                             .split("</script>")[0])

        self.assertIn('id="read-day"', page)
        self.assertIn('id="view-week"', page)
        self.assertIn("@media (max-width: 640px)", page)
        self.assertIn("data-theme=dark", page)
        self.assertIn("Reads.selectStories", page)
        self.assertNotIn("<script src=", page)
        self.assertNotIn("<link ", page)
        self.assertEqual(payload["daily"]["2026-09-28"][0]["score"], 26)
        self.assertEqual(payload["daily"]["2026-09-28"][0]["comments"], 11)

    def test_empty_page_has_a_named_day_option_and_no_network_assets(self):
        self.assertEqual(reads.build(self.root, self.output, now=NOW), 0)
        page = self.output.read_text(encoding="utf-8")
        payload = json.loads(page.split('id="reads-data" type="application/json">')[1]
                             .split("</script>")[0])

        self.assertIn("No curated days yet", page)
        self.assertEqual(payload["today"], "2026-09-28")
        self.assertEqual(payload["default_day"], "2026-09-28")
        self.assertNotIn("<script src=", page)
        self.assertNotIn('<link rel="stylesheet" href="http', page)


if __name__ == "__main__":
    unittest.main()
