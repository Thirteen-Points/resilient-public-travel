"""Run T2.6 against a team-approved real-text file without logging its text.

Example (from repository root, in a trusted environment):
    python scripts/run_t2_6_acceptance.py --provider deepseek --samples C:\\private\\real_samples.json

The input has ``meta.provenance=real`` and exactly ten ``samples`` with
sample_id, text, lang and source_note. Keep that input outside Git.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from backend.app.ai.llm_client import LLMConfig
from backend.app.services.structure.acceptance import AcceptanceSample, run_acceptance
from backend.app.services.structure.provider_client import StructureJsonClient


def load_real_samples(path: Path) -> list[AcceptanceSample]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("meta", {}).get("provenance") != "real":
        raise ValueError("T2.6 requires a team-approved real-text corpus; simulated fixtures are refused")
    samples = [AcceptanceSample(**{**item, "provenance": "real"}) for item in payload["samples"]]
    if len(samples) != 10 or len({sample.sample_id for sample in samples}) != 10:
        raise ValueError("T2.6 requires exactly ten unique real-text samples")
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=("deepseek", "qwen", "glm"))
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="Safe result JSON path; raw sample texts are omitted")
    args = parser.parse_args()

    # Reject the bundled simulated fixture before selecting a provider or calling it.
    try:
        samples = load_real_samples(args.samples)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"T2.6 sample input rejected: {exc}") from None
    provider = next((item for item in LLMConfig.from_env().providers if item.name == args.provider), None)
    if provider is None:
        raise SystemExit(f"{args.provider.upper()}_API_KEY is not configured")
    summary = run_acceptance(StructureJsonClient(provider), samples)
    record = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider.name,
        "model": provider.model,
        "corpus_provenance": "real; team approval must be verified separately",
        "total": summary.total,
        "first_passes": summary.first_passes,
        "retries": summary.retries,
        "fallbacks": summary.fallbacks,
        "passes_schema_threshold": summary.passes_t2_6,
        "semantic_accuracy_reviewed": False,
        "cases": [asdict(case) for case in summary.cases],
    }
    safe_json = json.dumps(record, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(safe_json + "\n", encoding="utf-8")
    print(safe_json)
    return 0 if summary.passes_t2_6 else 1


if __name__ == "__main__":
    raise SystemExit(main())
