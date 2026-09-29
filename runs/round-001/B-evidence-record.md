# B evidence collection run

Status: completed evidence collection; milestone acceptance remains partial.
Observed local date: 2026-09-27. Baseline: fe6cb4f85112cb37b77ee24a8c01aa0933ed878a.
Repository/remote: Thirteen-Points/resilient-public-travel / https://github.com/Thirteen-Points/resilient-public-travel.git.
Branch: Mingquan-Xia. Initial status: clean; successful escalated fetch confirmed matching HEAD and origin/Mingquan-Xia. Normal-network fetch first failed to connect; escalated fetch succeeded.

## Commands and actual results

Commands ran in the repository root unless specified otherwise.

1. `git status --short --branch`, `git remote -v`, `git branch -avv`, `git log`, recursive AGENTS.md inspection and relevant code/document reads: verified repository, branch, role/task/milestone requirements and historical handoffs. Parent AGENTS.md applies; no nested one found.
2. `python -m unittest discover -s backend/tests -v`: did not run; python was not on PATH.
3. Bundled Python with the same unittest arguments: failed (101 discovered entries, 3 import errors: missing jsonschema/fastapi). This is an environment failure, not a passing suite.
4. Created isolated `.venv-b-evidence` with bundled Python; installed `backend/requirements.txt` successfully. Moved only this task's environment into the existing ignored `.venv/b-evidence` after checking both absolute paths were inside the repository and the destination did not exist. Existing `.venv` contents preserved.
5. `.venv/b-evidence/Scripts/python.exe -m unittest discover -s backend/tests -v`: 127 tests passed in the shared working tree; full output [B-unittest.txt](B-unittest.txt). Concurrent changes appeared in signals.py and test_event_api_flow.py, including an extra test. This run is NOT attributed to the baseline and is NOT used for the report's committed-code claim.
6. `git archive --format=zip --output=.venv/b-baseline.zip fe6cb4f85112cb37b77ee24a8c01aa0933ed878a`; `Expand-Archive` to `.venv/b-baseline`: created an isolated committed snapshot without reverting any shared work.
7. The first snapshot-run logging attempt had an incorrect relative output path and failed to create its log; no passing result is attributed to that attempt. The corrected command used an absolute log path.
8. From `.venv/b-baseline`, using the absolute path to `.venv/b-evidence/Scripts/python.exe`: `-m unittest discover -s backend/tests -v`: **126 tests passed, exit 0**, [B-committed-unittest.txt](B-committed-unittest.txt). A Starlette/httpx deprecation warning was emitted; it did not fail tests. Covers local modules and backend integration only.
9. From the same snapshot/interpreter: `scripts/validate_contract_seeds.py`: **passed, exit 0**, [B-seeds.txt](B-seeds.txt). All four seeds readable; only B's three Events/five Signals validated against their schemas/models, not full Network/Route/Simulation schema acceptance.
10. `-m pip freeze` and `--version`: [B-environment.txt](B-environment.txt). No dependency edits committed.
11. `Test-Path backend/app/ai/llm_client.py`: false. `[bool]$env:OPENAI_API_KEY`: false; checked presence only. No API key values, raw model responses or real-model calls collected.

## Scope and manual review

Compared historical handoffs with current baseline code and commits; documented superseded T2.5 integration wording and unresolved model/corpus/line/API-contract discrepancies in [B-M2-progress-evidence.md](../../docs/coordination/B-M2-progress-evidence.md). Do not promote historical board or main statements into current remote facts.

During collection, other tasks committed `d7bfa18` (reviewer inbox plus integration report) and `e0b3ce6` (bilingual disclaimer copy). Read their commit stats, integration report and disclaimer status/copy; documented them separately as E12/E13. The 126-test snapshot result remains attributed only to fe6cb4f; the 127-test working-tree log remains explicitly distinguished. No other task's staged files are included in this task's commit. Manual Markdown-link verification passed, and `git diff --check` / scoped staged-diff whitespace checks passed.

Only this report package is to be staged and committed. Shared-working-tree edits and other tasks' environments/documents are preserved. The allowed output is B evidence material, not changes to pipeline code or other members' report sections. Review staged file names and diff before committing; push only to Mingquan-Xia without force.

Files produced: `docs/coordination/B-M2-progress-evidence.md`, `runs/round-001/B-evidence-record.md`, `B-unittest.txt`, `B-baseline-unittest.txt` (failed logging attempt marker only), `B-committed-unittest.txt`, `B-seeds.txt`, `B-environment.txt`. The directory is a new round and should be retained as an immutable collection record.

Recommended next action: A uses the English paragraphs and index, then obtains separate real-model and whole-chain records after the documented dependencies are resolved.
