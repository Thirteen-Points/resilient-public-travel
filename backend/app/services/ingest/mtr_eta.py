"""MTR East Rail arrival observations and heuristic anomaly detection.

The detector in this module is deliberately conservative.  Its thresholds are
project heuristics, not MTR's official definition of a service delay.
"""

from __future__ import annotations

import json
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..signal_models import Signal


MTR_API_URL = "https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php"
MTR_LINE = "EAL"
MTR_LANGUAGE = "TC"
CORRIDOR_STATIONS: tuple[tuple[str, str], ...] = (
    ("TAW", "大围"),
    ("KOT", "九龙塘"),
    ("MKK", "旺角东"),
    ("HUH", "红磡"),
    ("EXC", "会展"),
    ("ADM", "金钟"),
)


class MtrEtaFetchError(RuntimeError):
    """A recoverable MTR request or payload error."""


@dataclass(frozen=True)
class MtrDetectionConfig:
    """Named project heuristics; these are not official MTR delay standards."""

    ttnt_threshold_minutes: int = 10
    min_adjacent_stations: int = 2
    min_consecutive_polls: int = 2
    min_usable_stations: int = 4
    poll_interval_seconds: int = 60

    def __post_init__(self) -> None:
        if self.ttnt_threshold_minutes < 1:
            raise ValueError("ttnt_threshold_minutes must be positive")
        if self.min_adjacent_stations < 2:
            raise ValueError("min_adjacent_stations must be at least 2")
        if self.min_consecutive_polls < 1:
            raise ValueError("min_consecutive_polls must be positive")
        if not 2 <= self.min_usable_stations <= len(CORRIDOR_STATIONS):
            raise ValueError("min_usable_stations is outside the corridor size")
        if self.poll_interval_seconds < 1:
            raise ValueError("poll_interval_seconds must be positive")


@dataclass(frozen=True)
class StationObservation:
    station_code: str
    station_name: str
    official_delay: bool
    nearest_ttnt_minutes: int
    anomaly_reasons: tuple[str, ...]

    @property
    def anomalous(self) -> bool:
        return bool(self.anomaly_reasons)


@dataclass(frozen=True)
class StationFailure:
    station_code: str
    station_name: str
    reason: str


@dataclass(frozen=True)
class MtrEtaPollResult:
    signals: tuple[Signal, ...]
    observations: tuple[StationObservation, ...]
    failures: tuple[StationFailure, ...]
    anomalous_stations: tuple[str, ...]
    qualifying_stations: tuple[str, ...]
    consecutive_polls: int
    degraded: bool
    insufficient_data: bool
    used_cached_snapshot: bool


