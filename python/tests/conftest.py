"""Shared test fixtures.

`record_metric` lets a verification test log a measured quantity next to the limit it is held to.
CI sets ODS_EVIDENCE_DIR and keeps the resulting JSON as evidence, so numerical accuracy can be
compared between runs and versions and not only seen as pass/fail. Without the variable nothing
is written, so local runs are unchanged.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

_METRICS: list[dict] = []


@pytest.fixture
def record_metric(request: pytest.FixtureRequest):
    """Return `record(name, value, limit=None, op="<", units="", note="")` bound to the current test.

    `op` states how the value is compared with `limit` ("<" means the value must stay below it).
    Keep `name` stable between runs (it is the key for comparing them); put run-dependent detail in `note`.
    """

    def record(name: str, value: float, limit: float | None = None, op: str = "<", units: str = "", note: str = "") -> None:
        _METRICS.append(
            {
                "test": request.node.nodeid,
                "metric": name,
                "value": float(value),
                "limit": None if limit is None else float(limit),
                "op": op if limit is not None else None,
                "units": units,
                "note": note,
            }
        )

    return record


# Single-process only: under pytest-xdist each worker has its own _METRICS and the last writer would win,
# and a rerun plugin would append duplicates. Neither is used here; revisit if either is adopted.
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    out_dir = os.environ.get("ODS_EVIDENCE_DIR")
    if not out_dir or not _METRICS:
        return
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "verification_metrics.json").write_text(json.dumps(_METRICS, indent=2) + "\n", encoding="utf-8")
