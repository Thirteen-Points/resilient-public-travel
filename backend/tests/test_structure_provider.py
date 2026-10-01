"""Check T2.6 transport wiring and simulated-corpus rejection without network."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.ai.llm_client import Provider
from backend.app.services.structure.provider_client import StructureJsonClient
from scripts.run_t2_6_acceptance import load_real_samples


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self):
        return b'{"choices":[{"message":{"content":"{\\"event_type\\":\\"other\\"}"}}]}'


class StructureProviderTests(unittest.TestCase):
    def test_json_mode_passes_schema_and_returns_content(self):
        provider = Provider("test", "https://provider.invalid/v1", "secret", "model-a")
        with patch("urllib.request.urlopen", return_value=_Response()) as send:
            content = StructureJsonClient(provider).generate_json(
                system_prompt="system", user_prompt="untrusted text", json_schema={"type": "object"},
                timeout_seconds=3,
            )
        self.assertEqual(content, '{"event_type":"other"}')
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, "https://provider.invalid/v1/chat/completions")
        self.assertEqual(send.call_args.kwargs["timeout"], 3)
        body = json.loads(request.data)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertIn('"type": "object"', body["messages"][0]["content"])

    def test_simulated_corpus_is_rejected_before_provider_use(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "samples.json"
            path.write_text(json.dumps({"meta": {"provenance": "simulated"}, "samples": []}),
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "real-text corpus"):
                load_real_samples(path)


if __name__ == "__main__":
    unittest.main()
