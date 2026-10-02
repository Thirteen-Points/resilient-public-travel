"""Reproduce P3 capacity/fairness evidence from the same frozen M2 input."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.sim.adapters import od_route_sets_from_contract
from backend.app.sim.m2 import run_m2_multi_od
from backend.app.sim.cache import write_precomputed
from backend.app.sim.shared_capacity import resources_from_seed


def main() -> None:
    out = ROOT / "data/sim"
    raw_input = (out / "m2-route-input.json").read_bytes()
    payload = json.loads(raw_input)
    route_sets = od_route_sets_from_contract(payload, fixture=True)
    network_bytes = (ROOT / "contracts/seed/network.seed.json").read_bytes()
    expected_hash = payload["data_version"]["network_sha256"]
    if hashlib.sha256(network_bytes).hexdigest() != expected_hash:
        raise ValueError("Frozen route input network hash differs from current seed; regenerate input before comparing")
    resources = resources_from_seed(json.loads(network_bytes), payload["od_route_sets"], "weekday_peak")
    common = dict(scenario_id=payload["scenario_id"] + "_p3_shared_segments",
                  route_sets=route_sets, population=payload["population"], seed=payload["seed"],
                  window_min=payload["window_min"], time_range=tuple(payload["time_range"]),
                  assumptions=[
                      "Same frozen 10000-person, 30-directed-OD M2 input and seed 20260922; all results remain simulated.",
                      "Explicit directed resources use the seed stop order, seed vehicle size and each route leg headway; a passenger consumes every traversed segment.",
                      "Opposite directions are independent and capacity is reusable on non-overlapping segments; overlapping route ids share a single segment budget.",
                      "Target capacity is 0.85 times physical throughput. Physical capacity is floored per 60-minute window; no observed residual demand is available.",
                      "Both policies use identical physical-capacity/protected-first boarding checks; guided retains personal best until a route or segment capacity constraint forces an alternative.",
                      "Wheelchair/elderly are protected first; accessibility/max-walk and 15-minute route extra-delay are hard constraints. Dedicated wheelchair berth/boarding-assistance throughput is unknown and not guaranteed.",
                      "Queue delays are the maximum route/segment bottleneck estimate, not a schedule-based network forecast. No train-by-train seat propagation, external passengers or inter-window carryover is modelled.",
                  ])
    started = perf_counter()
    result = run_m2_multi_od(**common, shared_resources=resources)
    repeated = run_m2_multi_od(**common, shared_resources=resources)
    if repeated != result:
        raise AssertionError("Fixed-seed simulation is not reproducible")
    duration = perf_counter() - started
    # A deliberately constrained fixture verifies that pooling remains active;
    # this 10% factor is a sensitivity input, not an observed residual load.
    stressed_resources = tuple(replace(item, service_capacity_per_hour=item.service_capacity_per_hour * 0.1)
                               for item in resources)
    stress_common = {**common, "scenario_id": common["scenario_id"] + "_residual_10pct",
                     "assumptions": [*common["assumptions"],
                                     "Stress-only sensitivity: every segment has 10% of simulated capacity available; factor is invented for testing, not measured."]}
    stressed = run_m2_multi_od(**stress_common, shared_resources=stressed_resources)
    write_precomputed(result, out)
    write_precomputed(stressed, out)
    old = json.loads((out / "m2-simulation-result.json").read_text(encoding="utf-8"))
    evidence = {
        "input_file": "data/sim/m2-route-input.json", "input_sha256": hashlib.sha256(raw_input).hexdigest(),
        "source_revision": "working-tree", "provenance": "simulated",
        "reproducible_equal": True, "two_runs_elapsed_s": round(duration, 3),
        "previous_model": {"source": "data/sim/m2-simulation-result.json", "baseline": old["baseline"],
                           "guided": old["guided"], "capacity_model": old["capacity_model"]},
        "resource_inputs": [asdict(item) for item in resources],
        "current_model": result, "stress_10pct_residual": stressed,
    }
    (out / "p3-shared-capacity-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = []
    for label, case in (("旧路线桶模型", old), ("P3 共享区段模型", result), ("P3 10% 残余容量压力输入", stressed)):
        rows.append(f"| {label} | {case['baseline']['total_delay_person_min']} | {case['guided']['total_delay_person_min']} | {case['baseline']['served_demand']} | {case['guided']['served_demand']} | {case['guided']['wheelchair_unmet']} |")
    report = "\n".join([
        "# P3 共享区段仿真验收", "", "固定 10,000 人、30 个有向 OD、seed 20260922；结果全部为 simulated。",
        f"同一输入 SHA-256：`{evidence['input_sha256']}`。两次完整结果一致，共耗时 {duration:.3f} 秒（本机计算耗时）。",
        "", "| 场景 | baseline 延误（人·分钟） | guided 延误 | baseline 已服务 | guided 已服务 | guided 轮椅未满足 |",
        "|---|---:|---:|---:|---:|---:|---:|", *rows, "",
        "P3 引导改为逐人选择个人排序中最高的可行路线；空闲容量不会单独成为绕行理由。共享段逐一扣减，基线与引导使用相同物理容量及保护优先上车规则。",
        "10% 场景仅用于运力敏感性与失败路径验证，不代表真实残余运力，也不承诺引导一定降低延误。未满足人数按物理上车容量计算，与未分配人数分开。",
        "", result["capacity_model"]["note"], "",
        "硬约束的 15 分钟上限只约束所选路线相对个人最优的额外行程；拥堵排队或未服务的等待不受此上限保证。轮椅可达性不等于已核实轮椅泊位吞吐量。",
        "", "重新运行：`python scripts/precompute_sim_p3.py`；完整资源输入、前后结果、公平性及容量诊断见 `p3-shared-capacity-evidence.json`。", "",
    ])
    (out / "p3-shared-capacity-report.md").write_text(report, encoding="utf-8")
    print(json.dumps({"resources": len(resources), "repeat_equal": True,
                      "normal_delta": result["delta"], "stress_delta": stressed["delta"],
                      "normal_fairness": result["fairness"], "stress_fairness": stressed["fairness"]}))


if __name__ == "__main__":
    main()
