"""Write the MATLAB/Python parity fixture: a short synthetic run + Python's results.

    cd python && uv run python ../testdata/generate/make_parity_fixture.py

Creates testdata/data/parity/ with the test folder (time.mat etc.) and
expected.mat holding the Python pipeline's spectra, views and peaks. Both the
Python and the MATLAB suites process the same folder and assert the results agree.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import scipy.io

from ods.io import load_test
from ods.pipeline import run
from ods.synth import build_box_model, simulate, write_test

OUT = Path(__file__).resolve().parents[1] / "data" / "parity"
# Options come from the case spec, the single source of truth shared with both test runners
# (fs 1024 -> Nyquist 512 Hz; nfft 256).
SPEC = json.loads((OUT.parents[1] / "cases" / "parity-box-z.json").read_text())
OPTS = dict(df=SPEC["options"]["df"], band=tuple(SPEC["options"]["band"]))


def main() -> None:
    model = build_box_model()
    sim = simulate(model, "Z", fs=1024.0, duration=4.0, seed=11)
    write_test(OUT, model, sim, fmt="mat")
    (OUT / "truth.npz").unlink()  # parity only needs the data; keep the fixture small

    res = run(load_test(OUT), **OPTS)
    sp = res.spectra
    expected = {
        "df": OPTS["df"],
        "band": np.array(OPTS["band"]),
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
        "peak_index": np.array([p.index + 1 for p in res.peaks], dtype=float),  # 1-based
        "peak_f": np.array([p.f for p in res.peaks]),
        "peak_mpc": np.array([p.mpc for p in res.peaks]),
        "peak_coh": np.array([p.coh for p in res.peaks]),
    }
    scipy.io.savemat(OUT / "expected.mat", expected, do_compression=True)
    print(f"wrote {OUT} ({len(res.peaks)} peaks: {', '.join(f'{p.f:.1f}' for p in res.peaks)} Hz)")


if __name__ == "__main__":
    main()
