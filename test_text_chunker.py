"""Unit tests for text_chunker."""

from __future__ import annotations

import unittest

from text_chunker import chunk_text_for_tts, normalize_clipboard_text


class TestTextChunker(unittest.TestCase):
    def test_empty_and_whitespace(self) -> None:
        self.assertEqual(normalize_clipboard_text("   \n\t  "), "")
        self.assertEqual(chunk_text_for_tts("   \n\t  "), [])

    def test_first_chunk_stays_short_for_fast_ttfa(self) -> None:
        text = (
            "Hello there, this is a very long opening sentence with several clauses, "
            "designed to verify that the first chunk is kept short for fast startup, "
            "even before the period arrives. And here is a second sentence."
        )
        chunks = chunk_text_for_tts(text, first_chunk_max_chars=120, max_chunk_chars=320)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertLessEqual(len(chunks[0]), 120)

    def test_merges_short_trailing_sentences_within_limit(self) -> None:
        text = "First sentence. Second short one. Third short one."
        chunks = chunk_text_for_tts(text, first_chunk_max_chars=120, max_chunk_chars=320)
        self.assertEqual(chunks[0], "First sentence.")
        self.assertEqual(chunks[1], "Second short one. Third short one.")


if __name__ == "__main__":
    unittest.main()

