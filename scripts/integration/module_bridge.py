"""Test-only wiring of actual module implementations; contains no traffic algorithms."""
from copy import deepcopy
from pathlib import Path

from backend.app.engine import RouteEngine
from backend.app.engine.load_provider import FixtureLoadProvider
from backend.app.graph.adapter import MappingDataAdapter
from backend.app.sim.adapters import routes_from_c_route_output
from backend.app.sim.run import run_simulation
from .checks import load_json

ROOT = Path(__file__).resolve().parents[2]

class ModuleBridge:
    def __init__(self, scenario_path=None):
        self.config = load_json(scenario_path or ROOT / "tests/cross_module/fixtures/scenario.json")
        if self.config["provenance"] != "simulated":
            raise ValueError("Test bridge requires a simulated scenario")
        self.network = load_json(ROOT / self.config["network_source"])
        self.engine = RouteEngine.from_adapter(
            MappingDataAdapter(self.network, baseline_fare=self.config["baseline_fare_hkd"]),
            load_provider=FixtureLoadProvider(self.config["zero_demand"]))

    def query(self, profile=None):
        return self.engine.query_details(self.config["origin"], self.config["destination"],
                                         self.config["depart_at"], profile)

    @staticmethod
    def supplies(details):
        # Internal RouteSupply envelope only; public RouteCandidate[] is unchanged.
        return [dict(details["route_parameters"][r["route_id"]], route_id=r["route_id"])
                for r in details["routes"]]

    def simulate(self, details):
        options, supplies = routes_from_c_route_output(details, fixture=True)
        return run_simulation(scenario_id="integration_" + details["graph_snapshot"], routes=options,
                              supplies=supplies, population=self.config["population"], seed=self.config["seed"],
                              window_min=self.config["window_min"],
                              assumptions=[self.config["note"], "All values are simulated. No verified C-Data input.",
                                           "Zero-demand route cards prime routing; C-Sim generates its own fixed-seed population."])

    def closure(self, status="published", version=1):
        event = deepcopy(load_json(ROOT / "tests/integration/fixtures/simulated-contracts.json")["objects"]["Event"])
        line = self.network["lines"][0]
        event.update(event_id="integration_closure", line=line["id"], mode=line["mode"],
                     status=status, version=version, expires_at=None)
        event["affected_segments"] = [{"from_node":line["stops"][0], "to_node":line["stops"][1],
                                      "impact":"closed", "capacity_factor":0}]
        return event
