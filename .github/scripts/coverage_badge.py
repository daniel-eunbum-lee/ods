"""Turn a Cobertura/coverage.py XML report into a shields.io "endpoint" badge file.

    python3 coverage_badge.py coverage.xml "coverage (Python)" python-coverage.json

The percentage is (covered lines + covered branches) / (lines + branches) when the report carries
those totals (coverage.py does), which is the number `coverage report` prints and the CI floor uses;
otherwise the report's own line-rate, otherwise a count of the <line> elements. Standard library only.
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def percent(root: ET.Element) -> float:
    a = root.attrib
    try:
        valid = float(a["lines-valid"]) + float(a.get("branches-valid", 0))
        covered = float(a["lines-covered"]) + float(a.get("branches-covered", 0))
        if valid > 0:
            return 100.0 * covered / valid
    except (KeyError, ValueError):
        pass
    try:
        return 100.0 * float(a["line-rate"])
    except (KeyError, ValueError):
        pass
    lines = root.findall(".//line")
    if not lines:
        raise ValueError("no coverage data in the report")
    return 100.0 * sum(int(line.get("hits", 0)) > 0 for line in lines) / len(lines)


def colour(pct: float) -> str:
    for floor, name in ((90, "brightgreen"), (80, "green"), (70, "yellowgreen"), (60, "yellow"), (50, "orange")):
        if pct >= floor:
            return name
    return "red"


def main(xml_path: str, label: str, out_path: str) -> None:
    pct = percent(ET.parse(xml_path).getroot())
    if not 0.0 <= pct <= 100.0:  # also rejects NaN
        raise ValueError(f"coverage {pct} is not a percentage")
    pct = round(pct)  # the colour must match the number shown (89.6 shows 90%)
    badge = {"schemaVersion": 1, "label": label, "message": f"{pct:.0f}%", "color": colour(pct)}
    Path(out_path).write_text(json.dumps(badge) + "\n", encoding="utf-8")
    print(f"{label}: {badge['message']} ({badge['color']})")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
