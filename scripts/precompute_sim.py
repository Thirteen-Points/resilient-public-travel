"""Generate the checked-in simulation result from declared scenario inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.sim.adapters import routes_from_contract
from backend.app.sim.cache import write_precomputed
from backend.app.sim.run import run_simulation


def validate_fixture_config(config: dict) -> None:
    """Prevent unverified fixture values from acquiring a stronger label."""

    if not config.get("fixture"):
        return
    if config.get("provenance") != "simulated":
        raise ValueError("fixture scenarios must be labelled simulated")
    mislabeled = [
        item.get("route_id", "<missing>")
        for item in config.get("route_supply", [])
        if item.get("provenance") != "simulated"
    ]
    if mislabeled:
        raise ValueError(f"fixture route supplies must be simulated: {mislabeled}")


def precompute(config_path: Path, output_directory: Path) -> Path:
    with config_path.open("r", encoding="utf-8") as stream:
        config = json.load(stream)
    validate_fixture_config(config)
    route_path = REPOSITORY_ROOT / config["route_source"]
    with route_path.open("r", encoding="utf-8") as stream:
        route_payload = json.load(stream)
    routes, supplies = routes_from_contract(
        route_payload,
        config["route_supply"],
        fixture=bool(config.get("fixture")),
    )
    result = run_simulation(
        scenario_id=config["scenario_id"],
        routes=routes,
        supplies=supplies,
        population=int(config["population"]),
        seed=int(config["seed"]),
        window_min=float(config["window_min"]),
        time_range=tuple(config["time_range"]),
        assumptions=list(config["assumptions"]),
    )
    return write_precomputed(result, output_directory)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=REPOSITORY_ROOT / "data" / "sim" / "scn_huh_exc_closed_am_peak.input.json",
    )
    parser.add_argument("--output", type=Path, default=REPOSITORY_ROOT / "data" / "sim")
    args = parser.parse_args()
    print(precompute(args.config.resolve(), args.output.resolve()))


if __name__ == "__main__":
    main()
