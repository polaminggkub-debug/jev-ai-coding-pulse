"""HTML and CSS checks for network loads in the offline page."""

from html.parser import HTMLParser
from pathlib import Path
import re
from typing import List, Optional, Tuple

try:
    from .js_guard import _external_urls, js_external_loads
except ImportError:
    from js_guard import _external_urls, js_external_loads


def css_external_loads(css: str, source: str) -> List[str]:
    """Return external CSS @import and url() loads, ignoring comments."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    values = re.findall(r"(?is)url\(\s*(['\"]?)(.*?)\1\s*\)", css)
    values += re.findall(r"(?is)@import\s+(['\"])(.*?)\1", css)
    return [f"{source}: external CSS resource {url}"
            for _, value in values for url in _external_urls(value)]


class PageResources(HTMLParser):
    """Collect loading attributes and executable inline scripts/styles."""

    URL_ATTRIBUTES = {
        "audio": {"src"}, "base": {"href"}, "body": {"background"},
        "embed": {"src"}, "feimage": {"href", "xlink:href"},
        "iframe": {"src"}, "image": {"href", "xlink:href"},
        "img": {"src", "srcset", "href", "xlink:href"},
        "input": {"src"}, "link": {"href"}, "object": {"data"},
        "script": {"src"}, "source": {"src", "srcset"}, "table": {"background"},
        "td": {"background"}, "th": {"background"}, "track": {"src"},
        "use": {"href", "xlink:href"}, "video": {"src", "poster"},
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.failures: List[str] = []
        self.scripts: List[str] = []
        self.styles: List[str] = []
        self.capture = ""

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        self._check_attributes(tag, values)
        if tag == "iframe" and values.get("srcdoc"):
            nested = PageResources()
            nested.feed(values["srcdoc"])
            self.failures.extend(f"<iframe srcdoc> {issue}" for issue in nested.failures)
            for script in nested.scripts:
                self.failures.extend(js_external_loads(script, "<iframe srcdoc>"))
            for style in nested.styles:
                self.failures.extend(css_external_loads(style, "<iframe srcdoc>"))
        if tag == "script" and not values.get("src"):
            if values.get("type", "").lower() not in {"application/json", "application/ld+json"}:
                self.capture = "script"
        elif tag == "style":
            self.capture = "style"

    def _check_attributes(self, tag: str, values: dict) -> None:
        for name in self.URL_ATTRIBUTES.get(tag, set()):
            if tag == "link" and "canonical" in values.get("rel", "").lower():
                continue
            for url in _external_urls(values.get(name, "")):
                self.failures.append(f"<{tag} {name}> loads {url}")
        if tag == "meta" and values.get("http-equiv", "").lower() == "refresh":
            self.failures.extend(f"meta refresh loads {url}"
                                 for url in _external_urls(values.get("content", "")))
        self.failures.extend(css_external_loads(values.get("style", ""), f"<{tag} style>"))

    def handle_endtag(self, tag: str) -> None:
        if tag == self.capture:
            self.capture = ""

    def handle_data(self, data: str) -> None:
        if self.capture == "script":
            self.scripts.append(data)
        elif self.capture == "style":
            self.styles.append(data)


def page_load_failures(page: Path, root: Path) -> List[str]:
    """Check built-page resources, inline code, and runtime JS/CSS sources."""
    parser = PageResources()
    parser.feed(page.read_text(encoding="utf-8"))
    failures = [f"{page.name}: {issue}" for issue in parser.failures]
    for style in parser.styles:
        failures.extend(css_external_loads(style, page.name))
    for script in parser.scripts:
        failures.extend(js_external_loads(script, page.name))
    pipeline = root / "pipeline"
    for source in sorted(pipeline.rglob("*.js")):
        if source.name.startswith("test_") or source.name == "ui_harness.js":
            continue
        failures.extend(js_external_loads(source.read_text(encoding="utf-8"), str(source.relative_to(root))))
    for source in sorted(pipeline.rglob("*.css")):
        failures.extend(css_external_loads(source.read_text(encoding="utf-8"), str(source.relative_to(root))))
    return failures
