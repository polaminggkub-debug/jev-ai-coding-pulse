"""Adversarial examples for the offline source guards."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from js_guard import js_external_loads, js_functions
from page_guard import PageResources, css_external_loads


class StructureGuardTests(unittest.TestCase):
    def test_multiline_arrow_and_async_method_are_counted(self):
        body = "\n".join("    renderPart();" for _ in range(51))
        source = f"const draw = (item) => {{\n{body}\n}}"
        source += f"\nclass View {{\n  async update() {{\n{body}\n  }}\n}}"
        spans = js_functions(source)
        self.assertGreaterEqual(sum(span > 50 for _, _, span in spans), 2)

    def test_control_blocks_and_calls_are_not_functions(self):
        source = "if (ready) { run(); }\nwhile (pending) { wait(); }"
        self.assertEqual(js_functions(source), [])

    def test_anchor_links_are_allowed_but_resources_are_rejected(self):
        parser = PageResources()
        parser.feed('<a href="https://reddit.com/post">thread</a>'
                    '<script src="https://cdn.test/app.js"></script>')
        self.assertEqual(len(parser.failures), 1)
        self.assertIn("script", parser.failures[0])

    def test_svg_and_srcdoc_resource_loads_are_checked(self):
        parser = PageResources()
        parser.feed('<svg><image href="https://img.test/a.svg"></image>'
                    '<use xlink:href="//cdn.test/sprite.svg#logo"></use></svg>'
                    '<iframe srcdoc="&lt;img src=https://img.test/nested.png&gt;'
                    '&lt;script&gt;fetch(&amp;quot;https://api.test/data&amp;quot;)&lt;/script&gt;'
                    '&lt;style&gt;body{background:url(https://cdn.test/a.css)}&lt;/style&gt;'
                    '"></iframe>')
        self.assertEqual(len(parser.failures), 5)

    def test_css_and_javascript_network_loads_are_checked(self):
        self.assertTrue(css_external_loads('@import "https://cdn.test/a.css";', 'style'))
        failures = js_external_loads("fetch('https://api.test/data')", 'script')
        self.assertTrue(any("fetch" in issue for issue in failures))
        self.assertEqual(js_external_loads("a.href = 'https://reddit.com/post'", 'script'), [])


if __name__ == "__main__":
    unittest.main()
