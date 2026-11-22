"""Analytical benchmark: a uniform Euler-Bernoulli cantilever driven at its base.

The whole pipeline (files -> load_test -> run -> export) is checked against the exact
steady-state solution of a textbook problem, not against this project's own synthetic model.

Problem. A uniform beam, clamped to a shaker table at x = 0 and free at x = L, has its table
move along Z with acceleration a_b(t). With a complex modulus E(1 + j*eta) (hysteretic damping),
the absolute motion w(x) per unit table motion solves

    EI w'''' - rhoA w^2 w = 0,   w(0) = 1, w'(0) = 0, w''(L) = 0, w'''(L) = 0.

The closed form, with lam = beta*L, beta^4 = rhoA w^2 / (EI (1 + j eta)) and xi = x/L, is

    T(xi) = (cosh lam xi + cos lam xi)/2
            + [sinh lam sin lam (cosh lam xi - cos lam xi)
               - (cosh lam sin lam + cos lam sinh lam)(sinh lam xi - sin lam xi)] / (2 (1 + cos lam cosh lam)).

Its denominator vanishes at the cantilever frequency equation 1 + cos lam cosh lam = 0, so
f_n = lam_n^2 / (2 pi L^2) sqrt(EI / rhoA), with lam_n = 1.87510407, 4.69409113, 7.85475744, ...
[Blevins 1979, Table 8-1]. The first tests below verify the reference itself three ways (these
tabulated roots, a direct 4 x 4 boundary-value solve, and a converging modal sum), so a slip in
the formula can't hide behind the pipeline.

Test signal. 60 s of white Gaussian base acceleration (1 g rms, fs = 5120 Hz) is passed through
T exactly in the frequency domain. Every channel, the control included, gets 1e-3 g rms of white
sensor noise. Eight +Z accelerometers sit at x = L/8 ... L; the control is at the clamp.

Tolerances. The normalised-error band follows from estimation theory [Bendat & Piersol 2010];
the others are empirical, set with margin over the worst of 82 independent seeds (quoted next to
each limit). The fixed seed used here is not a cherry-picked one, and NumPy's generator stream is
stable, so the test is deterministic.
- Away from resonances the H1 error is random (the leakage bias there is far below it):
  normalised by the theoretical random error, |dT| follows a Rayleigh law (p95 = 1.73, p99 = 2.15).
- At a resonance the error is larger: the Hann window smears a peak only ~8 bins wide, and the
  coherence dips there. Peak amplitudes are therefore checked at a looser, stated tolerance.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest
import scipy.integrate
import scipy.optimize

from ods import G0
from ods.io import load_test
from ods.pipeline import export, run
from ods.shapes import mac

# Aluminium strip, SI units: 200 x 25 x 3 mm.
L, WIDTH, THICK, E_MOD, RHO, ETA = 0.200, 0.025, 0.003, 70e9, 2700.0, 0.04
EI, RHO_A = E_MOD * WIDTH * THICK**3 / 12, RHO * WIDTH * THICK
BLEVINS_LAMBDA = np.array([1.87510407, 4.69409113, 7.85475744, 10.99554073])  # Blevins (1979), Table 8-1
XI = np.arange(1, 9) / 8  # sensor stations x / L
FS, DURATION, DF, NOISE_G = 5120.0, 60.0, 0.3125, 1e-3
BAND = (20.0, 1500.0)  # holds modes 1-3 (61.7, 386.6, 1082.5 Hz); mode 4 is at 2121 Hz


def cantilever_lambdas(n: int = 4) -> np.ndarray:
    """Roots of 1 + cos(lam) cosh(lam) = 0; beyond the 6th, lam_n = (2n - 1) pi / 2 to < 1e-8."""
    brackets = [(1.0, 3.0), (4.0, 5.5), (7.0, 9.0), (10.0, 12.0), (13.0, 15.0), (16.5, 18.0)]
    roots = [scipy.optimize.brentq(lambda x: 1 + np.cos(x) * np.cosh(x), a, b, xtol=1e-14) for a, b in brackets]
    roots += [(2 * k - 1) * np.pi / 2 for k in range(7, n + 1)]
    return np.array(roots[:n])


def natural_frequencies(n: int = 4) -> np.ndarray:
    """Undamped cantilever natural frequencies, Hz."""
    return cantilever_lambdas(n) ** 2 / (2 * np.pi * L**2) * np.sqrt(EI / RHO_A)


def cantilever_T(xi: np.ndarray, f: np.ndarray) -> np.ndarray:
    """Exact absolute transmissibility (complex, g/g), shape (len(f), len(xi)). f must be > 0."""
    w = 2 * np.pi * np.asarray(f, dtype=float)
    lam = (L * (RHO_A * w**2 / (EI * (1 + 1j * ETA))) ** 0.25)[:, None]
    z = lam * np.asarray(xi, dtype=float)[None, :]
    c, s, ch, sh = np.cos(lam), np.sin(lam), np.cosh(lam), np.sinh(lam)
    return 0.5 * (np.cosh(z) + np.cos(z)) + (
        sh * s * (np.cosh(z) - np.cos(z)) - (ch * s + c * sh) * (np.sinh(z) - np.sin(z))
    ) / (2 * (1 + c * ch))


def cantilever_mode(lam_n: float, xi: np.ndarray) -> np.ndarray:
    """Classical mode shape cosh - cos - sigma (sinh - sin), written without e^lam cancellation."""
    one_minus_sigma = (np.exp(-lam_n) + np.cos(lam_n) + np.sin(lam_n)) / (np.cosh(lam_n) + np.cos(lam_n))
    sigma = 1 - one_minus_sigma
    z = lam_n * np.asarray(xi, dtype=float)
    # cosh z - sigma sinh z = ((1 - sigma) e^z + (1 + sigma) e^-z) / 2
    return 0.5 * (one_minus_sigma * np.exp(z) + (1 + sigma) * np.exp(-z)) - np.cos(z) + sigma * np.sin(z)


def resonance_mask(f: np.ndarray, bandwidths: float = 3.0) -> np.ndarray:
    """Bins within `bandwidths` half-power bandwidths (eta * f_n, the full width) of each mode."""
    near = np.zeros(f.shape, dtype=bool)
    for fn in natural_frequencies():
        near |= np.abs(f - fn) < bandwidths * ETA * fn
    return near


def write_cantilever_test(out_dir: Path, seed: int) -> None:
    """Simulate the shaker run and write it in the pipeline's input layout."""
    rng = np.random.default_rng(seed)
    n = int(FS * DURATION)
    base = rng.standard_normal(n)  # white, 1 g rms
    f = np.fft.rfftfreq(n, 1 / FS)
    T = np.ones((f.size, XI.size), dtype=complex)  # DC: the beam moves with the table
    T[1:] = cantilever_T(XI, f[1:])
    # Multiplying the whole record's FFT is exact steady state for this (periodic) record.
    resp = np.fft.irfft(np.fft.rfft(base)[:, None] * T, n=n, axis=0)
    data = np.column_stack([base, resp]) + NOISE_G * rng.standard_normal((n, 1 + XI.size))

    out_dir.mkdir(parents=True, exist_ok=True)
    names = ["ctrl"] + [f"a{i}" for i in range(1, XI.size + 1)]
    np.savez_compressed(out_dir / "time.npz", data=data, fs=FS, channels=np.array(names))
    (out_dir / "test.json").write_text(json.dumps({"fs": FS, "units": "g", "excitation_axis": "Z"}))
    nodes = "".join(f"{i},{x * L:.6f},0,0,0\n" for i, x in enumerate(XI, 1))
    (out_dir / "geometry.csv").write_text("node,x,y,z,base\n0,0,0,0,1\n" + nodes)
    chans = "".join(f"a{i},{i},+Z,response\n" for i in range(1, XI.size + 1))
    (out_dir / "channels.csv").write_text("channel,node,direction,role\nctrl,0,+Z,control\n" + chans)
    (out_dir / "lines.csv").write_text("node_a,node_b\n" + "".join(f"{i},{i + 1}\n" for i in range(XI.size)))


