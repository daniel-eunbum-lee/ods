"""End-to-end processing: test data -> spectra -> peaks -> ODS shapes, plus file export."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .io import TestData
from .shapes import Peak, accel_to_displacement, find_peaks, relative_transmissibility, rigid_body_projector
from .spectra import Spectra, compute_spectra, nfft_for_resolution


@dataclass
class Results:
    test: TestData
    spectra: Spectra
    T_rel: np.ndarray  # (nf, nch) transmissibility relative to the table, (unit/unit)
    T_el: np.ndarray  # (nf, nch) elastic part: rigid-body motion removed (control column = 0)
    disp: np.ndarray  # (nf, nch) relative displacement, mm per unit of input accel
    disp_el: np.ndarray  # (nf, nch) elastic displacement, mm per unit of input accel
    rigid_R: np.ndarray  # (nresp, nresp) rigid-body removal projector over response channels
    peaks: list[Peak]
    band: tuple[float, float]


def run(
    test: TestData,
    df: float = 0.625,
    band: tuple[float, float] = (20.0, 2000.0),
    prominence_db: float = 3.0,
    min_coh: float = 0.5,
) -> Results:
    if not np.std(test.data[:, test.control]) > 0:  # also catches NaN
        raise ValueError(f"Control channel {test.channel_names[test.control]!r} is constant (or not finite): no reference signal")
    if not df > 0:
        raise ValueError(f"df must be a positive frequency resolution (Hz), got {df!r}")
    nfft = nfft_for_resolution(test.fs, df)
    sp = compute_spectra(test.data, test.control, test.fs, nfft)
    # H1 is referenced to what the control reads, (d_ctrl . e) * table acceleration. Rescale so
    # T is per unit table acceleration along e; otherwise an inverted (-Z) or skewed control
    # breaks the relative view and the base-node motion.
    gain = float(test.channel_dirs[test.control] @ test.excitation_axis)
    if abs(gain) < 0.5:
        raise ValueError(
            f"Control direction is {np.degrees(np.arccos(min(1.0, abs(gain)))):.0f} deg from the excitation "
            "axis; check its direction in channels.csv and excitation_axis in test.json"
        )
    # b = gain * a_table, so H1 against b is T_true / gain: multiply to get T per unit a_table.
    sp.T = sp.T * gain
    T_rel = relative_transmissibility(sp.T, test.channel_dirs, test.excitation_axis)
    T_rel[:, test.control] = 0.0  # the control is the reference: zero relative motion by definition
    disp = accel_to_displacement(T_rel, sp.f, test.units)
    resp = test.responses

    node_pos = dict(zip(test.node_ids.tolist(), test.node_xyz))
    positions = np.array([node_pos[int(n)] for n in test.channel_nodes[resp]])
    R = rigid_body_projector(positions, test.channel_dirs[resp])
    T_el = np.zeros_like(T_rel)
    T_el[:, resp] = T_rel[:, resp] @ R.T  # table motion is rigid too, so T or T_rel give the same result
    disp_el = accel_to_displacement(T_el, sp.f, test.units)

    peaks = find_peaks(sp.f, sp.T[:, resp], sp.coh[:, resp], band, prominence_db, min_coh)
    return Results(test, sp, T_rel, T_el, disp, disp_el, R, peaks, band)


def csv_cell(text: str) -> str:
    """One CSV field from user text (a channel name or units), safe to open in a spreadsheet.

    A leading = + - @ (or tab / CR) makes Excel and LibreOffice evaluate the cell as a formula,
    so it gets a ' prefix (the OWASP recommendation). A comma, quote or line break would shift
    the columns, so such a field is quoted as in RFC 4180.
    """
    text = str(text)
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        text = "'" + text
    if any(ch in text for ch in ',"\r\n'):
        text = '"' + text.replace('"', '""') + '"'
    return text


def export(res: Results, out_dir: Path) -> list[Path]:
    """Write NPZ (everything) + CSVs (spectra and per-peak shapes). Returns written paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    t, sp = res.test, res.spectra
    names = t.channel_names
    written = []

    p = out_dir / "ods_results.npz"
    np.savez_compressed(
        p,
        f=sp.f,
        T=sp.T,
        T_rel=res.T_rel,
        disp_mm_per_unit=res.disp,
        T_elastic=res.T_el,
        disp_elastic_mm_per_unit=res.disp_el,
        rigid_R=res.rigid_R,
        coherence=sp.coh,
        Gbb=sp.Gbb,
        Gxx=sp.Gxx,
        channels=np.array(names),
        channel_nodes=t.channel_nodes,
        channel_dirs=t.channel_dirs,
        peak_f=np.array([pk.f for pk in res.peaks]),
        peak_index=np.array([pk.index for pk in res.peaks], dtype=int),
        peak_mpc_abs=np.array([pk.mpc for pk in res.peaks]),
        peak_coh_weighted=np.array([pk.coh for pk in res.peaks]),
        peak_shapes_mm_per_unit=res.disp[[pk.index for pk in res.peaks]],
        peak_shapes_elastic_mm_per_unit=res.disp_el[[pk.index for pk in res.peaks]],
        nfft=sp.nfft,
        n_avg=sp.n_avg,
        fs=t.fs,
    )
    written.append(p)

    keep = sp.f <= res.band[1]
    f = sp.f[keep]

    def _table(path: Path, header: list[str], cols: list[np.ndarray]) -> None:
        np.savetxt(path, np.column_stack(cols), delimiter=",", header=",".join(map(csv_cell, header)), comments="", fmt="%.6g", encoding="utf-8")
        written.append(path)

    _table(
        out_dir / "transmissibility.csv",
        ["f_hz"] + [f"{n}_mag" for n in names] + [f"{n}_phase_deg" for n in names],
        [f, np.abs(sp.T[keep]), np.degrees(np.angle(sp.T[keep]))],
    )
    _table(out_dir / "coherence.csv", ["f_hz"] + names, [f, sp.coh[keep]])
    unit2 = f"{t.units}^2/Hz"
    _table(out_dir / "asd.csv", ["f_hz"] + [f"{n}_{unit2}" for n in names], [f, sp.Gxx[keep]])

    p = out_dir / "ods_peaks.csv"
    with open(p, "w", encoding="utf-8") as fh:
        header = "peak,f_hz,mpc_abs,channel,node,dx,dy,dz,T_mag,T_phase_deg,T_rel_mag,T_rel_phase_deg".split(",") + [
            f"disp_rel_mm_per_{t.units}",
            "disp_rel_phase_deg",
            f"disp_elastic_mm_per_{t.units}",
            "disp_elastic_phase_deg",
            "coherence",
        ]
        fh.write(",".join(map(csv_cell, header)) + "\n")

        def _mp(z: complex) -> str:
            return f"{abs(z):.6g},{np.degrees(np.angle(z)):.2f}"

        for i, pk in enumerate(res.peaks, start=1):
            k = pk.index
            for c in t.responses:
                dx, dy, dz = t.channel_dirs[c]
                fh.write(
                    f"{i},{pk.f:.3f},{pk.mpc:.3f},{csv_cell(names[c])},{t.channel_nodes[c]},{dx:g},{dy:g},{dz:g},"
                    f"{_mp(sp.T[k, c])},{_mp(res.T_rel[k, c])},{_mp(res.disp[k, c])},{_mp(res.disp_el[k, c])},"
                    f"{sp.coh[k, c]:.4f}\n"
                )
    written.append(p)
    return written
