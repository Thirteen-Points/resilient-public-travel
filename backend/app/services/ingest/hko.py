"""Hong Kong Observatory weather-warning signal source (T2.2).

``warnsum`` determines whether the active warning-code set changed.
``warningInfo`` enriches emitted signals but is not required for them.  The
poller deliberately does not create Events or persist data; later pipeline
tasks consume the returned contract ``Signal`` objects.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..signal_models import Signal


HKO_API_URL = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"
HKO_SOURCE_NAME = "Hong Kong Observatory"
DEFAULT_LANGUAGE = "tc"
DEFAULT_TIMEOUT_S = 10.0
DEFAULT_POLL_INTERVAL_S = 90

JsonObject = dict[str, Any]
UrlOpener = Callable[..., Any]


class HkoFetchError(RuntimeError):
    """A recoverable HKO HTTP, decoding, or payload error."""


@dataclass(frozen=True)
class HkoPollResult:
    """One non-throwing polling outcome for schedulers and diagnostics."""

    signals: tuple[Signal, ...]
    active_codes: frozenset[str]
    changed: bool
    stale: bool
    degraded: bool
    error: str | None = None


class HkoClient:
    """Small standard-library HTTP client for the two official HKO endpoints."""

    def __init__(
        self,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        lang: str = DEFAULT_LANGUAGE,
        opener: UrlOpener = urlopen,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be greater than zero")
        if lang not in {"en", "tc", "sc"}:
            raise ValueError("lang must be one of: en, tc, sc")
        self.timeout_s = timeout_s
        self.lang = lang
        self._opener = opener

    def fetch_warnsum(self) -> JsonObject:
        payload = self._fetch_json("warnsum")
        if not isinstance(payload, dict):
            raise HkoFetchError("warnsum returned a non-object JSON payload")
        return payload

    def fetch_warning_info(self) -> JsonObject:
        payload = self._fetch_json("warningInfo")
        if not isinstance(payload, dict):
            raise HkoFetchError("warningInfo returned a non-object JSON payload")
        return payload

    def endpoint_url(self, data_type: str) -> str:
        return f"{HKO_API_URL}?{urlencode({'dataType': data_type, 'lang': self.lang})}"

    def _fetch_json(self, data_type: str) -> Any:
        url = self.endpoint_url(data_type)
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "ResilientRoute/0.1 (academic demonstration)",
            },
        )
        try:
            with self._opener(request, timeout=self.timeout_s) as response:
                body = response.read()
            return json.loads(body.decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise HkoFetchError(f"{data_type} request failed: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HkoFetchError(f"{data_type} returned invalid JSON: {exc}") from exc


class HkoWarningPoller:
    """Emit Signals only when the active HKO warning-code set changes."""

    def __init__(
        self,
        client: HkoClient | None = None,
        *,
        poll_interval_s: int = DEFAULT_POLL_INTERVAL_S,
    ) -> None:
        if not 60 <= poll_interval_s <= 120:
            raise ValueError("poll_interval_s must be between 60 and 120 seconds")
        self.client = client or HkoClient()
        self.poll_interval_s = poll_interval_s
        self._last_active_codes: frozenset[str] | None = None
        self._last_successful_warnsum: JsonObject | None = None

    @property
    def last_successful_warnsum(self) -> Mapping[str, Any] | None:
        """Return the cached last-good summary for diagnostics/fallback display."""

        return self._last_successful_warnsum

    def poll_once(self, *, received_at: datetime | None = None) -> HkoPollResult:
        """Poll once without raising for recoverable external-service failures."""

        timestamp = received_at or datetime.now(timezone.utc)
        try:
            summary = self.client.fetch_warnsum()
            records = _normalise_summary(summary)
        except HkoFetchError as exc:
            cached_codes = self._last_active_codes or frozenset()
            return HkoPollResult(
                signals=(),
                active_codes=cached_codes,
                changed=False,
                stale=self._last_successful_warnsum is not None,
                degraded=True,
                error=str(exc),
            )

        active_codes = frozenset(records)
        previous_codes = self._last_active_codes
        previous_summary = self._last_successful_warnsum
        changed = previous_codes is None or active_codes != previous_codes

        # A successful warnsum response always replaces the cached snapshot,
        # even when no Signal is emitted.
        self._last_active_codes = active_codes
        self._last_successful_warnsum = summary

        if not changed:
            return HkoPollResult(
                signals=(),
                active_codes=active_codes,
                changed=False,
                stale=False,
                degraded=False,
            )

        prior_codes = previous_codes or frozenset()
        added_codes = active_codes if previous_codes is None else active_codes - prior_codes
        removed_codes = frozenset() if previous_codes is None else prior_codes - active_codes

        detail_by_code: dict[str, JsonObject] = {}
        detail_error: str | None = None
        try:
            details = self.client.fetch_warning_info()
            detail_by_code = _normalise_details(details)
        except HkoFetchError as exc:
            detail_error = str(exc)

        previous_records = (
            _normalise_summary(previous_summary) if previous_summary is not None else {}
        )
        signals = [
            _build_signal(
                code=code,
                record=records[code],
                detail=detail_by_code.get(code),
                change="activated",
                received_at=timestamp,
                raw_url=self.client.endpoint_url("warnsum"),
                detail_unavailable=detail_error is not None,
            )
            for code in sorted(added_codes)
        ]
        signals.extend(
            _build_signal(
                code=code,
                record=previous_records.get(code, {"code": code, "name": code}),
                detail=None,
                change="cleared",
                received_at=timestamp,
                raw_url=self.client.endpoint_url("warnsum"),
                detail_unavailable=detail_error is not None,
            )
            for code in sorted(removed_codes)
        )

        return HkoPollResult(
            signals=tuple(signals),
            active_codes=active_codes,
            changed=True,
            stale=False,
            degraded=detail_error is not None,
            error=detail_error,
        )


def _normalise_summary(payload: Mapping[str, Any]) -> dict[str, JsonObject]:
    records: dict[str, JsonObject] = {}
    for key, value in payload.items():
        if not isinstance(value, Mapping):
            raise HkoFetchError(f"warnsum entry {key!r} is not an object")
        code = str(value.get("code") or key).strip()
        if not code:
            raise HkoFetchError("warnsum contains an empty warning code")
        records[code] = dict(value)
    return records


def _normalise_details(payload: Mapping[str, Any]) -> dict[str, JsonObject]:
    raw_details = payload.get("details", [])
    if raw_details is None:
        return {}
    if not isinstance(raw_details, list):
        raise HkoFetchError("warningInfo details is not a list")

    details: dict[str, JsonObject] = {}
    for item in raw_details:
        if not isinstance(item, Mapping):
            continue
        code = str(item.get("warningStatementCode") or "").strip()
        if code:
            details[code] = dict(item)
    return details


def _build_signal(
    *,
    code: str,
    record: Mapping[str, Any],
    detail: Mapping[str, Any] | None,
    change: str,
    received_at: datetime,
    raw_url: str,
    detail_unavailable: bool,
) -> Signal:
    safe_code = re.sub(r"[^A-Za-z0-9_-]+", "_", code).strip("_") or "warning"
    timestamp_id = received_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    name = str(record.get("name") or code)
    action_code = str(record.get("actionCode") or "unknown")

    if change == "cleared":
        text = f"香港天文台天气警告取消或不再生效：{name} ({code})。"
    else:
        text = f"香港天文台天气警告生效：{name} ({code})；行动代号：{action_code}。"
        contents = detail.get("contents") if detail is not None else None
        if isinstance(contents, list):
            detail_text = " ".join(str(part).strip() for part in contents if str(part).strip())
            if detail_text:
                text = f"{text} {detail_text}"
    if detail_unavailable:
        text = f"{text} warningInfo 暂时无法取得；本 Signal 仅根据 warnsum 生成。"

    return Signal(
        signal_id=f"sig_hko_{safe_code.lower()}_{change}_{timestamp_id}",
        received_at=received_at,
        source_type="official",
        source_name=HKO_SOURCE_NAME,
        author_hint=None,
        raw_text=text,
        raw_url=raw_url,
        lang="zh-HK",
        provenance="real",
    )


def main() -> int:
    """Run one live poll for manual verification; never start a background loop."""

    result = HkoWarningPoller().poll_once()
    output = {
        "active_codes": sorted(result.active_codes),
        "changed": result.changed,
        "stale": result.stale,
        "degraded": result.degraded,
        "error": result.error,
        "signals": [signal.model_dump(mode="json") for signal in result.signals],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if not result.error or result.signals else 1


if __name__ == "__main__":
    raise SystemExit(main())
