"""Validated, narrowly scoped runtime settings. Secrets never appear in responses."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from .store import PROVIDERS
from ..services.structure.llm_api_client import OpenAiCompatJsonClient

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
class ProviderEdit(Strict):
    model: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9._:/-]+$")
    api_key: SecretStr | None = None
    clear_key: bool = False
class AIEdit(Strict):
    enabled: bool
    provider: Literal["deepseek", "qwen", "glm"]
    timeout_s: int = Field(ge=2, le=30)
    providers: dict[Literal["deepseek", "qwen", "glm"], ProviderEdit]
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

def merge_settings(old, edit: SettingsEdit):
    if set(edit.ai.providers) != set(PROVIDERS):
        raise ValueError("All three providers must be supplied.")
    value = {"revision": edit.revision+1, "ai": {"enabled": edit.ai.enabled, "provider": edit.ai.provider,
        "timeout_s": edit.ai.timeout_s, "providers": {}}, "sources": edit.sources.model_dump()}
    for name, p in edit.ai.providers.items():
        if p.clear_key and p.api_key and p.api_key.get_secret_value():
            raise ValueError("Replace and clear key cannot be requested together.")
        key = "" if p.clear_key else old["ai"]["providers"][name]["api_key"]
        if p.api_key and p.api_key.get_secret_value().strip():
            key = p.api_key.get_secret_value().strip()
            if len(key) > 2048 or any(ord(c)<32 for c in key):
                raise ValueError("Invalid API key.")
        value["ai"]["providers"][name] = {"model": p.model, "api_key": key}
    if value["ai"]["enabled"] and not value["ai"]["providers"][value["ai"]["provider"]]["api_key"]:
        raise ValueError("Set a key for the selected provider before enabling AI.")
    return value

def llm_client(settings):
    ai = settings["ai"]
    p = ai["providers"][ai["provider"]]
    if not ai["enabled"] or not p["api_key"]:
        return None
    from .collect import official_open
    return OpenAiCompatJsonClient(opener=official_open, request_timeout_s=ai["timeout_s"], base_url=PROVIDERS[ai["provider"]][0], api_key=p["api_key"], model=p["model"], connect_timeout_s=ai["timeout_s"])
