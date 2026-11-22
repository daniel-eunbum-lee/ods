"""Tests for the ODS pipeline. Run with: uv run pytest"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
import scipy.signal

from ods import G0
from ods.io import load_test, parse_direction
from ods.pipeline import export, run
from ods.shapes import (
    accel_to_displacement,
    mac,
    mpc,
    node_projectors,
    relative_transmissibility,
    rigid_body_projector,
)
from ods.spectra import compute_spectra, nfft_for_resolution
from ods.synth import Modes, build_box_model, dof_transmissibility, simulate, write_test
from ods.viewer import build_viewer


def sdof_T(f: np.ndarray, fn: float, zeta: float) -> np.ndarray:
    """Classic base-excitation absolute transmissibility of an SDOF."""
    w, wn = 2 * np.pi * f, 2 * np.pi * fn
    return (wn**2 + 2j * zeta * wn * w) / (wn**2 - w**2 + 2j * zeta * wn * w)


# ---------------------------------------------------------------- spectra


def test_nfft_for_resolution():
    assert nfft_for_resolution(5120, 0.625) == 8192
    assert nfft_for_resolution(5120, 1.0) == 8192  # 5120 rounds up to next power of two
    assert nfft_for_resolution(1024, 1.0) == 1024


def test_h1_recovers_sdof_transmissibility():
    fs, n, fn, zeta = 2048.0, 2**18, 100.0, 0.05
    rng = np.random.default_rng(0)
    b = rng.standard_normal(n)
    f_full = np.fft.rfftfreq(n, 1 / fs)
    x = np.fft.irfft(np.fft.rfft(b) * sdof_T(f_full, fn, zeta), n=n)
    x += 1e-3 * rng.standard_normal(n)  # response noise: H1 should be unbiased by it
    sp = compute_spectra(np.column_stack([b, x]), control=0, fs=fs, nfft=2048)

    band = (sp.f > 10) & (sp.f < 800)
    T_true = sdof_T(sp.f[band], fn, zeta)
    rel_err = np.abs(sp.T[band, 1] - T_true) / np.abs(T_true)
    assert np.median(rel_err) < 0.01
    assert rel_err.max() < 0.08  # worst near the peak (window bias at 1 Hz resolution)
    assert np.allclose(sp.T[band, 0], 1.0)  # control against itself
    assert sp.coh[band, 1].min() > 0.98


def test_csd_broadcasting_matches_per_channel_loop():
    """compute_spectra relies on scipy.signal.csd broadcasting (1, N) against (nch, N)."""
    rng = np.random.default_rng(1)
    data = rng.standard_normal((8192, 3))
    data[:, 1] += 0.5 * data[:, 0]
    sp = compute_spectra(data, control=0, fs=1000.0, nfft=512)
    for c in range(3):
        _, gbx = scipy.signal.csd(data[:, 0], data[:, c], fs=1000.0, window="hann", nperseg=512, noverlap=256)
        _, gbb = scipy.signal.welch(data[:, 0], fs=1000.0, window="hann", nperseg=512, noverlap=256)
        np.testing.assert_allclose(sp.T[:, c], gbx / gbb, rtol=1e-10, atol=1e-12)


def test_record_shorter_than_nfft_raises():
    with pytest.raises(ValueError, match="shorter than nfft"):
        compute_spectra(np.zeros((100, 2)), 0, 1000.0, 256)


# ---------------------------------------------------------------- shapes


def test_relative_transmissibility_subtracts_projection_only():
    T = np.ones((4, 3), dtype=complex)
    dirs = np.array([[0, 0, 1.0], [1.0, 0, 0], [0, -0.6, 0.8]])
    rel = relative_transmissibility(T, dirs, np.array([0, 0, 1.0]))
    np.testing.assert_allclose(rel[0], [0.0, 1.0, 0.2])


def test_accel_to_displacement_units_and_sign():
    f = np.array([0.0, 10.0])
    d = accel_to_displacement(np.array([1.0, 1.0]), f, units="g")
    # 1 g at 10 Hz: x = -g0 / w^2 = -9.80665 / (2*pi*10)^2 m = -2.484 mm
    assert d[0] == 0.0
    assert d[1] == pytest.approx(-G0 / (2 * np.pi * 10) ** 2 * 1e3, rel=1e-12)
    assert d[1] == pytest.approx(-2.484, abs=1e-3)
    d_si = accel_to_displacement(np.array([1.0, 1.0]), f, units="m/s^2")
    assert d_si[1] == pytest.approx(d[1] / G0)


def test_mpc_and_mac():
    real = np.array([1.0, -2.0, 0.5]) * np.exp(1j * 0.7)  # rotated real shape is still standing
    assert mpc(real) == pytest.approx(1.0)
    assert mpc(np.array([1, 1j, -1, -1j])) == pytest.approx(0.0, abs=1e-12)  # travelling wave
    assert mac(real, 3 * real) == pytest.approx(1.0)
    assert mac(np.array([1.0, 0]), np.array([0, 1.0])) == pytest.approx(0.0)


def test_rigid_body_projector_removes_rigid_motion_only():
    rng = np.random.default_rng(2)
    pos = np.repeat(rng.uniform(-1, 1, (5, 3)), 3, axis=0)
    dirs = np.tile(np.eye(3), (5, 1))
    R = rigid_body_projector(pos, dirs)
    t, th = rng.standard_normal(3), rng.standard_normal(3)
    rigid = np.einsum("ij,ij->i", dirs, t + np.cross(th, pos - pos.mean(axis=0)))
    np.testing.assert_allclose(R @ rigid, 0, atol=1e-10)
    assert np.trace(R) == pytest.approx(len(dirs) - 6)  # projector onto a (k-6)-dim subspace


def test_node_projectors_triax_and_partial():
    dirs = np.array([[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0], [0, 0, -1.0]])
    proj = node_projectors(np.array([1, 2]), np.array([1, 1, 1, 2]), dirs, np.arange(4))
    u1 = proj[1][1] @ np.array([1.0, 2.0, 3.0])
    np.testing.assert_allclose(u1, [1, 2, 3])
    u2 = proj[2][1] @ np.array([4.0])  # single -Z sensor: X/Y unmeasured -> 0
    np.testing.assert_allclose(u2, [0, 0, -4], atol=1e-12)


def test_parse_direction():
    np.testing.assert_allclose(parse_direction("-y"), [0, -1, 0])
    np.testing.assert_allclose(parse_direction("1 1 0"), [2**-0.5, 2**-0.5, 0])
    with pytest.raises(ValueError):
        parse_direction("Q")


# ---------------------------------------------------------------- synthetic model


def test_modal_transmissibility_matches_sdof():
    fn, zeta = 50.0, 0.03
    modes = Modes(np.array([fn]), np.array([zeta]), np.array([[1.0]]), np.array([1.0]))  # unit mass
    f = np.linspace(1, 500, 200)
    # r + w^2 / (wn^2 - w^2 + 2j zeta wn w) is algebraically the classic SDOF formula.
    np.testing.assert_allclose(dof_transmissibility(modes, np.array([1.0]), f)[0], sdof_T(f, fn, zeta))


def test_box_model_is_well_posed():
    m = build_box_model()
    assert np.allclose(m.K, m.K.T)
    assert np.linalg.eigvalsh(m.K).min() > 0  # isolators ground every rigid-body DOF
    assert m.M.trace() / 3 == pytest.approx(3.8)


# ---------------------------------------------------------------- end to end


@pytest.fixture(scope="module")
def synthetic_results(tmp_path_factory):
    d = tmp_path_factory.mktemp("synth")
    model = build_box_model()
    sim = simulate(model, "Z", fs=5120.0, duration=20.0, seed=3)
    write_test(d, model, sim)
    test = load_test(d)
    return d, test, run(test, df=1.25), np.load(d / "truth.npz")


def test_input_level_matches_profile(synthetic_results):
    d, test, res, truth = synthetic_results
    grms = np.std(test.data[:, test.control])
    assert grms == pytest.approx(6.06, rel=0.03)  # NAVMAT profile is 6.06 grms


def _truth_rows(test, truth):
    idx = {int(n): i for i, n in enumerate(truth["node_ids"])}
    rows = [3 * idx[int(test.channel_nodes[c])] + int(np.argmax(np.abs(test.channel_dirs[c]))) for c in test.responses]
    return rows


@pytest.mark.parametrize("fn_expected, view, mac_min", [(54.6, "rel", 0.99), (283.3, "el", 0.98), (348.7, "el", 0.93)])
def test_ods_matches_true_modes(synthetic_results, fn_expected, view, mac_min):
    d, test, res, truth = synthetic_results
    df = res.spectra.f[1]
    peak = min(res.peaks, key=lambda p: abs(p.f - fn_expected))
    assert abs(peak.f - fn_expected) <= 1.5 * df
    j = int(np.argmin(np.abs(truth["fn"] - fn_expected)))
    phi = truth["phi"][_truth_rows(test, truth), j]
    resp = test.responses
    if view == "rel":
        assert mac(res.disp[peak.index, resp], phi) > mac_min
    else:
        assert mac(res.disp_el[peak.index, resp], res.rigid_R @ phi) > mac_min


def test_export_and_viewer(synthetic_results, tmp_path):
    d, test, res, truth = synthetic_results
    files = export(res, tmp_path)
    assert {f.name for f in files} >= {"ods_results.npz", "ods_peaks.csv", "transmissibility.csv"}
    z = np.load(tmp_path / "ods_results.npz")
    assert z["peak_shapes_mm_per_unit"].shape == (len(res.peaks), len(test.channel_names))
    html = build_viewer(res, tmp_path / "v.html").read_text(encoding="utf-8")
    assert "/*__ODS_DATA__*/" not in html
    assert '"rigidR"' in html and '"peaks"' in html


def test_csv_input_matches_npz(tmp_path):
    model = build_box_model()
    sim = simulate(model, "Z", fs=1024.0, duration=2.0, seed=4)
    write_test(tmp_path / "npz", model, sim, fmt="npz")
    write_test(tmp_path / "csv", model, sim, fmt="csv")
    write_test(tmp_path / "mat", model, sim, fmt="mat")
    a, b, c = load_test(tmp_path / "npz"), load_test(tmp_path / "csv"), load_test(tmp_path / "mat")
    assert b.fs == pytest.approx(1024.0)
    assert c.fs == pytest.approx(1024.0)
    assert b.channel_names == a.channel_names == c.channel_names
    np.testing.assert_allclose(b.data, a.data, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(c.data, a.data, rtol=0, atol=0)


def test_matlab_parity_fixture_is_current():
    """matlab/tests/run_tests.m compares MATLAB against this fixture; it must match Python now."""
    from pathlib import Path

    import scipy.io

    fx = Path(__file__).parents[1] / "matlab" / "tests" / "fixtures" / "parity"
    ex = scipy.io.loadmat(fx / "expected.mat")
    res = run(load_test(fx), df=float(ex["df"].squeeze()), band=tuple(ex["band"].ravel()))
    np.testing.assert_allclose(res.spectra.T, ex["T"], rtol=1e-12, atol=1e-15)
    np.testing.assert_allclose(res.T_el, ex["T_el"], rtol=1e-12, atol=1e-15)
    np.testing.assert_allclose(res.spectra.coh, ex["coh"], rtol=0, atol=1e-12)
    np.testing.assert_allclose(res.spectra.Gxx, ex["Gxx"], rtol=1e-12, atol=0)
    np.testing.assert_allclose(res.rigid_R, ex["rigid_R"], rtol=0, atol=1e-12)
    np.testing.assert_allclose(res.disp_el, ex["disp_el"], rtol=1e-12, atol=1e-15)
    assert [p.index + 1 for p in res.peaks] == ex["peak_index"].ravel().astype(int).tolist()


# ---------------------------------------------------------------- regressions from code review


def test_no_spurious_peak_at_band_edge():
    """A curve falling across fmin must not yield a 'peak' at the first in-band bin."""
    from ods.shapes import find_peaks

    f = np.arange(200.0)
    x = -0.2 * f
    x[119:122] += [6, 12, 6]  # bump centred on 120 Hz
    T = (10 ** (x / 20))[:, None]
    peaks = find_peaks(f, T, np.ones_like(T, dtype=float), band=(60, 199), prominence_db=3, min_coh=0.5)
    assert [p.f for p in peaks] == [120.0]


def test_inverted_control_gives_same_views(synthetic_results):
    """A control mounted -Z (data negated) must give the same T, relative and elastic views."""
    d, test, res, truth = synthetic_results
    data = test.data.copy()
    data[:, test.control] *= -1
    dirs = test.channel_dirs.copy()
    dirs[test.control] *= -1
    flipped = run(dataclasses.replace(test, data=data, channel_dirs=dirs), df=1.25)
    resp = test.responses
    np.testing.assert_allclose(flipped.spectra.T[:, resp], res.spectra.T[:, resp], rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(flipped.spectra.T[:, test.control], -1.0)  # it reads minus the table
    np.testing.assert_allclose(flipped.T_rel, res.T_rel, rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(flipped.T_el, res.T_el, rtol=1e-9, atol=1e-12)


def test_control_perpendicular_to_excitation_raises(synthetic_results):
    d, test, res, truth = synthetic_results
    dirs = test.channel_dirs.copy()
    dirs[test.control] = [1.0, 0.0, 0.0]
    with pytest.raises(ValueError, match="Control direction"):
        run(dataclasses.replace(test, channel_dirs=dirs), df=1.25)


def _write_small_test(d, time_text: str, meta: dict | None = None, bom: str = "") -> None:
    import json

    d.mkdir()
    (d / "time.csv").write_text(bom + time_text, encoding="utf-8")
    (d / "geometry.csv").write_text(bom + "node,x,y,z,base\n1,0,0,0,TRUE\n2,1,0,0,0\n\n", encoding="utf-8")
    (d / "channels.csv").write_text(bom + "channel,node,direction,role\nC,1,+Z,control\nA,2,+Z\n", encoding="utf-8")
    if meta is not None:
        (d / "test.json").write_text(json.dumps(meta), encoding="utf-8")


def test_fs_from_rounded_time_column(tmp_path):
    fs = 5120.0
    rows = "\n".join(f"{i / fs:.6f},{np.sin(i)},{np.cos(i)}" for i in range(4000))
    _write_small_test(tmp_path / "t", "time,C,A\n" + rows + "\n")
    assert load_test(tmp_path / "t").fs == pytest.approx(fs, rel=1e-5)


def test_test_json_fs_wins_over_time_file(tmp_path):
    rows = "\n".join(f"{i / 1000:.6f},{np.sin(i)},{np.cos(i)}" for i in range(100))
    _write_small_test(tmp_path / "t", "time,C,A\n" + rows + "\n", meta={"fs": 2000})
    assert load_test(tmp_path / "t").fs == 2000.0


def test_csv_with_bom_short_rows_and_case(tmp_path):
    rows = "\n".join(f"{np.sin(i)},{np.cos(i)}" for i in range(100))
    _write_small_test(tmp_path / "t", "C,A\n" + rows + "\n", meta={"fs": 100}, bom="﻿")
    t = load_test(tmp_path / "t")  # BOM on every file, blank line in geometry, short channels row
    assert t.channel_names == ["C", "A"]
    assert t.node_is_base.tolist() == [True, False]  # base=TRUE accepted, as in MATLAB


def test_duplicate_channel_rows_raise(tmp_path):
    rows = "\n".join(f"{np.sin(i)},{np.cos(i)}" for i in range(100))
    _write_small_test(tmp_path / "t", "C,A\n" + rows + "\n", meta={"fs": 100})
    with open(tmp_path / "t" / "channels.csv", "a", encoding="utf-8") as fh:
        fh.write("A,1,+X,response\n")
    with pytest.raises(ValueError, match="Duplicate channel"):
        load_test(tmp_path / "t")


def test_export_with_no_peaks(synthetic_results, tmp_path):
    d, test, res, truth = synthetic_results
    res_empty = dataclasses.replace(res, peaks=[])
    export(res_empty, tmp_path)
    assert np.load(tmp_path / "ods_results.npz")["peak_shapes_mm_per_unit"].shape == (0, len(test.channel_names))
    build_viewer(res_empty, tmp_path / "v.html")
