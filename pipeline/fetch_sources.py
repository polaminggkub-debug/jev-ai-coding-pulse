"""Run independent free sources and persist one normalized source snapshot."""
import json
from pathlib import Path
import sys

try:
    from .fetch_bluesky import fetch_bluesky
    from .fetch_devto import fetch_devto
    from .fetch_github import fetch_github
    from .fetch_hn import fetch_hn
    from .fetch_lobsters import fetch_lobsters
except ImportError:
    from fetch_bluesky import fetch_bluesky
    from fetch_devto import fetch_devto
    from fetch_github import fetch_github
    from fetch_hn import fetch_hn
    from fetch_lobsters import fetch_lobsters

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data' / 'incoming-sources.json'
FETCHERS = (fetch_hn, fetch_github, fetch_bluesky, fetch_devto, fetch_lobsters)


def run_sources(output_path=OUTPUT, *, fetchers=None):
    """Save successful source lists, isolating a broken adapter from all others."""
    listings = []
    for fetcher in (FETCHERS if fetchers is None else fetchers):
        try:
            listings.extend(fetcher() or [])
        except Exception as error:
            print(f"Source {fetcher.__module__} failed: {type(error).__name__}", file=sys.stderr)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + '.tmp')
    temporary.write_text(json.dumps(listings, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    temporary.replace(destination)
    return listings


if __name__ == '__main__':
    print(f"Fetched {len(run_sources())} source community listings.")
