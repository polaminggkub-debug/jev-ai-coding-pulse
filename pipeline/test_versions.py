import unittest

from registry import mentions
from versions import extract_version


class ExtractVersionTests(unittest.TestCase):
    def test_comment_version_wins_over_thread_title(self):
        self.assertEqual(
            extract_version("Claude Opus", "Opus 5.5 is much better", "Opus 5.4 discussion"),
            "Opus 5.5",
        )

    def test_uses_thread_title_when_comment_has_no_version(self):
        self.assertEqual(
            extract_version("Qwen", "Qwen has been great", "Qwen3.8 release thread"),
            "Qwen 3.8",
        )

    def test_returns_none_when_neither_has_a_version(self):
        self.assertIsNone(extract_version("Claude Opus", "I like Opus", "Claude model discussion"))

    def test_gpt_six_nicknames(self):
        for nickname in ("Astra", "Sol", "Luna", "Terra"):
            with self.subTest(nickname=nickname):
                self.assertEqual(extract_version("GPT / ChatGPT", f"{nickname} is my favorite"), f"GPT-6 {nickname}")
                self.assertEqual(extract_version("GPT / ChatGPT", f"GPT-6 {nickname}"), f"GPT-6 {nickname}")

    def test_gpt_version_and_family_scoping(self):
        self.assertEqual(extract_version("GPT / ChatGPT", "gpt-6 feels fast"), "GPT-6")
        self.assertIsNone(extract_version("Qwen", "I prefer GPT-6"))

    def test_deepseek_r_series(self):
        self.assertEqual(extract_version("DeepSeek", "DeepSeek-R1 is good at reasoning"), "DeepSeek R1")

    def test_registry_includes_xiaomi_mimo_in_open_zone(self):
        self.assertIn(("Xiaomi MiMo", "open"), mentions("Xiaomi MiMo is a coding model"))
        for nickname in ("Astra", "Sol", "Luna", "Terra"):
            with self.subTest(nickname=nickname):
                self.assertIn(("GPT / ChatGPT", "us"), mentions(nickname))

    def test_coding_tool_versions_require_the_tool_name(self):
        self.assertEqual(extract_version("Claude Code", "Claude Code v1.2.3 shipped"), "Claude Code 1.2.3")
        self.assertEqual(extract_version("Codex", "Codex version 0.9"), "Codex 0.9")
        self.assertIsNone(extract_version("Cursor", "Codex 0.9 is useful"))

    def test_costs_counts_and_percentages_are_not_versions(self):
        examples = (
            ("Cursor", "Claude 20 dollars is more useful than Cursor 20 dollars"),
            ("Codex", "Codex 2 weeks ago was fine"),
            ("Codex", "a codex 200$ subscription"),
            ("Claude Code", "Claude Code 80%, Pi 20%"),
            ("Claude Fable", "Fable 61/61 complete"),
        )
        for subject, text in examples:
            with self.subTest(subject=subject, text=text):
                self.assertIsNone(extract_version(subject, text))


if __name__ == "__main__":
    unittest.main()