class MtrEtaClient:
    """Small standard-library client for the official MTR next-train API."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        opener: Callable[..., object] = urlopen,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds
        self._opener = opener

    @staticmethod
    def endpoint_url(station_code: str) -> str:
        query = urlencode(
            {"line": MTR_LINE, "sta": station_code, "lang": MTR_LANGUAGE}
        )
        return f"{MTR_API_URL}?{query}"

    def fetch_station(self, station_code: str) -> Mapping[str, object]:
        request = Request(
            self.endpoint_url(station_code),
            headers={"Accept": "application/json", "User-Agent": "ResilientRoute/1.0"},
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if not 200 <= status < 300:
                    raise MtrEtaFetchError(f"HTTP {status}")
                raw = response.read()
            payload = json.loads(raw.decode("utf-8"))
        except MtrEtaFetchError:
            raise
        except HTTPError as exc:
            raise MtrEtaFetchError(f"HTTP {exc.code}") from exc
        except (URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise MtrEtaFetchError(f"request failed: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MtrEtaFetchError("response is not valid JSON") from exc

        if not isinstance(payload, Mapping):
            raise MtrEtaFetchError("response JSON must be an object")
        return payload


def parse_station_observation(
    payload: Mapping[str, object],
    station_code: str,
    station_name: str,
    config: MtrDetectionConfig,
) -> StationObservation:
    """Parse one station response and apply only station-level rules."""

    if payload.get("status") not in (1, "1"):
        message = payload.get("message", "unknown API status")
        raise MtrEtaFetchError(f"MTR API rejected response: {message}")

    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise MtrEtaFetchError("response has no data object")
    station_data = data.get(f"{MTR_LINE}-{station_code}")
    if not isinstance(station_data, Mapping):
        raise MtrEtaFetchError(f"response has no {MTR_LINE}-{station_code} data")

    ttnt_values: list[int] = []
    for direction in ("UP", "DOWN"):
        trains = station_data.get(direction, [])
        if not isinstance(trains, list):
            raise MtrEtaFetchError(f"{direction} train data must be a list")
        for train in trains:
            if not isinstance(train, Mapping):
                continue
            if str(train.get("valid", "")).upper() != "Y":
                continue
            try:
                ttnt = int(str(train.get("ttnt", "")))
            except (TypeError, ValueError):
                continue
            if ttnt >= 0:
                ttnt_values.append(ttnt)

    if not ttnt_values:
        raise MtrEtaFetchError("no valid future train ttnt value")

    nearest_ttnt = min(ttnt_values)
    official_delay = str(payload.get("isdelay", "N")).upper() == "Y"
    reasons: list[str] = []
    if official_delay:
        reasons.append("官方响应 isdelay=Y")
    if nearest_ttnt > config.ttnt_threshold_minutes:
        reasons.append(
            f"最近有效列车 ttnt={nearest_ttnt} 分钟，超过项目启发式阈值 "
            f"{config.ttnt_threshold_minutes} 分钟"
        )

    return StationObservation(
        station_code=station_code,
        station_name=station_name,
        official_delay=official_delay,
        nearest_ttnt_minutes=nearest_ttnt,
        anomaly_reasons=tuple(reasons),
    )


def find_qualifying_adjacent_stations(
    observations: Mapping[str, StationObservation],
    config: MtrDetectionConfig,
) -> tuple[str, ...]:
    """Return the longest adjacent anomalous run in corridor order."""

    best: tuple[str, ...] = ()
    current: list[str] = []
    for station_code, _ in CORRIDOR_STATIONS:
        observation = observations.get(station_code)
        if observation is not None and observation.anomalous:
            current.append(station_code)
            if len(current) > len(best):
                best = tuple(current)
        else:
            current = []
    if len(best) < config.min_adjacent_stations:
        return ()
    return best


class MtrEtaAnomalyPoller:
    """Stateful one-shot poller; callers decide how and when it is scheduled."""

    def __init__(
        self,
        client: MtrEtaClient,
        config: MtrDetectionConfig | None = None,
    ) -> None:
        self.client = client
        self.config = config or MtrDetectionConfig()
        self.last_successful_observations: dict[str, StationObservation] = {}
        self._candidate: tuple[str, ...] = ()
        self._consecutive_polls = 0
        self._incident_signaled = False

    def export_state(self) -> dict:
        return {"candidate": list(self._candidate), "consecutive_polls": self._consecutive_polls,
                "incident_signaled": self._incident_signaled,
                "observations": {key: asdict(value) for key, value in self.last_successful_observations.items()}}

    def restore_state(self, state: Mapping) -> None:
        self._candidate = tuple(state.get("candidate", ()))
        self._consecutive_polls = int(state.get("consecutive_polls", 0))
        self._incident_signaled = bool(state.get("incident_signaled", False))
        self.last_successful_observations = {
            key: StationObservation(**{**value, "anomaly_reasons": tuple(value["anomaly_reasons"])})
            for key, value in state.get("observations", {}).items()}

    def poll_once(self, *, received_at: datetime | None = None) -> MtrEtaPollResult:
        observations: dict[str, StationObservation] = {}
        failures: list[StationFailure] = []
        for station_code, station_name in CORRIDOR_STATIONS:
            try:
                payload = self.client.fetch_station(station_code)
                observation = parse_station_observation(
                    payload, station_code, station_name, self.config
                )
            except (MtrEtaFetchError, TypeError, ValueError) as exc:
                failures.append(
                    StationFailure(station_code, station_name, str(exc) or type(exc).__name__)
                )
                continue
            observations[station_code] = observation
            self.last_successful_observations[station_code] = observation

        insufficient = len(observations) < self.config.min_usable_stations
        qualifying = find_qualifying_adjacent_stations(observations, self.config)
        signals: tuple[Signal, ...] = ()

        # Incomplete data is not evidence of either delay or recovery, so it does
        # not mutate consecutive-incident state.
        if not insufficient:
            if qualifying:
                if qualifying == self._candidate:
                    self._consecutive_polls += 1
                else:
                    self._candidate = qualifying
                    self._consecutive_polls = 1
                    self._incident_signaled = False
                if (
                    self._consecutive_polls >= self.config.min_consecutive_polls
                    and not self._incident_signaled
                ):
                    when = received_at or datetime.now(timezone.utc)
                    signals = (self._build_signal(qualifying, observations, when),)
                    self._incident_signaled = True
            else:
                self._candidate = ()
                self._consecutive_polls = 0
                self._incident_signaled = False

        return MtrEtaPollResult(
            signals=signals,
            observations=tuple(observations.values()),
            failures=tuple(failures),
            anomalous_stations=tuple(
                code for code, observation in observations.items() if observation.anomalous
            ),
            qualifying_stations=qualifying,
            consecutive_polls=self._consecutive_polls,
            degraded=bool(failures),
            insufficient_data=insufficient,
            used_cached_snapshot=not observations and bool(self.last_successful_observations),
        )

    def _build_signal(
        self,
        station_codes: tuple[str, ...],
        observations: Mapping[str, StationObservation],
        received_at: datetime,
    ) -> Signal:
        station_parts: list[str] = []
        for code in station_codes:
            observation = observations[code]
            station_parts.append(
                f"{code}（{observation.station_name}）："
                + "；".join(observation.anomaly_reasons)
            )
        stamp = received_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return Signal(
            signal_id=f"mtr-eal-anomaly-{'-'.join(station_codes)}-{stamp}",
            received_at=received_at,
            source_type="official",
            source_name="港铁实时到站开放数据",
            author_hint=None,
            raw_text=(
                "东铁线实时到站数据出现相邻多站异常："
                + "；".join(station_parts)
                + f"。已连续 {self._consecutive_polls} 次轮询满足项目检测规则。"
                "疑似延误，尚未人工确认；这是基于官方数据的启发式推算，"
                "不是港铁官方延误公告。"
            ),
            raw_url=MTR_API_URL,
            lang="zh-HK",
            provenance="real-derived",
        )


def _result_summary(result: MtrEtaPollResult) -> dict[str, object]:
    return {
        "signals": [signal.model_dump(mode="json") for signal in result.signals],
        "observations": [asdict(item) for item in result.observations],
        "failures": [asdict(item) for item in result.failures],
        "anomalous_stations": result.anomalous_stations,
        "qualifying_stations": result.qualifying_stations,
        "consecutive_polls": result.consecutive_polls,
        "degraded": result.degraded,
        "insufficient_data": result.insufficient_data,
        "used_cached_snapshot": result.used_cached_snapshot,
    }


def main() -> int:
    """Run exactly one real poll and print a safe JSON summary."""

    result = MtrEtaAnomalyPoller(MtrEtaClient()).poll_once()
    print(json.dumps(_result_summary(result), ensure_ascii=False, indent=2))
    return 0 if result.observations else 1


if __name__ == "__main__":
    raise SystemExit(main())
