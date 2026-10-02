"""Durable shared budget for actual event and language-model requests.

Rates are CNY per million tokens. DeepSeek defaults conservatively use the
2026-10-02 official peak rate; unknown providers retain a configurable estimate.
No prompts, responses or API keys are written to this database.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
import time
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path


def external_ai_allowed() -> bool:
    truth = {"1", "true", "yes", "on"}
    return (os.getenv("OFFLINE_MODE", "true").lower() not in truth
            and os.getenv("AI_DISABLE_EXTERNAL", "false").lower() not in truth)


def number(name, default):
    value = float(os.getenv(name, str(default)))
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"Invalid {name}")
    return value


def rates(name, provider):
    # A custom connection called 'deepseek' must not inherit official pricing.
    official = (provider["base_url"].rstrip("/") in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}
                and provider["model"] in {"deepseek-flash", "deepseek-v4-flash", "deepseek-v4-flash-vision-exp"})
    prefix = name.upper()
    values = [os.getenv(prefix + suffix) for suffix in
              ("_INPUT_COST_PER_MILLION", "_CACHE_HIT_COST_PER_MILLION", "_OUTPUT_COST_PER_MILLION")]
    if official:
        return tuple(number(prefix + suffix, default) for suffix, default in zip(
            ("_INPUT_COST_PER_MILLION", "_CACHE_HIT_COST_PER_MILLION", "_OUTPUT_COST_PER_MILLION"), (2, .04, 8)))
    if values[0] is None or values[2] is None:
        return None
    return (number(prefix + "_INPUT_COST_PER_MILLION", 0),
            number(prefix + "_CACHE_HIT_COST_PER_MILLION", float(values[0])),
            number(prefix + "_OUTPUT_COST_PER_MILLION", 0))


class BudgetExceeded(RuntimeError):
    pass


class ModelBudget:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS model_usage (
                id TEXT PRIMARY KEY, at REAL NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
                status TEXT NOT NULL, cost REAL NOT NULL, estimated INTEGER NOT NULL,
                prompt_tokens INTEGER NOT NULL DEFAULT 0, completion_tokens INTEGER NOT NULL DEFAULT 0,
                cache_hit_tokens INTEGER NOT NULL DEFAULT 0)""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, name, provider, kwargs):
        price = rates(name, provider)
        # UTF-8 bytes are a conservative upper bound for this text-only request.
        input_bytes = len(json.dumps(kwargs, ensure_ascii=False).encode()) + 1024
        if input_bytes > 64000:
            raise BudgetExceeded("Model input exceeds configured bound")
        output_limit = min(8192, max(1, int(number("AI_MAX_OUTPUT_TOKENS", 2048))))
        amount = ((input_bytes * max(price[0], price[1]) + output_limit * price[2]) / 1e6
                  if price else number("AI_UNKNOWN_REQUEST_RESERVE_CNY", 1))
        if amount <= 0:
            raise BudgetExceeded("A positive request reserve is required")
        budget = number("AI_BUDGET_CNY", 50)
        identifier = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            spent = db.execute("SELECT COALESCE(SUM(cost),0) FROM model_usage").fetchone()[0]
            if spent + amount > budget:
                raise BudgetExceeded("Model budget exhausted; deterministic fallback remains available")
            db.execute("INSERT INTO model_usage(id,at,provider,model,status,cost,estimated) VALUES(?,?,?,?,?,?,1)",
                       (identifier, time.time(), name, provider["model"], "reserved", amount))
        return identifier, price

    def finish(self, identifier, price, usage, status):
        # HTTP/schema failures may still be billed. Missing usage retains the
        # reserve, including across a crash; it is never silently charged zero.
        known = isinstance(usage, dict) and all(isinstance(usage.get(k), int) and usage[k] >= 0
                                               for k in ("prompt_tokens", "completion_tokens"))
        prompt, output = (usage["prompt_tokens"], usage["completion_tokens"]) if known else (0, 0)
        hit = max(0, min(prompt, int(usage.get("prompt_cache_hit_tokens", 0)))) if known else 0
        with self.connect() as db:
            if known and price:
                cost = ((prompt - hit) * price[0] + hit * price[1] + output * price[2]) / 1e6
                db.execute("UPDATE model_usage SET cost=?,estimated=0 WHERE id=?", (cost, identifier))
            db.execute("UPDATE model_usage SET status=?,prompt_tokens=?,completion_tokens=?,cache_hit_tokens=? WHERE id=?",
                       (status, prompt, output, hit, identifier))

    def summary(self):
        with self.connect() as db:
            spent, calls, estimated, prompt, output, hits = db.execute("""SELECT COALESCE(SUM(cost),0),COUNT(*),
                COALESCE(SUM(estimated),0),COALESCE(SUM(prompt_tokens),0),COALESCE(SUM(completion_tokens),0),
                COALESCE(SUM(cache_hit_tokens),0) FROM model_usage WHERE status != 'cached'""").fetchone()
            cached = db.execute("SELECT COUNT(*) FROM model_usage WHERE status='cached'").fetchone()[0]
        budget = number("AI_BUDGET_CNY", 50)
        return {"spent_cny": round(spent, 6), "budget_cny": budget, "remaining_cny": round(max(0, budget-spent), 6),
                "calls": calls, "estimated_calls": estimated, "prompt_tokens": prompt, "completion_tokens": output,
                "provider_cache_hit_tokens": hits, "local_cache_hits": cached,
                "accounting": "conservative estimate; reconcile with provider invoice"}

    @staticmethod
    def cache_key(provider, key, kwargs):
        return hashlib.sha256(json.dumps([provider["base_url"], provider["model"], key["value"], kwargs],
                                         sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def cached(self, cache_key, name, model):
        with self.lock:
            entry = self.cache.get(cache_key)
            if not entry or entry[0] <= time.monotonic():
                self.cache.pop(cache_key, None)
                return None
            self.cache.move_to_end(cache_key)
            output = entry[1]
        with self.connect() as db:
            db.execute("INSERT INTO model_usage(id,at,provider,model,status,cost,estimated) VALUES(?,?,?,?,?,0,0)",
                       (uuid.uuid4().hex, time.time(), name, model, "cached"))
        return output

    def remember(self, cache_key, output):
        ttl = number("AI_CACHE_TTL_S", 900)
        with self.lock:
            self.cache[cache_key] = (time.monotonic()+ttl, output)
            self.cache.move_to_end(cache_key)
            while len(self.cache) > 128:
                self.cache.popitem(last=False)
