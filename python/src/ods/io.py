"""Load a shaker test: time histories + geometry.

Expected directory layout (the synthetic generator writes the same thing)::

    test.json      {"fs": 5120, "units": "g", "excitation_axis": "Z", "time_file": "time.npz"}
    time.npz       data (N, nch), channels (nch,)      -- or --
    time.mat       data (N, nch), channels (cellstr), fs   (MATLAB-friendly) -- or --
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
import math
import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

import numpy as np

_AXIS = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}
_TIME_SUFFIXES = (".npz", ".mat", ".csv")
# Opening these on Windows reaches a device, whatever the folder or extension (NUL.csv is NUL).
_WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    f"{p}{i}" for p in ("COM", "LPT") for i in [*range(1, 10), "¹", "²", "³"]
}
_MAT_NUMERIC = {"double", "single", "logical"} | {f"{s}int{b}" for s in ("", "u") for b in (8, 16, 32, 64)}
_MAT_TEXT = {"cell", "char"}

# Largest time-data array load_test accepts, as declared by the file (bytes, float64). A small
# crafted file can declare a huge array, or decompress to one (a .mat "zip bomb"); this refuses
# it up front. 8 GiB is ~1e9 samples, e.g. 64 channels x 5120 Hz x 54 min. Raise it if needed.
MAX_TIME_DATA_BYTES = 8 * 2**30


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
    """Rows as dicts with lower-cased keys. utf-8-sig drops the BOM Excel writes; short rows
    get "" for missing fields, extra fields are dropped, and blank rows are skipped."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = []
        for row in csv.DictReader(fh):
            clean = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k is not None}
            if any(clean.values()):
                rows.append(clean)
        return rows


def _mat_names(raw: np.ndarray) -> list[str]:
    """Channel names from a .mat file: a cell array (object array) or a char matrix."""
    if raw.dtype == object:
        return [str(np.squeeze(c)).strip() for c in raw.ravel()]
    return [str(r).strip() for r in np.atleast_1d(raw)]


