"""Public build identity, without shell commands or credential exposure."""
from __future__ import annotations

import os
import re


def get_build_info() -> dict[str, str | None]:
    """Return a verified-format full commit SHA when the deploy supplies one.

    Render supplies RENDER_GIT_COMMIT; Docker accepts APP_BUILD_SHA at build/run.
    Missing identity stays unknown: the running source is not inferred from main.
    """
    for variable in ("APP_BUILD_SHA", "RENDER_GIT_COMMIT", "GITHUB_SHA"):
        candidate = os.getenv(variable, "").strip().lower()
        if re.fullmatch(r"[0-9a-f]{40}", candidate):
            return {"commit_sha": candidate, "source": variable}
    return {"commit_sha": None, "source": "unknown"}
