"""Load a shaker test: time histories + geometry.

Expected directory layout (the synthetic generator writes the same thing)::

    test.json      {"fs": 5120, "units": "g", "excitation_axis": "Z", "time_file": "time.npz"}
    time.npz       data (N, nch), channels (nch,)      -- or --
    time.csv       header = channel names; optional first column "time" (s)
    geometry.csv   node,x,y,z[,base]                    (base=1: shaker table / fixture point)
    channels.csv   channel,node,direction,role          (direction "+X"/"-Z" or "dx dy dz";
                                                         role "control" or "response")
    lines.csv      node_a,node_b                        (optional, display wireframe)

All channels must come from one synchronised recording (one test axis).
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_AXIS = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}


@dataclass
class TestData:
    fs: float
    units: str
    excitation_axis: np.ndarray  # (3,) unit vector
    data: np.ndarray  # (N, nch)
    channel_names: list[str]
    channel_nodes: np.ndarray  # (nch,) node id per channel
    channel_dirs: np.ndarray  # (nch, 3) unit vectors, global axes
    control: int  # column index of the control accelerometer
    node_ids: np.ndarray  # (nn,)
    node_xyz: np.ndarray  # (nn, 3)
    node_is_base: np.ndarray  # (nn,) bool
    lines: list[tuple[int, int]] = field(default_factory=list)

    @property
    def responses(self) -> np.ndarray:
        """Column indices of response channels (everything except the control)."""
        return np.array([i for i in range(len(self.channel_names)) if i != self.control])


def parse_direction(text: str) -> np.ndarray:
    """'+X', '-z', 'Y' or 'dx dy dz' -> unit vector."""
    s = text.strip().upper()
    if s.lstrip("+-") in _AXIS:
        sign = -1.0 if s.startswith("-") else 1.0
        return sign * np.array(_AXIS[s.lstrip("+-")])
    v = np.array([float(p) for p in s.replace(",", " ").split()])
    if v.shape != (3,) or not np.linalg.norm(v) > 0:
        raise ValueError(f"Bad direction {text!r}: use +X/-Y/Z or three components")
    return v / np.linalg.norm(v)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="") as fh:
        return [{k.strip().lower(): v.strip() for k, v in row.items()} for row in csv.DictReader(fh)]


def _load_time(path: Path, fs_meta: float | None) -> tuple[np.ndarray, list[str], float]:
    if path.suffix.lower() == ".npz":
        with np.load(path) as z:
            data = np.asarray(z["data"], dtype=float)
            names = [str(c) for c in z["channels"]]
            fs = float(z["fs"]) if "fs" in z else fs_meta
    else:
        with open(path, newline="") as fh:
            names = [h.strip() for h in next(csv.reader(fh))]
        data = np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2)
        fs = fs_meta
        if names[0].lower() == "time":
            dt = np.median(np.diff(data[:, 0]))
            fs = fs or 1.0 / dt
            data, names = data[:, 1:], names[1:]
    if fs is None:
        raise ValueError("Sample rate unknown: put 'fs' in test.json or a 'time' column in the CSV")
    return data, names, fs


def load_test(test_dir: str | Path) -> TestData:
    test_dir = Path(test_dir)
    meta = json.loads((test_dir / "test.json").read_text()) if (test_dir / "test.json").exists() else {}
    time_file = test_dir / meta.get("time_file", "time.npz" if (test_dir / "time.npz").exists() else "time.csv")
    data, names, fs = _load_time(time_file, meta.get("fs"))

    geo = _read_csv(test_dir / "geometry.csv")
    node_ids = np.array([int(r["node"]) for r in geo])
    node_xyz = np.array([[float(r["x"]), float(r["y"]), float(r["z"])] for r in geo])
    node_is_base = np.array([r.get("base", "0") in ("1", "true", "yes") for r in geo])

    chan_rows = {r["channel"]: r for r in _read_csv(test_dir / "channels.csv")}
    missing = [n for n in names if n not in chan_rows]
    if missing:
        raise ValueError(f"Channels in time data but not in channels.csv: {missing}")
    unknown_nodes = {int(r["node"]) for r in chan_rows.values()} - set(node_ids.tolist())
    if unknown_nodes:
        raise ValueError(f"channels.csv references nodes missing from geometry.csv: {sorted(unknown_nodes)}")

    channel_nodes = np.array([int(chan_rows[n]["node"]) for n in names])
    channel_dirs = np.array([parse_direction(chan_rows[n]["direction"]) for n in names])
    controls = [i for i, n in enumerate(names) if chan_rows[n].get("role", "response").lower() == "control"]
    if len(controls) != 1:
        raise ValueError(f"Need exactly one channel with role=control, found {len(controls)}")

    lines: list[tuple[int, int]] = []
    if (test_dir / "lines.csv").exists():
        lines = [(int(r["node_a"]), int(r["node_b"])) for r in _read_csv(test_dir / "lines.csv")]

    axis_name = str(meta.get("excitation_axis", "")).upper()
    excitation = np.array(_AXIS[axis_name]) if axis_name in _AXIS else channel_dirs[controls[0]]

    return TestData(
        fs=fs,
        units=meta.get("units", "g"),
        excitation_axis=excitation,
        data=data,
        channel_names=names,
        channel_nodes=channel_nodes,
        channel_dirs=channel_dirs,
        control=controls[0],
        node_ids=node_ids,
        node_xyz=node_xyz,
        node_is_base=node_is_base,
        lines=lines,
    )
