from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from backend.app.services.event_models import Event
from backend.app.services.signal_models import Signal
from scripts.generate_contract_schemas import schema_documents, write_schemas
from scripts.validate_contract_seeds import (
    SEED_FILENAMES,
    load_seed_documents,
    validate_seed_payload,
)


ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "contracts" / "seed" / "event.seed.json"
SCHEMA_DIR = ROOT / "contracts" / "schemas"


class ContractSeedTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        cls.event_schema = json.loads(
            (SCHEMA_DIR / "event.schema.json").read_text(encoding="utf-8")
        )
        cls.signal_schema = json.loads(
            (SCHEMA_DIR / "signal.schema.json").read_text(encoding="utf-8")
        )

    def test_seed_has_three_valid_events_and_five_valid_signals(self) -> None:
        self.assertEqual(len(self.seed["events"]), 3)
        self.assertEqual(len(self.seed["signals"]), 5)
        for event in self.seed["events"]:
            Event.model_validate(event)
        for signal in self.seed["signals"]:
            Signal.model_validate(signal)

    def test_all_four_shared_seed_files_are_readable_json_objects(self) -> None:
        documents = load_seed_documents()
        self.assertEqual(set(documents), set(SEED_FILENAMES))
        expected_top_level = {
            "network.seed.json": {"meta", "nodes", "lines", "walk_links"},
            "event.seed.json": {"meta", "events", "signals"},
            "routes.seed.json": {"meta", "routes"},
            "sim.seed.json": {"meta", "baseline", "guided"},
        }
        for filename, document in documents.items():
            with self.subTest(filename=filename):
                self.assertIsInstance(document, dict)
                self.assertTrue(expected_top_level[filename].issubset(document))

    def test_seed_passes_committed_json_schemas(self) -> None:
        for event in self.seed["events"]:
            Draft202012Validator(self.event_schema).validate(event)
        for signal in self.seed["signals"]:
            Draft202012Validator(self.signal_schema).validate(signal)

    def test_committed_schemas_match_current_models(self) -> None:
        documents = schema_documents()
        self.assertEqual(documents["event.schema.json"], self.event_schema)
        self.assertEqual(documents["signal.schema.json"], self.signal_schema)

    def test_schema_generation_is_deterministic_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            write_schemas(target)
            first = {path.name: path.read_bytes() for path in target.iterdir()}
            write_schemas(target)
            second = {path.name: path.read_bytes() for path in target.iterdir()}
        self.assertEqual(first, second)

    def test_event_schema_rejects_undefined_ui_state(self) -> None:
        event = copy.deepcopy(self.seed["events"][0])
        event["ui_state"] = "front-end-only hint"
        with self.assertRaises(ValidationError):
            Event.model_validate(event)
        self.assertTrue(
            list(Draft202012Validator(self.event_schema).iter_errors(event))
        )

    def test_signal_schema_requires_nullable_fields_to_be_present(self) -> None:
        for field in ("author_hint", "raw_url"):
            with self.subTest(field=field):
                signal = copy.deepcopy(self.seed["signals"][0])
                signal.pop(field)
                with self.assertRaises(ValidationError):
                    Signal.model_validate(signal)
                self.assertTrue(
                    list(Draft202012Validator(self.signal_schema).iter_errors(signal))
                )

    def test_ids_are_unique_and_every_signal_is_referenced(self) -> None:
        event_ids = [event["event_id"] for event in self.seed["events"]]
        signal_ids = [signal["signal_id"] for signal in self.seed["signals"]]
        referenced = {
            signal_id
            for event in self.seed["events"]
            for signal_id in event["signals"]
        }
        self.assertEqual(len(event_ids), len(set(event_ids)))
        self.assertEqual(len(signal_ids), len(set(signal_ids)))
        self.assertEqual(referenced, set(signal_ids))

    def test_seed_retains_three_demonstration_states(self) -> None:
        states = [
            (event["status"], event["confidence"])
            for event in self.seed["events"]
        ]
        self.assertEqual(
            states,
            [
                ("pending_review", 0.20),
                ("pending_review", 0.55),
                ("published", 0.90),
            ],
        )

    def test_complete_validator_accepts_seed(self) -> None:
        self.assertEqual(
            validate_seed_payload(
                self.seed, self.event_schema, self.signal_schema
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
