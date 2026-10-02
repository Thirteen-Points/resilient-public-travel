"""PowerShell-friendly CLI: python -m backend.app.services.ingest.online_cli."""
from __future__ import annotations

import argparse
import json
import os
import signal
import threading
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from ..event_store import DEFAULT_DB_PATH
from .mtr_mobile import MtrMobileAdapter
from .online_http import PublicHttp
from .online_runner import BLOCKED, SOURCES, IngestConfig, IngestRunner
from .online_store import IngestStore

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    if value.strip().lower() not in {"1", "true", "yes", "on", "0", "false", "no", "off"}:
        raise ValueError("invalid boolean configuration")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def emit(value):
    print(json.dumps(value, ensure_ascii=True, separators=(",", ":")), flush=True)


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv(BACKEND_ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description="真实来源采集：只进入人工审核收件箱")
    parser.add_argument("command", choices=("once", "poll", "status"))
    parser.add_argument("--sources", help="逗号分隔来源；默认读取 INGEST_SOURCES")
    parser.add_argument("--cycles", type=int, help="poll 的轮数上限；省略则持续运行")
    args = parser.parse_args(argv)
    if args.cycles is not None and (args.command != "poll" or args.cycles < 1):
        parser.error("--cycles 只能用于 poll 且必须为正整数")
    try:
        selected = tuple(x.strip() for x in (args.sources or os.getenv("INGEST_SOURCES", "mtr_mobile")).split(","))
        config = IngestConfig(
            sources=selected, enabled=env_bool("INGEST_ENABLED"),
            offline=env_bool("OFFLINE_MODE", True),
            interval=int(os.getenv("INGEST_INTERVAL_SECONDS", "300")),
            lookback_hours=int(os.getenv("INGEST_LOOKBACK_HOURS", "24")),
            max_items=int(os.getenv("INGEST_MAX_ITEMS", "100")),
            page_size=int(os.getenv("INGEST_PAGE_SIZE", "25")),
            extra_keywords=tuple(x.strip().casefold() for x in os.getenv("INGEST_EXTRA_KEYWORDS", "").split(",") if x.strip()),
        )
        timeout, retries = float(os.getenv("INGEST_TIMEOUT_SECONDS", "10")), int(os.getenv("INGEST_RETRIES", "2"))
        if not 0 < timeout <= 30 or not 0 <= retries <= 2:
            raise ValueError("timeout or retry configuration exceeds bounds")
        lang = os.getenv("INGEST_MTR_LANG", "zh-HK")
        if lang not in {"zh-HK", "en"}:
            raise ValueError("unsupported MTR language")
        path = Path(os.getenv("DB_PATH") or str(DEFAULT_DB_PATH))
        path = (path if path.is_absolute() else BACKEND_ROOT / path).resolve()
        store = IngestStore(path)
        store.initialize()
    except (ValueError, OSError):
        emit({"type": "error", "error": "invalid_configuration_or_database"})
        return 2
    if args.command == "status":
        emit({"type": "status", "database": str(path), "publishes_events": False,
              "enabled": config.enabled, "offline": config.offline,
              "sources": {name: {"selected": name in config.sources,
                  "blocked_reason": BLOCKED.get(name), "state": store.state(name)} for name in SOURCES}})
        return 0
    stop = threading.Event()
    def request_stop(_signum, _frame):
        stop.set()
    previous = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.signal(sig, request_stop)
    http = PublicHttp(timeout=timeout, retries=retries, stop=stop)
    runner = IngestRunner(store, config, {"mtr_mobile": MtrMobileAdapter(http, lang)}, stop=stop)
    emit({"type": "started", "database": str(path), "sources": config.sources,
          "interval_seconds": config.interval, "publishes_events": False})
    exit_code, cycles = 0, 0
    try:
        while not stop.is_set():
            results = runner.cycle()
            cycles += 1
            for result in results:
                emit({"type": "source_result", "cycle": cycles, **result})
            if any(x["status"] in {"error", "blocked", "offline", "disabled"} for x in results):
                exit_code = 1
            if args.command == "once" or (args.cycles and cycles >= args.cycles):
                break
            # All sources run independently in the cycle; sleep to the next due
            # source, including persisted backoff. A waiting/busy round is not
            # counted as a successful collection (see completed_rounds).
            due = [x.get("next_attempt") for x in results if x.get("next_attempt")]
            from .online_models import utcnow
            delay = max(1, min(due) - utcnow().timestamp()) if due else config.interval
            stop.wait(delay)
    finally:
        http.close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        emit({"type": "stopped", "cycles": cycles, "requested": stop.is_set()})
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
