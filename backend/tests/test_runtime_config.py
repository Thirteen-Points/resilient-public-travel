from __future__ import annotations

import unittest

from backend.app.runtime_config import DEFAULT_CORS_ORIGINS, parse_cors_origins


class CorsOriginConfigTests(unittest.TestCase):
    def test_missing_value_keeps_local_development_origins(self) -> None:
        self.assertEqual(parse_cors_origins(None), DEFAULT_CORS_ORIGINS)
        self.assertEqual(parse_cors_origins("  "), DEFAULT_CORS_ORIGINS)

    def test_exact_origins_are_normalized_and_deduplicated(self) -> None:
        self.assertEqual(
            parse_cors_origins(" https://demo.example/ , https://demo.example "),
            ("https://demo.example",),
        )

    def test_wildcards_and_paths_are_rejected(self) -> None:
        for value in ("*", "https://demo.example/app", "file:///tmp"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, r"exact http\(s\) origins|wildcard"):
                parse_cors_origins(value)


if __name__ == "__main__":
    unittest.main()
