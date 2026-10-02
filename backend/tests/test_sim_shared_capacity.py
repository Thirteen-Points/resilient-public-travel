from dataclasses import replace

import pytest

from backend.app.engine.load import RouteSupply
from backend.app.sim.adapters import ODRouteSet
from backend.app.sim.m2 import _guided_multi_od, run_m2_multi_od
from backend.app.sim.models import Agent, RouteOption
from backend.app.sim.shared_capacity import SharedResource, resources_from_seed, resources_from_snapshot
from backend.app.sim.service import build_diversion_plan


def route(rid, eta=10, accessible=True):
    return RouteOption(rid, eta, 0, 0, 0, 1, ("MTR",), accessible)


def supply(rid, capacity=1000):
    return RouteSupply(rid, 3600, capacity, eta_max_factor=1)


def simulate(route_sets, resources, population=100):
    return run_m2_multi_od(scenario_id="shared-segment-test", route_sets=route_sets,
                           population=population, seed=20260922, window_min=60,
                           time_range=("08:00", "09:00"), assumptions=["simulated test"],
                           shared_resources=resources)


def test_distinct_route_ids_share_one_physical_segment_and_conserve_demand():
    sets = (ODRouteSet("A", "B", (route("ab"),), (supply("ab"),), 1, "simulated"),
            ODRouteSet("A", "C", (route("ac"),), (supply("ac"),), 1, "simulated"))
    resources = (SharedResource("L:A->B", ("ab", "ac"), 20, 3600, 1),)
    result = simulate(sets, resources)
    assert result == simulate(sets, resources)
    assert result["guided"]["served_demand"] == 20
    assert result["baseline"]["served_demand"] == 20
    assert result["baseline"]["resource_load"][0]["physical_capacity_excess"] == 80
    assert result["guided"]["resource_load"][0]["physical_capacity_excess"] == 0
    assert result["guided"]["protected_unmet"] == 0
    assert result["guided"]["wheelchair_unmet"] == 0
    for policy in ("baseline", "guided"):
        metrics = result[policy]
        assert metrics["served_demand"] + metrics["unmet_demand"] == 100
        assert metrics["assigned_demand"] + metrics["unassigned_demand"] == 100


def test_no_capacity_pressure_keeps_personal_best_instead_of_large_bucket():
    routes = (route("best", eta=10), route("large-slower", eta=20))
    sets = (ODRouteSet("A", "B", routes, (supply("best", 1000), supply("large-slower", 2000)), 1, "simulated"),)
    result = simulate(sets, ())
    assert result["guided"]["total_delay_person_min"] == result["baseline"]["total_delay_person_min"]
    assert result["guided"]["route_load"][0]["assigned_users"] == 100
    assert result["guided"]["route_load"][1]["assigned_users"] == 0


def test_shared_capacity_never_overrides_accessibility_or_extra_delay_limit():
    routes = (route("best"), route("stairs", eta=11, accessible=False), route("too-late", eta=26))
    sets = (ODRouteSet("A", "B", routes, tuple(supply(item.route_id) for item in routes), 1, "simulated"),)
    agents = (Agent("a1", "A", "B", "wheelchair", "wheelchair", 400),
              Agent("a2", "A", "B", "wheelchair", "wheelchair", 400))
    assignments, _ = _guided_multi_od(agents, sets,
                                     {agent.agent_id: list(routes) for agent in agents}, 60,
                                     (SharedResource("limited", ("best",), 1, 3600, 1),))
    assert assignments == {"a1": "best"}


def test_shared_resources_fail_closed_on_conflicting_or_unknown_identity():
    sets = (ODRouteSet("A", "B", (route("ab"),), (supply("ab"),), 1, "simulated"),)
    with pytest.raises(ValueError, match="unknown routes"):
        simulate(sets, (SharedResource("L:A->B", ("missing",), 20, 3600),))
    resource = SharedResource("L:A->B", ("ab",), 20, 3600)
    with pytest.raises(ValueError, match="duplicate shared resource_id"):
        simulate(sets, (resource, resource))
    assert simulate(sets, (replace(resource, service_capacity_per_hour=0),))["guided"]["served_demand"] == 0