# ---------------------------------------------------------------- the reference solution itself


def test_reference_frequency_equation_matches_blevins():
    np.testing.assert_allclose(cantilever_lambdas(), BLEVINS_LAMBDA, atol=1e-8)
    assert natural_frequencies()[0] == pytest.approx(61.69, abs=0.01)  # 3.516/(2 pi L^2) sqrt(EI/rhoA)


def test_reference_matches_direct_boundary_value_solve():
    """Solve w = A cos + B sin + C cosh + D sinh with the four boundary conditions numerically."""
    f = np.linspace(5, 2500, 300)
    lam = L * (RHO_A * (2 * np.pi * f) ** 2 / (EI * (1 + 1j * ETA))) ** 0.25
    xi = np.linspace(0, 1, 11)
    direct = []
    for q in lam:
        bc = np.array(
            [
                [1, 0, 1, 0],  # w(0) = 1
                [0, q, 0, q],  # w'(0) = 0
                [-(q**2) * np.cos(q), -(q**2) * np.sin(q), q**2 * np.cosh(q), q**2 * np.sinh(q)],  # w''(L) = 0
                [q**3 * np.sin(q), -(q**3) * np.cos(q), q**3 * np.sinh(q), q**3 * np.cosh(q)],  # w'''(L) = 0
            ],
            dtype=complex,
        )
        a = np.linalg.solve(bc, np.array([1, 0, 0, 0], dtype=complex))
        z = q * xi
        direct.append(a[0] * np.cos(z) + a[1] * np.sin(z) + a[2] * np.cosh(z) + a[3] * np.sinh(z))
    np.testing.assert_allclose(cantilever_T(xi, f), np.array(direct), rtol=1e-8)


