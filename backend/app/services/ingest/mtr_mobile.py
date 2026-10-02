"""MTR's public Traffic News website JSON, NOT a documented MTR Mobile API."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.robotparser import RobotFileParser

from .online_http import PublicHttp, SourceFailure
from .online_models import SourcePage, SourcePost, TRANSPORT

BASE = "https://www.mtr.com.hk"
ANNOUNCEMENTS = BASE + "/alert/alert.json"
LINE_STATUS = BASE + "/alert/ryg_line_status.json"
PUBLIC_PAGE = BASE + "/alert/alert_simpletxt_title_tc.html"
HK = timezone(timedelta(hours=8))


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.suppressed += 1
        if tag in {"p", "br", "li", "tr", "td", "div"} and not self.suppressed:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.suppressed = max(0, self.suppressed - 1)
        if tag in {"p", "div", "li", "tr"} and not self.suppressed:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(data)


def plain_text(value: str) -> str:
    parser = PlainText()
    parser.feed(value)
    return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())


def publication_time(value) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise SourceFailure("source_format_changed", permanent=True)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=HK)).astimezone(timezone.utc)
    except ValueError as exc:
        raise SourceFailure("source_format_changed", permanent=True) from exc


class MtrMobileAdapter:
    name = "mtr_mobile"
    min_interval_seconds = 300

    def __init__(self, http: PublicHttp, lang: str = "zh-HK"):
        self.http, self.lang = http, lang
        self.min_interval_seconds = 300
        self._snapshot = None
        self._snapshot_rows = ()
        self._diagnostics = {}

    def _json(self, url):
        try:
            return json.loads(self.http.get(url).decode("utf-8-sig"))
        except (ValueError, UnicodeError) as exc:
            raise SourceFailure("source_format_changed", permanent=True) from exc

    def fetch_page(self, cursor, limit):
        # Fetch a fresh snapshot on every new round; cached body is only used
        # while draining local pages in this round. Restart safely re-fetches.
        if not cursor or cursor.get("snapshot") != self._snapshot:
            robots = RobotFileParser()
            try:
                robots.parse(self.http.get(BASE + "/robots.txt").decode("utf-8-sig").splitlines())
            except UnicodeError as exc:
                raise SourceFailure("robots_unreadable", permanent=True) from exc
            if not all(robots.can_fetch("ResilientRoute-Collector", url)
                       for url in (ANNOUNCEMENTS, LINE_STATUS)):
                raise SourceFailure("robots_disallowed", permanent=True)
            document, status = self._json(ANNOUNCEMENTS), self._json(LINE_STATUS)
            try:
                rows = document["data"]
                state = status["ryg_status"]
                lines = state["line"]
                if not isinstance(rows, list) or not isinstance(lines, list):
                    raise ValueError()
                refresh = float(state["refreshInterval"]) / 1000
                if refresh <= 0:
                    raise ValueError()
                self.min_interval_seconds = max(300, int(refresh + .999))
                self._diagnostics = {
                    "feed_url": ANNOUNCEMENTS,
                    "snapshot_sha256": hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest(),
                    "feed_built_at": state.get("lastBuildDate"),
                    "line_status": {str(x["line_code"]): str(x["status"]) for x in lines},
                    "upstream_refresh_seconds": refresh,
                    "min_interval_seconds": self.min_interval_seconds,
                    "publication_time_policy": "skip_missing",
                }
                def priority(row):
                    if not isinstance(row, dict):
                        raise ValueError()
                    text = str(row.get("alertTitleTc", "") or row.get("alertTitle", "")).casefold()
                    east_rail = any(x in text for x in ("東鐵", "东铁", "east rail"))
                    corridor = any(x in text for x in TRANSPORT[8:])
                    return (not east_rail, not corridor, str(row.get("id", "")))
                self._snapshot_rows = tuple(sorted(rows, key=priority))
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise SourceFailure("source_format_changed", permanent=True) from exc
            self._snapshot = self._diagnostics["snapshot_sha256"]
        offset = int(cursor.get("offset", 0)) if cursor and cursor.get("snapshot") == self._snapshot else 0
        posts = tuple(self.parse(row) for row in self._snapshot_rows[offset:offset + limit])
        next_offset = offset + len(posts)
        next_cursor = {"snapshot": self._snapshot, "offset": next_offset} if next_offset < len(self._snapshot_rows) else None
        return SourcePage(posts, next_cursor, self._diagnostics)

    def parse(self, row) -> SourcePost:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise SourceFailure("source_format_changed", permanent=True)
        suffix = "Tc" if self.lang == "zh-HK" else ""
        title, content = row.get("alertTitle" + suffix), row.get("alertContent" + suffix)
        if not isinstance(title, str) or not isinstance(content, str):
            raise SourceFailure("source_format_changed", permanent=True)
        refs = row.get("resumptionReferIds") or []
        if not isinstance(refs, list) or any(not isinstance(x, str) for x in refs):
            raise SourceFailure("source_format_changed", permanent=True)
        page = PUBLIC_PAGE if suffix else PUBLIC_PAGE.replace("_tc.html", ".html")
        from urllib.parse import quote
        return SourcePost(
            platform=self.name, post_id=row["id"],
            text=plain_text(title + "\n" + content),
            url=page + "#" + quote(row["id"], safe=""), lang=self.lang,
            published_at=publication_time(row.get("issuedTime")),
            author_hint="official-mtr-corporation", source_name="港鐵官方交通消息（待人工审核）",
            official=True, repost_of=tuple(refs), original=row,
        )