def _time_file_path(test_dir: Path, name: object) -> Path:
    """test.json's time_file, which must be a relative path inside the test folder.

    test.json travels with the data, possibly from someone else. An absolute path, a UNC path
    (//host/share/x.csv, which makes Windows connect to that host and send the user's login
    hash) or a ".." step would otherwise read files outside the folder.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"time_file must be a file name, got {name!r}")
    parts = re.split(r"[\\/]", name)
    if PureWindowsPath(name).anchor or PurePosixPath(name).is_absolute() or ".." in parts:
        raise ValueError(f"time_file must be a relative path inside the test folder, got {name!r}")
    if any(re.split(r"[.:]", p)[0].strip().upper() in _WINDOWS_DEVICES for p in parts) or (
        os.name == "nt" and os.path.abspath(test_dir / name).startswith("\\\\.\\")  # Windows' own verdict
    ):
        raise ValueError(f"time_file must not name a Windows device (CON, NUL, COM1, ...), got {name!r}")
    if PurePosixPath(name.replace("\\", "/")).suffix.lower() not in _TIME_SUFFIXES:
        raise ValueError(f"time_file must end in {', '.join(_TIME_SUFFIXES)}, got {name!r}")
    return _in_folder(test_dir, name)


def _in_folder(test_dir: Path, name: str) -> Path:
    """test_dir / name, refusing a symbolic link that leads outside the folder (archives keep links)."""
    path = test_dir / name
    if not path.resolve().is_relative_to(test_dir.resolve()):
        raise ValueError(f"{name} is a link to a file outside the test folder")
    return path


def _check_size(nbytes: int, path: Path) -> None:
    if nbytes > MAX_TIME_DATA_BYTES:
        raise ValueError(
            f"{path.name}: time data would take {nbytes / 2**30:.3g} GiB, above the "
            f"{MAX_TIME_DATA_BYTES / 2**30:.3g} GiB limit (ods.io.MAX_TIME_DATA_BYTES)"
        )


def npz_bytes(path: Path, keys: tuple[str, ...], numeric: str | None = None) -> int:
    """Upper bound on the memory np.load(path)[key] takes for these keys, without loading them.

    Members are resolved as numpy does ("data" wins over "data.npy"). A member's uncompressed
    size from the zip directory is a hard bound on what is read, so a decompression bomb is
    caught; for the ``numeric`` key the .npy header's shape also counts, as float64 after conversion.
    """
    total = 0
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        for key in keys:
            member = key if key in names else f"{key}.npy" if f"{key}.npy" in names else None
            if member is None:
                continue
            nbytes = zf.getinfo(member).file_size
            if key == numeric:
                with zf.open(member) as fh:
                    try:
                        version = np.lib.format.read_magic(fh)
                        read = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
                        shape, _, _ = read(fh)
                        nbytes = max(nbytes, math.prod(shape) * 8)
                    except ValueError:
                        pass  # not a .npy member: np.load hands back raw bytes, bounded by file_size
            total += nbytes
    return total


def _csv_data_bytes(path: Path) -> int:
    """Estimated float64 size of a time CSV: rows (file size / median line length) x columns."""
    cap = 1 << 20  # a file with no line breaks must not be read whole just to estimate its size
    with open(path, "rb") as fh:
        header = fh.readline(cap)
        sample = [line for line in (fh.readline(cap) for _ in range(200)) if line.strip()]
    if not sample:
        return 0
    row_len = sorted(len(line) for line in sample)[len(sample) // 2]
    rows = (path.stat().st_size - len(header)) / row_len
    return int(rows * (header.count(b",") + 1) * 8)


def _load_time(path: Path, fs_meta: float | None) -> tuple[np.ndarray, list[str], float]:
    suffix = path.suffix.lower()
    if suffix == ".mat":
        import scipy.io

        wanted = ("data", "channels", "fs")
        listed = [(name, shape, cls) for name, shape, cls in scipy.io.whosmat(path) if name in wanted]
        names_seen = [name for name, _, _ in listed]
        dup = sorted({n for n in names_seen if names_seen.count(n) > 1})
        if dup:  # loadmat reads the first copy, so a second, small one could hide a huge first
            raise ValueError(f"{path.name} holds more than one variable named {', '.join(dup)}")
        for name, _, cls in listed:
            # A cell's listed shape says nothing about what it holds, so only plain numeric
            # data/fs count correctly. channels may be a cell: its strings are not bounded here
            # (they are small in any real file; MATLAB's whos does count them).
            if cls not in (_MAT_TEXT if name == "channels" else _MAT_NUMERIC):
                raise ValueError(f"{path.name}: variable {name!r} has class {cls}")
        _check_size(sum(math.prod(shape) * 8 for _, shape, _ in listed), path)
        z = scipy.io.loadmat(path, variable_names=list(wanted))
        data = np.asarray(z["data"], dtype=float)
        names = _mat_names(z["channels"])
        fs_file = float(np.squeeze(z["fs"])) if "fs" in z else None
    elif suffix == ".npz":
        _check_size(npz_bytes(path, ("data", "channels", "fs"), numeric="data"), path)
        with np.load(path) as z:
            data = np.asarray(z["data"], dtype=float)
            names = [str(c) for c in z["channels"]]
            fs_file = float(z["fs"]) if "fs" in z else None
    elif suffix == ".csv":
        _check_size(_csv_data_bytes(path), path)  # a text file cannot decompress: an estimate is enough
        with open(path, newline="", encoding="utf-8-sig") as fh:
            names = [h.strip() for h in next(csv.reader(fh))]
        data = np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2, encoding="utf-8-sig")
        fs_file = None
        if names[0].lower() == "time":
            t = data[:, 0]
            # Span over count, not 1/median(diff): printed times are rounded, so individual
            # steps are quantised and the median step can be off by one rounding unit.
            if len(t) > 1 and t[-1] > t[0]:
                fs_file = (len(t) - 1) / (t[-1] - t[0])
            data, names = data[:, 1:], names[1:]
    else:
        raise ValueError(f"Unsupported time file {path.name} (use .npz, .mat or .csv)")
    # test.json wins, so a user can correct a wrong rate without rewriting the time file.
    fs = fs_meta if fs_meta is not None else fs_file
    if fs is None:
        raise ValueError("Sample rate unknown: put 'fs' in test.json or a 'time' column in the CSV")
    return data, names, float(fs)


def load_test(test_dir: str | Path) -> TestData:
    test_dir = Path(test_dir)
    meta_path = _in_folder(test_dir, "test.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig")) if meta_path.exists() else {}
    default = next((n for n in ("time.npz", "time.mat", "time.csv") if (test_dir / n).exists()), "time.csv")
    time_file = _time_file_path(test_dir, meta["time_file"]) if "time_file" in meta else _in_folder(test_dir, default)
    data, names, fs = _load_time(time_file, meta.get("fs"))

    geo = _read_csv(_in_folder(test_dir, "geometry.csv"))
    node_ids = np.array([int(r["node"]) for r in geo])
    node_xyz = np.array([[float(r["x"]), float(r["y"]), float(r["z"])] for r in geo])
    node_is_base = np.array([r.get("base", "0").lower() in ("1", "true", "yes") for r in geo])
    bad = node_ids[~np.isfinite(node_xyz).all(axis=1)] if node_xyz.size else node_ids[:0]
    if bad.size:  # float() accepts "nan" and "inf"; such a node has no position to draw or fit
        raise ValueError(f"geometry.csv has non-finite coordinates for node(s) {bad.tolist()}")

    chan_rows: dict[str, dict[str, str]] = {}
    for r in _read_csv(_in_folder(test_dir, "channels.csv")):
        if r["channel"] in chan_rows:
            raise ValueError(f"Duplicate channel in channels.csv: {r['channel']!r}")
        chan_rows[r["channel"]] = r
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
        lines = [(int(r["node_a"]), int(r["node_b"])) for r in _read_csv(_in_folder(test_dir, "lines.csv"))]

    if meta.get("excitation_axis") is not None:  # JSON null means "not set"
        raw = meta["excitation_axis"]
        axis_name = raw.strip().upper() if isinstance(raw, str) else ""
        if not re.fullmatch(r"[+-]?[XYZ]", axis_name):
            # Silently falling back to the control's direction would hide a skewed control (#12).
            raise ValueError(f"excitation_axis must be X, Y or Z (optionally signed), got {meta['excitation_axis']!r}")
        excitation = parse_direction(axis_name)
    else:
        excitation = channel_dirs[controls[0]]

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