def test_reference_static_limit_and_modal_sum():
    """T -> 1 as f -> 0, and a 64-mode modal sum converges onto the closed form."""
    assert cantilever_T(np.array([0.5, 1.0]), np.array([1e-3])) == pytest.approx(1.0, abs=1e-9)
    f = np.linspace(20, 1500, 200)
    xg = np.linspace(0, 1, 20001)
    lams = cantilever_lambdas(64)
    wn = 2 * np.pi * lams**2 / (2 * np.pi * L**2) * np.sqrt(EI / RHO_A)
    T_modal = np.ones((f.size, XI.size), dtype=complex)
    for lam_n, w_n in zip(lams, wn):
        phi_g = cantilever_mode(lam_n, xg)
        gamma = scipy.integrate.trapezoid(phi_g, xg) / scipy.integrate.trapezoid(phi_g**2, xg)  # uniform mass
        r2 = (2 * np.pi * f / w_n) ** 2
        T_modal += (r2 / (1 + 1j * ETA - r2))[:, None] * gamma * cantilever_mode(lam_n, XI)[None, :]
    np.testing.assert_allclose(T_modal, cantilever_T(XI, f), rtol=2e-5)


# ---------------------------------------------------------------- the pipeline against it


@pytest.fixture(scope="module")
def cantilever(tmp_path_factory):
    d = tmp_path_factory.mktemp("cantilever")
    write_cantilever_test(d, seed=7)
    test = load_test(d)
    res = run(test, df=DF, band=BAND)
    out = d / "out"
    export(res, out)
    return test, res, out


def _in_band(res):
    f = res.spectra.f
    k = (f >= BAND[0]) & (f <= BAND[1])
    return k, f[k]


def test_transmissibility_matches_exact_away_from_resonance(cantilever):
    test, res, _ = cantilever
    k, f = _in_band(res)
    T_meas = res.spectra.T[k][:, test.responses]
    T_true = cantilever_T(XI, f)
    away = ~resonance_mask(f)
    rel = np.abs(T_meas - T_true)[away] / np.abs(T_true)[away]
    phase = np.degrees(np.abs(np.angle(T_meas[away] / T_true[away])))
    assert np.median(rel) < 1e-3  # 82-seed worst: 0.033 %
    assert np.percentile(rel, 99) < 0.012  # 82-seed worst: 0.66 %
    assert rel.max() < 0.08  # 82-seed worst: 5.8 % (near an antiresonance, where |T| is small)
    assert phase.max() < 4.0  # deg; 82-seed worst: 2.6
    np.testing.assert_allclose(res.spectra.T[k][:, test.control], 1.0)  # the control gain is +1 here


def test_random_error_matches_theory(cantilever):
    """Off resonance the H1 error is purely random, of the size Bendat & Piersol predict.

    eps = sqrt((1 - coh) / (2 n_avg coh)) is the normalised random error of |H|; the complex
    error has rms sqrt(2) eps |T|, and its magnitude follows a Rayleigh law. A bias of even a
    fraction of eps (a wrong spectral convention, scaling or window treatment) would shift
    these percentiles well past the limits.
    """
    test, res, _ = cantilever
    k, f = _in_band(res)
    T_meas = res.spectra.T[k][:, test.responses]
    coh = res.spectra.coh[k][:, test.responses]
    eps = np.sqrt((1 - coh) / (2 * res.spectra.n_avg * coh))
    z = np.abs(T_meas - cantilever_T(XI, f)) / (np.sqrt(2) * eps * np.abs(T_meas))
    z = z[~resonance_mask(f)]
    p95, p99 = np.percentile(z, [95, 99])
    # Rayleigh: 1.73 and 2.15. At 36 averages the expected values are a few % higher (about 1.80
    # and 2.25; 82 seeds gave 1.77-1.83 and 2.21-2.31): the eps formula is a large-sample one, and
    # coherence estimated from few averages reads high, so eps is slightly underestimated.
    assert 1.65 < p95 < 1.95
    assert 2.05 < p99 < 2.50


