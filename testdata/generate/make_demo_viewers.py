"""Rebuild the two demo viewers in docs/demo/ (run from python/: ``uv run python ../testdata/generate/make_demo_viewers.py``).

* ods_viewer.html           the box-on-isolators synthetic test (``ods synth`` + ``ods run`` defaults)
* ods_viewer_cantilever.html the base-driven cantilever of the analytical benchmark, same seed, record
                             length and settings as ``python/tests/test_benchmark_cantilever.py``

Regenerate both whenever viewer_template.html or the processing changes, so the demos never lag behind the tool.
"""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

from ods.io import load_test
from ods.pipeline import run
from ods.synth import build_box_model, simulate, write_test
from ods.viewer import build_viewer

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "docs" / "demo"


def _benchmark():
    """The benchmark test module, loaded by path so the demo uses exactly the benchmark's problem."""
    path = ROOT / "python" / "tests" / "test_benchmark_cantilever.py"
    spec = importlib.util.spec_from_file_location("test_benchmark_cantilever", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    DEMO.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        box = Path(tmp) / "box"
        model = build_box_model()
        # defaults of `ods synth`: Z axis, 5120 Hz, 60 s, seed 1
        write_test(box, model, simulate(model, "Z", 5120.0, 60.0, seed=1), fmt="npz")
        build_viewer(run(load_test(box)), DEMO / "ods_viewer.html", title="Box on isolators (synthetic, Z random)")

        bm = _benchmark()
        cant = Path(tmp) / "cantilever"
        bm.write_cantilever_test(cant, seed=7)
        build_viewer(
            run(load_test(cant), df=bm.DF, band=bm.BAND),
            DEMO / "ods_viewer_cantilever.html",
            title="Aluminium cantilever, 200 x 25 x 3 mm (analytical benchmark)",
        )
    for p in sorted(DEMO.glob("*.html")):
        print(f"{p.relative_to(ROOT)}  {p.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
