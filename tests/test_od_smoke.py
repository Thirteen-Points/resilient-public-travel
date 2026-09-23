from scripts.od_smoke import build_od_pairs, summarize_response


def test_default_six_nodes_form_thirty_directed_pairs():
    pairs = build_od_pairs(["TAW", "KOT", "MKK", "HUH", "EXC", "ADM"])
    assert len(pairs) == 30
    assert ("TAW", "ADM") in pairs
    assert ("ADM", "TAW") in pairs
    assert all(origin != destination for origin, destination in pairs)


def test_route_summary_preserves_status_count_provenance_and_errors():
    good = summarize_response(200, [{"route_id": "r1", "provenance": "simulated"},
                                    {"route_id": "r2", "provenance": "simulated"}])
    assert good == {"http_status": 200, "candidate_count": 2,
                    "provenance": ["simulated"], "error": None}
    bad = summarize_response(503, {"error": {"code": "DATA_UNAVAILABLE"}})
    assert bad["http_status"] == 503
    assert bad["candidate_count"] == 0
    assert "DATA_UNAVAILABLE" in bad["error"]
