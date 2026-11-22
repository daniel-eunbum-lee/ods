"""Write the MATLAB/Python parity fixture: a short synthetic run + Python's results.

    uv run python matlab/tests/make_parity_fixture.py

Creates matlab/tests/fixtures/parity/ with the test folder (time.mat etc.) and
expected.mat holding the Python pipeline's spectra, views and peaks. run_tests.m
processes the same folder in MATLAB and asserts the results agree to round-off.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import scipy.io

from ods.io import load_test
from ods.pipeline import run
from ods.synth import build_box_model, simulate, write_test

OUT = Path(__file__).parent / "fixtures" / "parity"
OPTS = dict(df=4.0, band=(20.0, 450.0))  # fs 1024 -> Nyquist 512 Hz; nfft 256


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
