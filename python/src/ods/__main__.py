"""Command line: ``ods synth`` makes a synthetic test, ``ods run <test_dir>`` computes ODS."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

from .io import _check_size, _in_folder, load_test, npz_bytes
from .pipeline import export, run
from .shapes import mac
from .viewer import build_viewer


def _cmd_synth(a: argparse.Namespace) -> None:
    from .synth import build_box_model, simulate, write_test

    t0 = time.perf_counter()
    model = build_box_model()
    sim = simulate(model, a.axis, a.fs, a.duration, seed=a.seed)
    write_test(Path(a.out), model, sim, fmt=a.format)
    m = sim["modes"]
    print(f"Wrote synthetic test to {a.out} ({sim['data'].shape[0]} samples x {sim['data'].shape[1]} ch, "
          f"input {sim['grms_input']:.2f} grms, {time.perf_counter() - t0:.1f} s)")
    print("True modes (Hz, zeta, participation along excitation):")
    for f, z, g in zip(m.fn, m.zeta, m.participation):
        print(f"  {f:8.1f}  {z:.2f}  {g:+.3f}")


def _compare_truth(res, truth_path: Path) -> None:
    """Match each ODS peak to the nearest true mode and report MAC on measured DOFs."""
    # truth.npz is picked up from the test folder automatically: same size guard as the time file.
    _check_size(npz_bytes(truth_path, ("node_ids", "fn", "phi"), numeric="phi"), truth_path)
    tr = np.load(truth_path)
    t = res.test
    node_index = {int(n): i for i, n in enumerate(tr["node_ids"])}
    resp = t.responses
    rows = [3 * node_index[t.channel_nodes[c]] + int(np.argmax(np.abs(t.channel_dirs[c]))) for c in resp]
    signs = np.array([np.sign(t.channel_dirs[c][np.argmax(np.abs(t.channel_dirs[c]))]) for c in resp])
    print("\nPeak vs. nearest true mode, MAC on measured DOFs for each view of the ODS:")
    print("  (abs = absolute T, rel = relative to table, el = rigid-body removed from ODS and mode)")
    print(f"  {'ODS f':>8}  {'true fn':>8}  {'Δf':>6}  {'MAC abs':>7}  {'MAC rel':>7}  {'MAC el':>6}  {'MPC abs':>7}  {'γ² wtd':>6}")
    for p in res.peaks:
        j = int(np.argmin(np.abs(tr["fn"] - p.f)))
        phi = tr["phi"][rows, j] * signs
        k = p.index
        m_abs = mac(res.spectra.T[k, resp], phi)
        m_rel = mac(res.disp[k, resp], phi)
        m_el = mac(res.disp_el[k, resp], res.rigid_R @ phi)
        print(f"  {p.f:8.2f}  {tr['fn'][j]:8.2f}  {p.f - tr['fn'][j]:+6.2f}  {m_abs:7.3f}  {m_rel:7.3f}  {m_el:6.3f}  {p.mpc:7.3f}  {p.coh:6.3f}")


def _cmd_run(a: argparse.Namespace) -> None:
    t0 = time.perf_counter()
    test = load_test(a.test_dir)
    res = run(test, df=a.df, band=(a.fmin, a.fmax), prominence_db=a.prominence, min_coh=a.min_coh)
    out = Path(a.out)
    files = export(res, out)
    viewer = build_viewer(res, out / "ods_viewer.html", title=a.title or Path(a.test_dir).name)
    sp = res.spectra
    print(f"{len(test.channel_names)} channels, fs {test.fs:g} Hz, nfft {sp.nfft} (Δf {sp.f[1]:.3f} Hz), "
          f"{sp.n_avg} averages, {time.perf_counter() - t0:.1f} s")
    print(f"{len(res.peaks)} peaks: " + ", ".join(f"{p.f:.1f}" for p in res.peaks) + " Hz")
    for f in files + [viewer]:
        print(f"  wrote {f}")
    truth = _in_folder(Path(a.test_dir), "truth.npz")
    if truth.exists():
        _compare_truth(res, truth)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="ods", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("synth", help="generate a synthetic shaker test")
    s.add_argument("--out", default="data/synthetic")
    s.add_argument("--axis", default="Z", choices=["X", "Y", "Z"])
    s.add_argument("--fs", type=float, default=5120.0)
    s.add_argument("--duration", type=float, default=60.0, help="seconds")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--format", default="npz", choices=["npz", "mat", "csv"], help="time-history file format")
    s.set_defaults(func=_cmd_synth)

    r = sub.add_parser("run", help="compute ODS for a test directory")
    r.add_argument("test_dir")
    r.add_argument("--out", default="outputs")
    r.add_argument("--df", type=float, default=0.625, help="target frequency resolution, Hz")
    r.add_argument("--fmin", type=float, default=20.0)
    r.add_argument("--fmax", type=float, default=2000.0)
    r.add_argument("--prominence", type=float, default=3.0, help="peak prominence, dB")
    r.add_argument("--min-coh", type=float, default=0.5)
    r.add_argument("--title", default=None)
    r.set_defaults(func=_cmd_run)

    a = ap.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
