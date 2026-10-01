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
    load_contract_schemas,
    validate_seed_documents,
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
        cls.documents = load_seed_documents()
        cls.schemas = load_contract_schemas()

    def test_seed_has_three_valid_events_and_five_valid_signals(self) -> None:
        self.assertEqual(len(self.seed["events"]), 3)
        self.assertEqual(len(self.seed["signals"]), 5)
        for event in self.seed["events"]:
            Event.model_validate(event)
        for signal in self.seed["signals"]:
            Signal.model_validate(signal)

    def test_all_four_shared_seed_files_have_the_expected_root_shape(self) -> None:
        self.assertEqual(set(self.documents), set(SEED_FILENAMES))
        expected_top_level = {
            "network.seed.json": {"meta", "nodes", "lines", "walk_links"},
            "event.seed.json": {"meta", "events", "signals"},
            "routes.seed.json": {"meta", "routes", "persona_top_picks", "excluded_route_examples"},
            "sim.seed.json": {"scenario_id", "meta", "baseline", "guided"},
        }
        for filename, document in self.documents.items():
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

    def test_every_seed_passes_its_committed_schema(self) -> None:
        for filename in SEED_FILENAMES:
            with self.subTest(filename=filename):
                Draft202012Validator(self.schemas[filename]).validate(self.documents[filename])

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
            validate_seed_documents(self.documents, self.schemas),
            [],
        )

    def test_network_schema_rejects_unknown_fields_and_bad_references(self) -> None:
        documents = copy.deepcopy(self.documents)
        documents["network.seed.json"]["nodes"][0]["lat"] = "22.37"
        documents["network.seed.json"]["lines"][0]["unexpected"] = True
        documents["network.seed.json"]["lines"][0]["stops"][0] = "UNKNOWN"
        errors = validate_seed_documents(documents, self.schemas)
        self.assertTrue(any("nodes.0.lat" in error for error in errors), errors)
        self.assertTrue(any("unexpected" in error for error in errors), errors)
        self.assertTrue(any("unknown node IDs UNKNOWN" in error for error in errors), errors)

    def test_route_and_sim_seeds_reject_unknown_cross_file_ids(self) -> None:
        documents = copy.deepcopy(self.documents)
        documents["routes.seed.json"]["routes"][0]["legs"][0]["from"] = "UNKNOWN"
        documents["sim.seed.json"]["guided"]["shares"][0]["route_id"] = "unknown-route"
        errors = validate_seed_documents(documents, self.schemas)
        self.assertTrue(any("unknown node ID 'UNKNOWN'" in error for error in errors), errors)
        self.assertTrue(any("unknown route ID 'unknown-route'" in error for error in errors), errors)

    def test_validator_reports_malformed_nested_shapes_without_crashing(self) -> None:
        documents = copy.deepcopy(self.documents)
        documents["network.seed.json"]["meta"] = None
        documents["routes.seed.json"]["routes"][0]["legs"] = None
        documents["sim.seed.json"]["guided"] = None
        errors = validate_seed_documents(documents, self.schemas)
        self.assertTrue(any("network.seed.json" in error for error in errors), errors)
        self.assertTrue(any("routes.seed.json" in error for error in errors), errors)
        self.assertTrue(any("sim.seed.json" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
