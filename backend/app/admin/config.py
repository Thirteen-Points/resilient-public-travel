"""Validated, narrowly scoped runtime settings. Secrets never appear in responses."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from .store import PROVIDERS

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
class KeyEdit(Strict):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    label: str = Field(default="API key", max_length=80)
    value: SecretStr | None = None
class ProviderEdit(Strict):
    model: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9._:/-]+$")
    name: str = Field(default="", max_length=80)
    base_url: str | None = Field(default=None, max_length=500)
    enabled: bool = True
    keys: list[KeyEdit] | None = Field(default=None, max_length=8)
    api_key: SecretStr | None = None  # Legacy clients
    clear_key: bool = False
class AIEdit(Strict):
    enabled: bool
    provider: str = Field(min_length=1, max_length=64)
    order: list[str] | None = Field(default=None, max_length=12)
    timeout_s: int = Field(ge=2, le=30)
    providers: dict[str, ProviderEdit]
class MtrEdit(Strict):
    enabled: bool
    timeout_s: int = Field(ge=2, le=15)
    ttnt_threshold_minutes: int = Field(ge=1, le=60)
    min_adjacent_stations: int = Field(ge=2, le=6)
    min_consecutive_polls: int = Field(ge=1, le=10)
    min_usable_stations: int = Field(ge=2, le=6)
    poll_interval_seconds: int = Field(ge=60, le=600)
class HkoEdit(Strict):
    enabled: bool
    timeout_s: int = Field(ge=2, le=15)
    lang: Literal["tc", "sc", "en"]
    poll_interval_seconds: int = Field(ge=60, le=120)
class SourcesEdit(Strict):
    mtr: MtrEdit
    hko: HkoEdit
class SettingsEdit(Strict):
    revision: int = Field(ge=0)
    ai: AIEdit
    sources: SourcesEdit

def normalize_ai(ai):
    ai.setdefault("order", [ai["provider"]] + [n for n in ai["providers"] if n != ai["provider"]])
    for name, p in ai["providers"].items():
        p.setdefault("base_url", PROVIDERS.get(name, ("", ""))[0])
        p.setdefault("name", name)
        p.setdefault("enabled", True)
        if "keys" not in p:
            key = p.get("api_key", "")
            p["keys"] = [{"id": "primary", "label": "Primary key", "value": key}] if key else []
    return ai

def merge_settings(old, edit: SettingsEdit):
    from .llm_network import validate_url
    import re
    old_ai = normalize_ai(old["ai"])
    order = edit.ai.order or [edit.ai.provider] + [n for n in edit.ai.providers if n != edit.ai.provider]
    if (not 1 <= len(edit.ai.providers) <= 12 or len(set(order)) != len(order)
        or set(order) != set(edit.ai.providers) or any(not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", n) for n in order)):
        raise ValueError("Supply 1–12 unique providers and an order containing every provider exactly once.")
    value = {"revision": edit.revision+1, "ai": {"enabled": edit.ai.enabled, "provider": order[0],
        "order": order, "timeout_s": edit.ai.timeout_s, "providers": {}}, "sources": edit.sources.model_dump()}
    for name, p in edit.ai.providers.items():
        previous = old_ai["providers"].get(name, {})
        if p.clear_key and p.api_key and p.api_key.get_secret_value():
            raise ValueError("Replace and clear key cannot be requested together.")
        if p.keys is not None:
            saved = {k["id"]: k for k in previous.get("keys", [])}
            if len({k.id for k in p.keys}) != len(p.keys): raise ValueError("Key identifiers must be unique.")
            keys = [{"id": k.id, "label": k.label, "value": k.value.get_secret_value().strip() if k.value and k.value.get_secret_value().strip() else saved.get(k.id, {}).get("value", "")} for k in p.keys]
        else:
            key = "" if p.clear_key else previous.get("api_key", previous.get("keys", [{}])[0].get("value", "") if previous.get("keys") else "")
            if p.api_key and p.api_key.get_secret_value().strip(): key = p.api_key.get_secret_value().strip()
            keys = [{"id": "primary", "label": "Primary key", "value": key}] if key else []
        if any(len(k["value"]) > 2048 or any(ord(c)<32 for c in k["value"]) for k in keys):
            raise ValueError("Invalid API key.")
        value["ai"]["providers"][name] = {"name": p.name or name, "model": p.model, "enabled": p.enabled,
            "base_url": validate_url(p.base_url or previous.get("base_url") or PROVIDERS.get(name, ("", ""))[0]),
            "keys": keys, "api_key": keys[0]["value"] if keys else ""}
    if value["ai"]["enabled"] and not any(p["enabled"] and any(k["value"] for k in p["keys"]) for p in value["ai"]["providers"].values()):
        raise ValueError("Save at least one enabled provider with an API key before enabling AI.")
    return value

def llm_client(settings, store=None, *, provider=None, key_id=None):
    from .llm_runtime import OrderedClient
    ai = normalize_ai(settings["ai"])
    if not ai["enabled"] and provider is None: return None
    candidates = []
    for name in ([provider] if provider else ai["order"]):
        p = ai["providers"].get(name)
        if not p or (not p["enabled"] and provider is None): continue
        for key in p["keys"]:
            if key["value"] and (key_id is None or key["id"] == key_id):
                candidates.append((name, p, key))
    budget = getattr(store, "llm_budget", None)
    return OrderedClient(candidates, ai["timeout_s"], store, budget=budget) if candidates else None
