"""Regression contract for the public Lobsters JSON payload shape."""
import datetime as dt
import unittest

from fetch_lobsters import TAGS, fetch_lobsters
from source_utils import iso_utc

NOW = dt.datetime.fromisoformat("2026-09-28T12:00:00+00:00").timestamp()


def story(tag, suffix, score, created):
    return {
        "short_id": f"{tag}-{suffix}",
        "title": f"{tag} AI coding tools discussion",
        "score": score,
        "created_at": iso_utc(created),
        "url": f"https://example.test/{tag}/{suffix}",
        "short_id_url": f"https://lobste.rs/s/{tag}-{suffix}/discussion",
    }


class LobstersContractTests(unittest.TestCase):
    def test_live_commenting_user_shape_keeps_both_tags_and_source_contract(self):
        tag_calls = []
        stories = {
            tag: [
                story(tag, "below-threshold", 4, NOW - 3600),
                story(tag, "too-old", 99, NOW - 6 * 86400),
                story(tag, "kept", 5, NOW - 3600),
            ]
            for tag in TAGS
        }

        def fake(url):
            for tag in TAGS:
                if url.endswith(f"/t/{tag}.json"):
                    tag_calls.append(tag)
                    return stories[tag]
            if "/s/" in url:
                short_id = url.rsplit("/", 1)[-1].removesuffix(".json")
                return {"comments": [
                    {
                        "short_id": f"comment-{short_id}",
                        "comment": "Claude Code helped with this migration",
                        "created_at": iso_utc(NOW - 600),
                        "score": 2,
                        "commenting_user": "lobster_user",
                        "url": f"https://lobste.rs/c/comment-{short_id}",
                    },
                    {
                        "short_id": f"old-comment-{short_id}",
                        "comment": "Old comment outside the source window",
                        "created_at": iso_utc(NOW - 6 * 86400),
                        "score": 10,
                        "commenting_user": "old_user",
                        "url": f"https://lobste.rs/c/old-comment-{short_id}",
                    },
                ]}
            raise AssertionError(f"Unexpected Lobsters endpoint: {url}")

        listing = fetch_lobsters(now=NOW, http_get=fake)[0]

        self.assertEqual(set(tag_calls), set(TAGS))
        self.assertEqual(len(listing["top"]), len(TAGS))
        kept = {post["id"].split(":", 1)[1]: post for post in listing["top"]}
        self.assertEqual(set(kept), {f"{tag}-kept" for tag in TAGS})
        for tag in TAGS:
            post = kept[f"{tag}-kept"]
            self.assertEqual(post["score"], 5)
            self.assertEqual(post["url"], f"https://lobste.rs/s/{tag}-kept/discussion")
            self.assertEqual(len(post["comments"]), 1)
            self.assertEqual(post["comments"][0]["author"], "lobster_user")


if __name__ == "__main__":
    unittest.main()
