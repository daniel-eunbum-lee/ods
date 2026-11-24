"""Welch spectra, H1 transmissibility and coherence against the control accelerometer."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.signal


@dataclass
class Spectra:
    f: np.ndarray  # (nf,) Hz
    T: np.ndarray  # (nf, nch) complex H1 transmissibility, response / control
    coh: np.ndarray  # (nf, nch) ordinary coherence with the control channel
    Gbb: np.ndarray  # (nf,) control ASD, units^2/Hz
    Gxx: np.ndarray  # (nf, nch) response ASDs, units^2/Hz
    nfft: int
    n_avg: int


def nfft_for_resolution(fs: float, df: float) -> int:
    """Smallest power of two giving a bin spacing <= df."""
    return int(2 ** np.ceil(np.log2(fs / df)))


def compute_spectra(data: np.ndarray, control: int, fs: float, nfft: int, overlap: float = 0.5) -> Spectra:
    """H1 = G_bx / G_bb with a Hann window.

    H1 is unbiased by noise on the response channels (it averages out of G_bx) but
    biased low by noise on the control channel; with a clean control accel that bias
    is negligible. Coherence flags bins where either noise or nonlinearity matters.
    """
    if not 0 <= overlap < 1:
        raise ValueError("overlap must be in [0, 1)")
    n = data.shape[0]
    if n < nfft:
        raise ValueError(f"Record ({n} samples) shorter than nfft ({nfft}); lower the resolution")
    x = np.asarray(data, dtype=float).T  # (nch, N)
    b = x[control][None, :]
    kw = dict(fs=fs, window="hann", nperseg=nfft, noverlap=int(nfft * overlap), detrend="constant", axis=-1)

    # scipy's csd(x, y) = E[conj(X) Y], so csd(b, x) is G_bx as needed for H1.
    f, Gbx = scipy.signal.csd(b, x, **kw)  # broadcasts b against every channel
    _, Gxx = scipy.signal.welch(x, **kw)
    Gbb = Gxx[control]

    with np.errstate(divide="ignore", invalid="ignore"):
        T = Gbx / Gbb
        coh = np.abs(Gbx) ** 2 / (Gbb * Gxx)
    T = np.nan_to_num(T)
    coh = np.clip(np.nan_to_num(coh), 0.0, 1.0)

    step = nfft - int(nfft * overlap)
    n_avg = 1 + (n - nfft) // step
    return Spectra(f=f, T=T.T, coh=coh.T, Gbb=Gbb, Gxx=Gxx.T, nfft=nfft, n_avg=n_avg)