def test_peaks_are_the_cantilever_modes(cantilever):
    _, res, _ = cantilever
    fn = natural_frequencies()[:3]
    found = np.array([p.f for p in res.peaks])
    assert found.size == 3, f"expected the 3 in-band modes, got peaks at {found}"
    # A broad peak's maximum scatters by a fraction of its half-power bandwidth, so the limit
    # is the larger of 1.5 bins and 10 % of eta * f_n. 82-seed worst: 0.19, 0.66 and 1.57 Hz
    # against limits of 0.47, 1.55 and 4.33 Hz.
    tol = np.maximum(1.5 * DF, 0.1 * ETA * fn)
    assert np.all(np.abs(found - fn) <= tol), f"peaks {found} vs exact {fn}"
    assert min(p.coh for p in res.peaks) > 0.95  # 82-seed worst: 0.968


def test_ods_at_each_peak_matches_exact_shape(cantilever):
    """The measured ODS is the exact operating shape at that frequency, in shape and amplitude."""
    test, res, _ = cantilever
    lams = cantilever_lambdas(3)
    # Peak amplitude tolerances, by mode: the sharp 61.7 Hz peak spans only ~8 bins, so
    # window smearing plus the coherence dip there cost a few %. 82-seed worst: 5.3, 0.74, 0.39 %.
    amp_tol = [0.08, 0.015, 0.015]
    for p, lam_n, tol in zip(res.peaks, lams, amp_tol):
        T_true = cantilever_T(XI, [p.f])[0]
        T_meas = res.spectra.T[p.index, test.responses]
        assert 1 - mac(T_meas, T_true) < 1e-5  # 82-seed worst: 2.2e-6
        assert np.abs(T_meas[-1] / T_true[-1] - 1) < tol
        # The ODS is not the mode shape: nearby modes and the residual of the rest mix in.
        # It must sit exactly as far from the classical mode as the exact solution does.
        disp_meas = res.disp[p.index, test.responses]
        mac_true = mac(T_true - 1, cantilever_mode(lam_n, XI))
        assert mac(disp_meas, cantilever_mode(lam_n, XI)) == pytest.approx(mac_true, abs=2e-4)  # worst of 20 seeds: 5.6e-5


def test_exported_peak_table_in_mm_per_g(cantilever):
    """ods_peaks.csv carries the right numbers in the right units: tip displacement in mm/g."""
    test, res, out = cantilever
    with open(out / "ods_peaks.csv", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["channel"] == "a8"]
    assert len(rows) == len(res.peaks)
    for row, p, tol in zip(rows, res.peaks, [0.08, 0.015, 0.015]):
        f_pk = float(row["f_hz"])
        assert f_pk == pytest.approx(p.f, abs=1e-3)
        T_rel_true = cantilever_T(XI[-1:], [f_pk])[0, 0] - 1  # relative to the table
        disp_true_mm = abs(T_rel_true) * G0 * 1e3 / (2 * np.pi * f_pk) ** 2  # x = a / w^2, in mm per g
        assert float(row["disp_rel_mm_per_g"]) == pytest.approx(disp_true_mm, rel=tol)
    # Hand check of magnitude: tip participation 1.566 / eta = 39 g/g relative, and
    # 39 * 9807 mm/s^2 / (2 pi 61.7 Hz)^2 = 2.5 mm of tip motion per g of table input.
    assert float(rows[0]["disp_rel_mm_per_g"]) == pytest.approx(2.5, rel=0.1)


def test_exported_transmissibility_csv_matches_exact(cantilever):
    """transmissibility.csv (rounded to 6 significant figures) still matches the exact solution."""
    _, _, out = cantilever
    tab = np.genfromtxt(out / "transmissibility.csv", delimiter=",", names=True)
    f = tab["f_hz"]
    keep = (f >= BAND[0]) & (f <= BAND[1]) & ~resonance_mask(f)
    T_true = cantilever_T(XI[-1:], f[keep])[:, 0]
    rel_mag = np.abs(tab["a8_mag"][keep] / np.abs(T_true) - 1)
    dphase = (tab["a8_phase_deg"][keep] - np.degrees(np.angle(T_true)) + 180) % 360 - 180
    assert np.percentile(rel_mag, 99) < 0.012
    assert np.abs(dphase).max() < 4.0
