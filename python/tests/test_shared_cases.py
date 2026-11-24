"""Runner for the language-neutral cases in testdata/ (the MATLAB runner reads the same files).

Each case names an input folder, pipeline options, a golden output file and a list of checks with
tolerances; see testdata/README.md for the format and the comparison rule.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import scipy.io

from ods.io import load_test
from ods.pipeline import run

TESTDATA = Path(__file__).resolve().parents[2] / "testdata"
if not TESTDATA.is_dir():  # e.g. tests run from an sdist, which does not ship the shared data
    pytest.skip("testdata/ not present", allow_module_level=True)
CASES = sorted((TESTDATA / "cases").glob("*.json"))


def _actuals(res) -> dict[str, np.ndarray]:
    """The quantities a case may check, under the names used in the golden files.

    Peak bins are 1-based in the golden files (MATLAB indexing).
    """
    sp = res.spectra
    return {
        "f": sp.f,
        "T": sp.T,
        "coh": sp.coh,
        "Gbb": sp.Gbb,
        "Gxx": sp.Gxx,
        "T_rel": res.T_rel,
        "T_el": res.T_el,
        "disp_el": res.disp_el,
        "rigid_R": res.rigid_R,
        "nfft": sp.nfft,
        "n_avg": sp.n_avg,
        "peak_index": np.array([p.index + 1 for p in res.peaks], dtype=float),
        "peak_f": np.array([p.f for p in res.peaks]),
        "peak_mpc": np.array([p.mpc for p in res.peaks]),
        "peak_coh": np.array([p.coh for p in res.peaks]),
    }


def assert_close(actual, expected, check: dict) -> None:
    """|actual - expected| <= atol + atol_fullscale * max|expected| + rtol * |expected|, element-wise."""
    a = np.asarray(actual).ravel()
    e = np.asarray(expected).ravel()
    assert a.size == e.size, f"{a.size} elements, expected {e.size}"
    assert np.array_equal(np.isnan(a), np.isnan(e)), "NaN in different places"
    keep = ~np.isnan(e)
    a, e = a[keep], e[keep]
    if e.size == 0:
        return
    tol = check["atol"] + check["atol_fullscale"] * np.abs(e).max() + check["rtol"] * np.abs(e)
    err = np.abs(a - e)
    worst = int(np.argmax(err - tol))
    assert np.all(err <= tol), f"element {worst}: differs by {err[worst]:.3g}, tolerance {tol[worst]:.3g}"


@pytest.fixture(scope="module")
def evaluated():
    """Run each case's pipeline once and share it between that case's checks."""
    cache: dict[str, tuple[dict, dict, dict]] = {}

    def get(path: Path):
        if path.name not in cache:
            spec = json.loads(path.read_text())
            opts = spec["options"]
            res = run(load_test(TESTDATA / spec["input"]), df=float(opts["df"]), band=tuple(opts["band"]))
            golden = scipy.io.loadmat(TESTDATA / spec["expected"])
            cache[path.name] = (spec, _actuals(res), golden)
        return cache[path.name]

    return get


def _params():
    for path in CASES:
        spec = json.loads(path.read_text())
        for check in spec["checks"]:
            yield pytest.param(path, check, id=f"{spec['id']}-{check['quantity']}")


def test_cases_are_present():
    assert CASES, f"no shared cases found in {TESTDATA / 'cases'}"


def test_case_specs_are_well_formed():
    # Same keys in the same order in every check: MATLAB's jsondecode returns a struct array only then.
    required = ["quantity", "rtol", "atol", "atol_fullscale"]
    for path in CASES:
        spec = json.loads(path.read_text())
        assert {"id", "description", "input", "options", "expected", "checks"} <= spec.keys(), path.name
        assert spec["id"] == path.stem, f"{path.name}: id must equal the file name"
        assert (TESTDATA / spec["input"]).is_dir() and (TESTDATA / spec["expected"]).is_file(), path.name
        assert spec["checks"], f"{path.name}: a case with no checks would pass vacuously"
        for check in spec["checks"]:
            assert list(check) == required, f"{path.name}: {check}"


@pytest.mark.parametrize(("path", "check"), list(_params()))
def test_shared_case(evaluated, path, check):
    _, actual, golden = evaluated(path)
    name = check["quantity"]
    assert name in actual, f"runner does not expose quantity {name!r}"
    assert_close(actual[name], golden[name], check)
