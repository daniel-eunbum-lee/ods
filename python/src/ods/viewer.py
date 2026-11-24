"""Build the standalone HTML ODS viewer (no external scripts; data embedded as JSON)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import G0
from .pipeline import Results
from .shapes import node_projectors

_TEMPLATE = Path(__file__).with_name("viewer_template.html")


def _rounded(a: np.ndarray, sig: int = 5) -> list[float]:
    """Round to ``sig`` significant figures to keep the embedded JSON small."""
    return [float(f"{v:.{sig}g}") for v in np.asarray(a, dtype=float)]


def _finite(obj):
    """Replace NaN/inf with 0 throughout: JSON has no NaN, and one would blank the whole viewer.

    The MATLAB builder writes 0 for non-finite numbers too.
    """
    if isinstance(obj, float):
        return obj if np.isfinite(obj) else 0.0
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_finite(v) for v in obj]
    return obj


def embed_json(data: dict) -> str:
    """JSON that is safe inside <script type="application/json">.

    Escaping every < (not only </) also stops "<!--<script" in a channel name from switching the
    HTML parser into a state where the page's own </script> no longer ends the data block.
    \\u003c etc. are ordinary JSON escapes, so JSON.parse returns the original text.
    """
    text = json.dumps(_finite(data), separators=(",", ":"), allow_nan=False)
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def build_viewer(res: Results, out_path: Path, title: str = "Shaker test") -> Path:
    t, sp = res.test, res.spectra
    keep = (sp.f >= res.band[0] * 0.8) & (sp.f <= res.band[1])
    idx_map = -np.ones(sp.f.size, dtype=int)
    idx_map[keep] = np.arange(int(keep.sum()))

    proj = node_projectors(t.node_ids, t.channel_nodes, t.channel_dirs, t.responses)
    data = {
        "meta": {
            "title": title,
            "fs": t.fs,
            "df": float(sp.f[1] - sp.f[0]),
            "n_avg": sp.n_avg,
            "units": t.units,
            "to_si": G0 if t.units.lower() == "g" else 1.0,
            "excitation": t.excitation_axis.tolist(),
            "band": list(res.band),
            "control": int(t.control),
            # The control reads g = d_ctrl . e of the table, so its rms is |g| x the table rms. run()
            # rejects |g| < 0.5; the guard only protects hand-built results from dividing by ~0.
            "grms": float(np.std(t.data[:, t.control]) / max(abs(t.channel_dirs[t.control] @ t.excitation_axis), 0.5)),
        },
        "f": _rounded(sp.f[keep], 7),
        "ch": [
            {"name": n, "node": int(nd), "dir": [round(float(v), 6) for v in d]}
            for n, nd, d in zip(t.channel_names, t.channel_nodes, t.channel_dirs)
        ],
        "Tre": [_rounded(sp.T[keep, c].real) for c in range(sp.T.shape[1])],
        "Tim": [_rounded(sp.T[keep, c].imag) for c in range(sp.T.shape[1])],
        "coh": [_rounded(sp.coh[keep, c], 4) for c in range(sp.T.shape[1])],
        "nodes": [
            {"id": int(i), "x": float(x), "y": float(y), "z": float(z), "base": bool(b)}
            for i, (x, y, z), b in zip(t.node_ids, t.node_xyz, t.node_is_base)
        ],
        "lines": [[int(a), int(b)] for a, b in t.lines],
        "resp": t.responses.tolist(),
        "rigidR": np.round(res.rigid_R, 8).tolist(),
        "proj": {str(nid): {"idx": idx.tolist(), "P": np.round(P, 8).tolist()} for nid, (idx, P) in proj.items()},
        "peaks": [
            {"i": int(idx_map[p.index]), "f": p.f, "db": p.indicator_db, "coh": p.coh}
            for p in res.peaks
            if idx_map[p.index] >= 0
        ],
    }
    # read_text turns any CRLF into LF and newline="\n" keeps it that way on Windows: the page's
    # Content-Security-Policy allows its script by a hash of the exact (LF) script text.
    html = _TEMPLATE.read_text(encoding="utf-8").replace("/*__ODS_DATA__*/", embed_json(data))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8", newline="\n")
    return out_path
