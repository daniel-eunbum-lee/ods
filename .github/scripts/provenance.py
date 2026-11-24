"""Write evidence/provenance.json: what exactly was tested, and where and when.

Run after the tests, inside the project environment (`uv run --locked python .github/scripts/provenance.py`),
so the recorded package versions are the ones the tests actually used. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

PACKAGES = ("ods", "numpy", "scipy", "pytest", "pytest-cov", "ruff")


def package_versions() -> dict[str, str]:
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "not installed"
    return versions


def main(out_dir: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    server, repo, run_id = (os.environ.get(k) for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"))
    record = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": os.environ.get("GITHUB_SHA"),
        "git_ref": os.environ.get("GITHUB_REF"),
        "event": os.environ.get("GITHUB_EVENT_NAME"),
        "run_url": f"{server}/{repo}/actions/runs/{run_id}" if run_id else None,
        "runner_os": os.environ.get("RUNNER_OS"),
        "job": os.environ.get("GITHUB_JOB"),
        "platform": platform.platform(),
        "python": sys.version,
        "lockfile_sha256": hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest(),
        "packages": package_versions(),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "provenance.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(os.environ.get("ODS_EVIDENCE_DIR", "evidence")))
