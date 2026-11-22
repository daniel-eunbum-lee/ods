"""Synthetic shaker test: a small box on four corner isolators, base-driven in one axis.

The model is a lumped-mass system with three translational DOFs per node:

* 8 box corners joined by axial bar springs (12 edges + 6 face diagonals). That
  triangulates every face, so the box is stiff and its elastic modes sit high.
* 4 isolators (axis-aligned bushings kx/ky/kz) from the bottom corners to the table,
  giving the low-frequency rigid-body modes (bounce, rock, sway).
* A top-panel centre node on bushings that are soft in Z only: a "panel drum" mode.
* Extra mass on one top corner so the CG is offset and bounce/pitch/roll couple under
  single-axis excitation (otherwise Z excitation would only show bounce).

Equation of motion in coordinates relative to the table (moving rigidly with base
acceleration a_b along unit axis e):

    M z'' + C z' + K z = -M r a_b,   r = e repeated per node

With mass-normalised modes Phi and modal damping, the absolute-acceleration
transmissibility of every DOF is

    T(w) = r + w^2 * sum_n phi_n (phi_n^T M r) / (w_n^2 - w^2 + 2j zeta_n w_n w)

which is exactly what the H1 estimate should recover.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy.linalg

AXES = {"X": np.array([1.0, 0.0, 0.0]), "Y": np.array([0.0, 1.0, 0.0]), "Z": np.array([0.0, 0.0, 1.0])}


@dataclass
class Model:
    """Lumped-mass model. Coordinates in m, masses in kg, stiffness in N/m."""

    node_ids: list[int]
    coords: np.ndarray  # (n, 3)
    M: np.ndarray  # (3n, 3n)
    K: np.ndarray  # (3n, 3n)
    lines: list[tuple[int, int]]  # node-id pairs, for display only
    base_nodes: dict[int, np.ndarray]  # table attachment points (id -> xyz), display only
    zeta_rigid: float = 0.04
    zeta_elastic: float = 0.02
    rigid_cutoff_hz: float = 200.0


@dataclass
class Modes:
    fn: np.ndarray  # (m,) Hz
    zeta: np.ndarray  # (m,)
    phi: np.ndarray  # (3n, m) mass-normalised
    participation: np.ndarray  # (m,) phi^T M r for the excitation axis


def _bar(K: np.ndarray, i: int, j: int, xi: np.ndarray, xj: np.ndarray, k: float) -> None:
    """Add an axial spring between nodes i and j (rotation-invariant)."""
    u = (xj - xi) / np.linalg.norm(xj - xi)
    ke = k * np.outer(u, u)
    _assemble_pair(K, i, j, ke)


def _bushing(K: np.ndarray, i: int, j: int, kxyz: tuple[float, float, float]) -> None:
    """Add three axis-aligned springs between nodes i and j."""
    _assemble_pair(K, i, j, np.diag(kxyz))


def _assemble_pair(K: np.ndarray, i: int, j: int, ke: np.ndarray) -> None:
    a, b = slice(3 * i, 3 * i + 3), slice(3 * j, 3 * j + 3)
    K[a, a] += ke
    K[b, b] += ke
    K[a, b] -= ke
    K[b, a] -= ke


def build_box_model() -> Model:
    """Build the default 9-node box-on-isolators model."""
    lx, ly, lz = 0.30, 0.20, 0.15
    corners = [(0, 0, 0), (lx, 0, 0), (lx, ly, 0), (0, ly, 0)]
    coords = np.array(corners + [(x, y, lz) for x, y, _ in corners] + [(lx / 2, ly / 2, lz)], dtype=float)
    node_ids = list(range(1, 10))
    n = len(node_ids)

    masses = np.full(n, 0.35)
    masses[6] += 0.80  # node 7: heavy component on one top corner -> CG offset
    masses[8] = 0.20  # node 9: panel centre
    M = np.diag(np.repeat(masses, 3))

    K = np.zeros((3 * n, 3 * n))
    k_bar = 1.0e7
    edges = [(1, 2), (2, 3), (3, 4), (4, 1), (5, 6), (6, 7), (7, 8), (8, 5), (1, 5), (2, 6), (3, 7), (4, 8)]
    diagonals = [(1, 3), (5, 7), (1, 6), (2, 7), (3, 8), (4, 5)]  # one per face
    for a, b in edges + diagonals:
        _bar(K, a - 1, b - 1, coords[a - 1], coords[b - 1], k_bar)

    # Isolators: grounded to the table, so they act on motion relative to the base.
    k_iso = (5.0e4, 5.0e4, 1.2e5)
    for i in range(4):
        K[3 * i : 3 * i + 3, 3 * i : 3 * i + 3] += np.diag(k_iso)

    # Panel centre: stiff in-plane, soft out-of-plane.
    for c in (5, 6, 7, 8):
        _bushing(K, 8, c - 1, (2.0e6, 2.0e6, 1.5e5))

    iso_h = 0.03
    base_nodes = {101 + i: coords[i] - np.array([0, 0, iso_h]) for i in range(4)}
    lines = edges + [(5, 9), (6, 9), (7, 9), (8, 9)] + [(101 + i, 1 + i) for i in range(4)]
    lines += [(101, 102), (102, 103), (103, 104), (104, 101)]
    return Model(node_ids, coords, M, K, lines, base_nodes)


def influence_vector(n_nodes: int, axis: np.ndarray) -> np.ndarray:
    """r: rigid-body unit translation of every node along ``axis``."""
    return np.tile(axis, n_nodes)


def solve_modes(model: Model, axis: np.ndarray) -> Modes:
    """Undamped eigen-solution with modal damping assigned by frequency band."""
    w2, phi = scipy.linalg.eigh(model.K, model.M)  # phi is mass-normalised
    w2 = np.clip(w2, 0.0, None)
    fn = np.sqrt(w2) / (2 * np.pi)
    zeta = np.where(fn < model.rigid_cutoff_hz, model.zeta_rigid, model.zeta_elastic)
    r = influence_vector(len(model.node_ids), axis)
    gamma = phi.T @ model.M @ r
    return Modes(fn, zeta, phi, gamma)


def dof_transmissibility(modes: Modes, r: np.ndarray, f: np.ndarray) -> np.ndarray:
    """Absolute-acceleration transmissibility of every DOF, shape (3n, nf). Dimensionless."""
    w = 2 * np.pi * np.asarray(f, dtype=float)
    wn = 2 * np.pi * modes.fn
    T = np.tile(r[:, None], (1, w.size)).astype(complex)
    # Loop over modes to keep memory at (3n, nf) rather than (3n, m, nf).
    for k in range(wn.size):
        h = w**2 / (wn[k] ** 2 - w**2 + 2j * modes.zeta[k] * wn[k] * w)
        T += np.outer(modes.phi[:, k] * modes.participation[k], h)
    return T


def navmat_asd(f: np.ndarray) -> np.ndarray:
    """NAVMAT P-9492 style random profile, g^2/Hz (6.06 grms over 20-2000 Hz).

    20-80 Hz: +3 dB/oct up to 0.04; 80-350 Hz: flat 0.04; 350-2000 Hz: -3 dB/oct.
    Deliberately non-flat so the test can show that transmissibility removes it.
    """
    f = np.asarray(f, dtype=float)
    asd = np.zeros_like(f)
    lo = (f >= 20) & (f < 80)
    mid = (f >= 80) & (f <= 350)
    hi = (f > 350) & (f <= 2000)
    asd[lo] = 0.04 * (f[lo] / 80.0)
    asd[mid] = 0.04
    asd[hi] = 0.04 * (350.0 / f[hi])
    return asd


def simulate(
    model: Model,
    axis_name: str = "Z",
    fs: float = 5120.0,
    duration: float = 60.0,
    noise_asd: float = 1e-6,
    seed: int = 1,
) -> dict:
    """Simulate one shaker run. Returns time data in g plus ground truth.

    Responses are generated by multiplying the base-accel spectrum by T(f) on a single
    full-length FFT, i.e. periodic steady state (no start-up transient). Sensor noise is
    white with one-sided ASD ``noise_asd`` (g^2/Hz) on every channel incl. the control.
    """
    rng = np.random.default_rng(seed)
    axis = AXES[axis_name]
    n_samples = int(round(fs * duration))
    n_samples += n_samples % 2
    f = np.fft.rfftfreq(n_samples, 1 / fs)

    # Complex Gaussian bins with E|X_k|^2 = S_k * fs * N / 2 give a one-sided ASD S_k.
    scale = np.sqrt(navmat_asd(f) * fs * n_samples / 4.0)
    Xb = scale * (rng.standard_normal(f.size) + 1j * rng.standard_normal(f.size))
    Xb[0] = 0.0
    Xb[-1] = Xb[-1].real
    base = np.fft.irfft(Xb, n=n_samples)

    modes = solve_modes(model, axis)
    r = influence_vector(len(model.node_ids), axis)
    T = dof_transmissibility(modes, r, f)
    dof_acc = np.fft.irfft(T * Xb[None, :], n=n_samples, axis=1)  # (3n, N) in g

    # Triaxial accelerometer at every structural node, aligned with global axes.
    channels: list[dict] = [{"channel": "CTRL", "node": 100, "direction": f"+{axis_name}", "role": "control"}]
    responses = []
    for i, nid in enumerate(model.node_ids):
        for j, ax in enumerate("XYZ"):
            channels.append({"channel": f"N{nid}{ax}", "node": nid, "direction": f"+{ax}", "role": "response"})
            responses.append(dof_acc[3 * i + j])
    noise_std = np.sqrt(noise_asd * fs / 2.0)
    data = np.vstack([base] + responses)
    data += noise_std * rng.standard_normal(data.shape)

    return {
        "fs": fs,
        "axis": axis_name,
        "data": data.T.astype(np.float32),  # (N, nch)
        "channels": channels,
        "modes": modes,
        "grms_input": float(np.std(base)),
    }


def write_test(out_dir: Path, model: Model, sim: dict, fmt: str = "npz") -> None:
    """Write files in the same layout the pipeline expects for a real test.

    ``fmt='csv'`` writes ``time.csv`` (a ``time`` column + one column per channel) as a
    worked example of the CSV input path; it is ~10x larger than the NPZ.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    names = [c["channel"] for c in sim["channels"]]
    if fmt == "csv":
        time_file = "time.csv"
        t = np.arange(sim["data"].shape[0]) / sim["fs"]
        np.savetxt(
            out_dir / time_file,
            np.column_stack([t, sim["data"]]),
            delimiter=",",
            header=",".join(["time"] + names),
            comments="",
            fmt=["%.7f"] + ["%.6g"] * len(names),
        )
    elif fmt == "npz":
        time_file = "time.npz"
        np.savez_compressed(out_dir / time_file, data=sim["data"], fs=sim["fs"], channels=np.array(names))
    elif fmt == "mat":
        import scipy.io

        time_file = "time.mat"
        chans = np.empty((len(names), 1), dtype=object)  # saved as a MATLAB cell array
        chans[:, 0] = names
        scipy.io.savemat(
            out_dir / time_file, {"data": sim["data"].astype(float), "channels": chans, "fs": sim["fs"]},
            do_compression=True,
        )
    else:
        raise ValueError(f"fmt must be 'npz', 'mat' or 'csv', got {fmt!r}")

    with open(out_dir / "test.json", "w") as fh:
        json.dump({"fs": sim["fs"], "units": "g", "excitation_axis": sim["axis"], "time_file": time_file}, fh, indent=2)

    table_centre = np.mean(list(model.base_nodes.values()), axis=0)
    with open(out_dir / "geometry.csv", "w") as fh:
        fh.write("node,x,y,z,base\n")
        for nid, xyz in zip(model.node_ids, model.coords):
            fh.write(f"{nid},{xyz[0]:.4f},{xyz[1]:.4f},{xyz[2]:.4f},0\n")
        for nid, xyz in model.base_nodes.items():
            fh.write(f"{nid},{xyz[0]:.4f},{xyz[1]:.4f},{xyz[2]:.4f},1\n")
        fh.write(f"100,{table_centre[0]:.4f},{table_centre[1]:.4f},{table_centre[2]:.4f},1\n")

    with open(out_dir / "channels.csv", "w") as fh:
        fh.write("channel,node,direction,role\n")
        for c in sim["channels"]:
            fh.write(f"{c['channel']},{c['node']},{c['direction']},{c['role']}\n")

    with open(out_dir / "lines.csv", "w") as fh:
        fh.write("node_a,node_b\n")
        for a, b in model.lines:
            fh.write(f"{a},{b}\n")

    m = sim["modes"]
    np.savez(
        out_dir / "truth.npz",
        fn=m.fn,
        zeta=m.zeta,
        phi=m.phi,
        participation=m.participation,
        node_ids=np.array(model.node_ids),
    )
