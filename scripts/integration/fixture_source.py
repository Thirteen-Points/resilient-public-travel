"""File/data-loader boundary for invented contract fixtures, never a route algorithm."""
from copy import deepcopy
from pathlib import Path

from .checks import Finding, check_events, check_network, check_route, load_json
from .contracts import CONTRACTS, validate_payload

DEFAULT_FIXTURE = Path(__file__).resolve().parents[2] / "tests/integration/fixtures/simulated-contracts.json"


class FixtureSource:
    """Inject a JSON loader; callers always receive copies and no values are repaired."""
    def __init__(self, path=DEFAULT_FIXTURE, loader=load_json):
        self.path = Path(path)
        self._data = loader(self.path)
        if self._data.get("fixture_meta", {}).get("provenance") != "simulated":
            raise ValueError("Fixture envelope must be simulated")
        self._verify_labels(self._data)

    @classmethod
    def _verify_labels(cls, value):
        if isinstance(value, dict):
            if "provenance" in value and value["provenance"] != "simulated":
                raise ValueError("Invented fixture data must never be labelled real/real-derived")
            for item in value.values():
                cls._verify_labels(item)
        elif isinstance(value, list):
            for item in value:
                cls._verify_labels(item)

    def get(self, kind):
        return deepcopy(self._data["objects"][kind])

    def network(self):
        return deepcopy(self._data["network"])


def validate_fixture(source):
    findings = []
    for kind in CONTRACTS:
        try:
            findings.extend(validate_payload(kind, source.get(kind)))
        except KeyError:
            findings.append(Finding("REQUIRED", kind, "Fixture object missing"))
    if findings:
        return findings
    network = source.network()
    findings.extend(check_network(network))
    findings.extend(check_events({"events": [source.get("Event")], "signals": [source.get("Signal")]}, network))
    route = source.get("RouteCandidate")
    findings.extend(check_route(route, network, wheelchair=True))
    return findings
