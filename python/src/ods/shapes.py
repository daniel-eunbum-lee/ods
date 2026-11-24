"""Turn transmissibilities into operating deflection shapes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.signal

from . import G0


@dataclass
class Peak:
    index: int  # frequency bin
    f: float  # Hz
    indicator_db: float  # channel-norm of absolute transmissibility, dB
    coh: float  # |T|^2-weighted mean coherence over response channels at this bin
    mpc: float  # modal phase collinearity of the absolute shape, 1 = real (standing)


def relative_transmissibility(T: np.ndarray, dirs: np.ndarray, excitation: np.ndarray) -> np.ndarray:
    """Remove the rigid table motion: T_rel = T - d.e per channel.

    A sensor along the excitation axis sees the table motion at T = 1, so T - 1 is the
    motion relative to the fixture. A cross-axis sensor (d.e = 0) has nothing to
    subtract; a skewed sensor subtracts its projection. ``T`` is (nf, nch).
    """
    return T - (dirs @ excitation)[None, :]


def accel_to_displacement(A: np.ndarray, f: np.ndarray, units: str = "g") -> np.ndarray:
    """Acceleration (per unit input) -> displacement in mm (per unit input).

    In the frequency domain x = a / (-w^2). The DC bin is set to 0 rather than inf.
    For ``units='g'`` the acceleration is first converted to m/s^2.
    """
    to_si = G0 if units.lower() == "g" else 1.0
    w2 = (2 * np.pi * np.asarray(f, dtype=float)) ** 2
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.where(w2 > 0, -to_si * 1e3 / w2, 0.0)
    return A * (scale[:, None] if A.ndim == 2 else scale)


def mpc(shape: np.ndarray) -> float:
    """Modal phase collinearity (Pappa et al.), 0..1.

    Eigenvalues of the 2x2 covariance of (Re, Im) parts: if all points lie on one line
    through the origin of the complex plane the shape is a standing (real) wave and
    MPC = 1. The vectors are deliberately not mean-centred: a line through the origin is
    what makes a standing wave. Low MPC means a travelling-wave look, from closely
    spaced modes or non-proportional damping.
    """
    z = np.asarray(shape, dtype=complex)
    re, im = z.real, z.imag
    cov = np.array([[re @ re, re @ im], [re @ im, im @ im]])
    lam = np.linalg.eigvalsh(cov)
    total = lam.sum()
    return float(((lam[1] - lam[0]) / total) ** 2) if total > 0 else 1.0


def mac(a: np.ndarray, b: np.ndarray) -> float:
    """Modal assurance criterion between two (possibly complex) shape vectors."""
    a = np.asarray(a, dtype=complex)
    b = np.asarray(b, dtype=complex)
    return float(np.abs(np.vdot(a, b)) ** 2 / (np.vdot(a, a).real * np.vdot(b, b).real))


def find_peaks(
    f: np.ndarray,
    T: np.ndarray,
    coh: np.ndarray,
    band: tuple[float, float],
    prominence_db: float = 3.0,
    min_coh: float = 0.5,
    min_spacing_hz: float = 3.0,
) -> list[Peak]:
    """Pick ODS frequencies from the channel-norm of the *absolute* transmissibility.

    The norm across channels is the single-reference analogue of a CMIF: a peak in it
    means some part of the unit is resonating. Absolute T is used deliberately: above
    an isolation frequency the unit is nearly still, so T - 1 sits at a flat ~-1 floor
    (the table moving underneath) that buries elastic resonances.

    The coherence gate is weighted by |T|^2, i.e. it asks "are the channels that carry
    this shape trustworthy?"; a plain mean is dragged down by quiet, noise-floor channels.
    """
    power = np.abs(T) ** 2
    indicator = np.sqrt(power.sum(axis=1))
    ind_db = 20 * np.log10(np.maximum(indicator, 1e-12))
    in_band = (f >= band[0]) & (f <= band[1])
    df = f[1] - f[0]
    # Search the whole curve and keep in-band peaks afterwards. Masking out-of-band bins to
    # -inf instead would turn a band edge on a falling/rising slope into a fake local maximum
    # with infinite prominence. floor(x + 0.5) (round half up) matches MATLAB's round().
    idx, _ = scipy.signal.find_peaks(
        ind_db,
        prominence=prominence_db,
        distance=max(1, int(np.floor(min_spacing_hz / df + 0.5))),
    )
    w_coh = (power * coh).sum(axis=1) / np.maximum(power.sum(axis=1), 1e-30)
    peaks = []
    for k in idx:
        if in_band[k] and w_coh[k] >= min_coh:
            peaks.append(Peak(int(k), float(f[k]), float(ind_db[k]), float(w_coh[k]), mpc(T[k])))
    return peaks


def rigid_body_projector(positions: np.ndarray, dirs: np.ndarray) -> np.ndarray:
    """Matrix R (k x k) that removes least-squares 6-DOF rigid-body motion from k channels.

    A rigid motion (translation t, small rotation theta) is read by a sensor at p with
    direction d as d.t + d.(theta x p) = d.t + theta.(p x d). Stacking those rows gives
    A (k x 6); R = I - A A^+ leaves only the elastic (deforming) part. Positions are taken
    about their centroid for conditioning. Needs >= 6 well-spread channels to remove all
    six rigid-body DOFs; with fewer, the pseudo-inverse removes what is observable.
    """
    p = positions - positions.mean(axis=0)
    A = np.hstack([dirs, np.cross(p, dirs)])
    return np.eye(len(dirs)) - A @ np.linalg.pinv(A, rcond=1e-8)


def node_projectors(
    node_ids: np.ndarray, channel_nodes: np.ndarray, channel_dirs: np.ndarray, channels: np.ndarray
) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Per node: (channel indices, 3 x k pseudo-inverse) mapping sensor values to an xyz vector.

    Each sensor reads d . u, so for k sensors at a node D u = s with D (k x 3). The
    pseudo-inverse gives the least-squares u for k >= 3 non-coplanar directions and the
    minimum-norm u otherwise, i.e. unmeasured directions come out as zero motion.
    """
    out: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for nid in node_ids:
        idx = np.array([c for c in channels if channel_nodes[c] == nid], dtype=int)
        if idx.size:
            out[int(nid)] = (idx, np.linalg.pinv(channel_dirs[idx], rcond=1e-6))
    return out


def node_shape(shape: np.ndarray, projectors: dict[int, tuple[np.ndarray, np.ndarray]]) -> dict[int, np.ndarray]:
    """Channel shape vector (nch,) -> complex xyz vector per measured node."""
    return {nid: P @ shape[idx] for nid, (idx, P) in projectors.items()}