def test_seed_resources_pool_partial_overlap_but_separate_direction_and_segment():
    network = {"lines": [{"id": "L", "stops": ["A", "B", "C"],
                           "capacity_per_vehicle": 20, "headway_s": {"peak": 3600}}]}
    def raw(rid, origin, destination):
        return {"route_id": rid, "legs": [{"mode": "MTR", "line": "L", "from": origin,
                                           "to": destination, "headway_s": 3600}]}
    resources = resources_from_seed(network, [{"routes": [raw("ab", "A", "B"), raw("ac", "A", "C"),
                                                          raw("bc", "B", "C"), raw("ca", "C", "A")]}], "peak")
    membership = {item.resource_id: item.route_ids for item in resources}
    assert membership["L:A->B"] == ("ab", "ac")
    assert membership["L:B->C"] == ("ac", "bc")
    assert membership["L:C->B"] == ("ca",)
    assert membership["L:B->A"] == ("ca",)


def test_supply_tuple_order_does_not_change_route_supply_pairing():
    sets = (ODRouteSet("A", "B", (route("ab"), route("ac")), (supply("ab"), supply("ac", 1)), 1, "simulated"),)
    assert simulate(sets, ()) == simulate((replace(sets[0], supplies=tuple(reversed(sets[0].supplies))),), ())


def test_aggregate_diversion_deduplicates_identical_routes_and_rejects_conflicts():
    raw = {"route_id": "r", "headway_s": 3600, "capacity_per_hour": 20, "provenance": "simulated"}
    payload = {"event_id": "evt", "demand": 100, "routes": [raw, raw]}
    assert build_diversion_plan(payload)["unstoppable_demand"] == 80
    with pytest.raises(ValueError, match="conflicting supply"):
        build_diversion_plan({**payload, "routes": [raw, {**raw, "capacity_per_hour": 21}]})


def test_aggregate_diversion_consumes_shared_segment_only_once():
    raw = {"headway_s": 3600, "capacity_per_hour": 100, "provenance": "simulated"}
    payload = {"event_id": "evt", "demand": 100,
               "routes": [{**raw, "route_id": "a"}, {**raw, "route_id": "b"}],
               "shared_resources": [{"resource_id": "shared", "route_ids": ["a", "b"],
                                      "service_capacity_per_hour": 20, "headway_s": 3600, "target_factor": 1}]}
    result = build_diversion_plan(payload)
    assert sum(item["users"] for item in result["shares"]) == 20
    assert result["unstoppable_demand"] == 80


@pytest.mark.parametrize("bad_demand", [True, 1.5, -1])
def test_aggregate_diversion_rejects_non_integer_or_negative_demand(bad_demand):
    with pytest.raises(ValueError, match="non-negative integer"):
        build_diversion_plan({"event_id": "evt", "demand": bad_demand, "routes": []})


def test_snapshot_projection_applies_reduced_capacity_once_and_rejects_stale_graph():
    from backend.app.engine.service import RouteEngine

    engine = RouteEngine.from_seed()
    at = "2026-09-22T08:20:00+08:00"
    detail = engine.query_details("TAW", "ADM", at, {"mobility": "standard"}, limit=10)
    before = resources_from_snapshot(engine.snapshots.current, detail, at)
    original = next(item for item in before if item.resource_id == "ERL:TAW->KOT")
    engine.snapshots.update_event({"event_id": "evt_capacity", "status": "published", "line": "ERL",
                                   "direction": "both", "affected_segments": [{"from_node": "TAW", "to_node": "KOT",
                                       "impact": "reduced_capacity", "capacity_factor": 0.5}]})
    with pytest.raises(ValueError, match="snapshots differ"):
        resources_from_snapshot(engine.snapshots.current, detail, at)
    detail = engine.query_details("TAW", "ADM", at, {"mobility": "standard"}, limit=10)
    current = next(item for item in resources_from_snapshot(engine.snapshots.current, detail, at)
                   if item.resource_id == "ERL:TAW->KOT")
    assert current.service_capacity_per_hour == original.service_capacity_per_hour / 2
    assert current.headway_s == original.headway_s * 2
