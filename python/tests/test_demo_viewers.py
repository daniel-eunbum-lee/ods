"""The demo viewers in docs/demo/ must be rebuilt whenever the viewer template changes."""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path

import pytest

import ods.io

TEMPLATE = Path(ods.io.__file__).with_name("viewer_template.html")
DEMOS = sorted((Path(__file__).resolve().parents[2] / "docs" / "demo").glob("*.html"))
SCRIPT = re.compile(r"<script>(.*?)</script>", re.S)


def test_the_demo_viewers_are_present():
    assert {p.name for p in DEMOS} >= {"ods_viewer.html", "ods_viewer_cantilever.html"}


@pytest.mark.parametrize("path", DEMOS, ids=lambda p: p.name)
def test_demo_viewer_carries_the_current_template_script(path):
    """Same script as the template and a Content-Security-Policy that allows exactly that script.

    Fails when the template changed but the demos were not regenerated with
    testdata/generate/make_demo_viewers.py.
    """
    html = path.read_text(encoding="utf-8")
    (script,) = SCRIPT.findall(html)
    (template_script,) = SCRIPT.findall(TEMPLATE.read_text(encoding="utf-8"))
    assert script == template_script, f"{path.name} is out of date: run testdata/generate/make_demo_viewers.py"
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    assert f"script-src 'sha256-{digest}'" in html
