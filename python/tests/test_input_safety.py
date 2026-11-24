"""Untrusted input and safe output.

A test folder may come from someone else (a customer, another lab), so test.json and the data
files are treated as untrusted. The CSV outputs are opened in spreadsheets and the viewer in a
browser, so text from the input (channel names, units, title) must not act as formulas, markup
or script there.
"""

from __future__ import annotations

import base64
import csv
import dataclasses
import hashlib
import io
import json
import re
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pytest
import scipy.io

import ods.io
from ods.io import load_test
from ods.pipeline import csv_cell, export, run
from ods.synth import build_box_model, simulate, write_test
from ods.viewer import build_viewer

TEMPLATE = Path(ods.io.__file__).with_name("viewer_template.html")


@pytest.fixture(scope="module")
def folders(tmp_path_factory):
    """The same small synthetic test written as .npz, .mat and .csv."""
    d = tmp_path_factory.mktemp("safety")
    model = build_box_model()
    sim = simulate(model, "Z", fs=1024.0, duration=4.0, seed=5)
    for fmt in ("npz", "mat", "csv"):
        write_test(d / fmt, model, sim, fmt=fmt)
    return d


@pytest.fixture(scope="module")
def results(folders):
    return run(load_test(folders / "npz"), df=4.0, band=(20.0, 400.0))


def _copy_with_meta(src: Path, dst: Path, **meta) -> Path:
    shutil.copytree(src, dst)
    m = json.loads((dst / "test.json").read_text(encoding="utf-8"))
    m.update(meta)
    (dst / "test.json").write_text(json.dumps(m), encoding="utf-8")
    return dst


# ---------------------------------------------------------------- time_file must stay in the folder


@pytest.mark.parametrize(
    "name",
    [
        "//evil.example/share/time.npz",  # UNC: Windows would connect and send the login hash
        r"\\evil.example\share\time.npz",
        "C:/data/time.npz",
        "C:time.npz",  # drive-relative
        "/tmp/time.npz",
        "../npz/time.npz",  # a real, valid file, but outside this folder
        r"sub\..\..\npz\time.npz",
        "secret.txt",  # unknown extensions were once read as CSV, echoing the first line in an error
        "NUL.npz",  # Windows devices, whatever the extension or folder
        "sub/con.csv",
        "COM1.mat",
        "CONIN$.csv",
        "COM¹.csv",
        "x/CON:.csv",
        "time",
        "",
        5,
        None,
    ],
)
def test_time_file_outside_the_test_folder_is_rejected(folders, tmp_path, name):
    d = _copy_with_meta(folders / "npz", tmp_path / "t", time_file=name)
    with pytest.raises(ValueError, match="time_file"):
        load_test(d)


def test_time_file_in_a_subfolder_is_accepted(folders, tmp_path):
    d = _copy_with_meta(folders / "npz", tmp_path / "t", time_file="raw/time.npz")
    (d / "raw").mkdir()
    (d / "time.npz").rename(d / "raw" / "time.npz")
    assert load_test(d).data.shape == load_test(folders / "npz").data.shape


def test_link_to_a_file_outside_the_test_folder_is_rejected(folders, tmp_path):
    d = tmp_path / "t"
    shutil.copytree(folders / "npz", d)
    (d / "geometry.csv").unlink()
    try:  # archives (tar) keep symbolic links; Windows needs developer mode to create one
        (d / "geometry.csv").symlink_to(folders / "npz" / "geometry.csv")
    except OSError:
        pytest.skip("cannot create symbolic links here")
    with pytest.raises(ValueError, match="outside the test folder"):
        load_test(d)


# ---------------------------------------------------------------- size limit and selective loading


@pytest.mark.parametrize("fmt", ["npz", "mat", "csv"])
def test_time_data_above_the_size_limit_is_refused_before_loading(folders, monkeypatch, fmt):
    load_test(folders / fmt)  # well under the default limit
    monkeypatch.setattr(ods.io, "MAX_TIME_DATA_BYTES", 1000)
    with pytest.raises(ValueError, match="limit"):
        load_test(folders / fmt)


def test_npz_member_named_data_counts_against_the_limit(folders, tmp_path, monkeypatch):
    """numpy reads a member called exactly "data" before "data.npy": a tiny data.npy must not hide it."""
    d = tmp_path / "t"
    shutil.copytree(folders / "npz", d)
    with np.load(d / "time.npz") as z:
        real, chans, fs = z["data"], z["channels"], z["fs"]
    with zipfile.ZipFile(d / "time.npz", "w", zipfile.ZIP_DEFLATED) as zf:
        for member, arr in [("data.npy", np.zeros((2, 2))), ("channels.npy", chans), ("fs.npy", fs), ("data", real)]:
            buf = io.BytesIO()
            np.lib.format.write_array(buf, arr)
            zf.writestr(member, buf.getvalue())
    monkeypatch.setattr(ods.io, "MAX_TIME_DATA_BYTES", real.nbytes // 2)
    with pytest.raises(ValueError, match="limit"):
        load_test(d)


def test_mat_with_a_second_data_variable_is_refused(folders, tmp_path):
    """loadmat reads the first "data"; a second, small one must not hide a huge first one."""
    d = tmp_path / "t"
    shutil.copytree(folders / "mat", d)
    extra = io.BytesIO()
    scipy.io.savemat(extra, {"data": np.zeros((1, 1))})
    with open(d / "time.mat", "ab") as fh:
        fh.write(extra.getvalue()[128:])  # one more variable element, without a second file header
    with pytest.raises(ValueError, match="more than one variable named data"):
        load_test(d)


def test_mat_data_in_a_cell_is_refused_before_loading(folders, tmp_path):
    """A cell's listed shape (1x1) says nothing about the array inside it, so it can't be size-checked."""
    d = tmp_path / "t"
    shutil.copytree(folders / "mat", d)
    z = scipy.io.loadmat(d / "time.mat")
    wrapped = np.empty((1, 1), dtype=object)
    wrapped[0, 0] = z["data"]
    scipy.io.savemat(d / "time.mat", {"data": wrapped, "channels": z["channels"], "fs": z["fs"]})
    with pytest.raises(ValueError, match="'data' has class cell"):
        load_test(d)


def test_csv_size_estimate_is_close_to_the_real_size(folders):
    """The CSV limit uses an estimate (a text file cannot decompress); it must not refuse real files."""
    t = load_test(folders / "csv")
    actual = t.data.nbytes * (t.data.shape[1] + 1) / t.data.shape[1]  # plus the time column
    assert 0.8 < ods.io._csv_data_bytes(folders / "csv" / "time.csv") / actual < 1.25


def test_mat_loads_only_the_variables_it_uses(folders, tmp_path, monkeypatch):
    d = tmp_path / "t"
    shutil.copytree(folders / "mat", d)
    z = scipy.io.loadmat(d / "time.mat")
    z["other"] = np.ones((5, 5))  # anything else in the file is never read
    scipy.io.savemat(d / "time.mat", {k: v for k, v in z.items() if not k.startswith("__")})
    seen = {}
    real = scipy.io.loadmat

    def spy(path, **kw):
        seen.update(kw)
        return real(path, **kw)

    monkeypatch.setattr(scipy.io, "loadmat", spy)
    load_test(d)
    assert seen["variable_names"] == ["data", "channels", "fs"]


# ---------------------------------------------------------------- geometry


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_non_finite_coordinates_are_rejected(folders, tmp_path, value):
    d = tmp_path / "t"
    shutil.copytree(folders / "npz", d)
    lines = (d / "geometry.csv").read_text(encoding="utf-8").splitlines()
    node, _, y, z, base = lines[1].split(",")
    lines[1] = ",".join([node, value, y, z, base])
    (d / "geometry.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        load_test(d)


# ---------------------------------------------------------------- CSV output


@pytest.mark.parametrize(
    "text, expected",
    [
        ("A1", "A1"),
        ("=1+1", "'=1+1"),
        ("+X accel", "'+X accel"),
        ("-Z", "'-Z"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("\tx", "'\tx"),
        ("a,b", '"a,b"'),
        ('say "hi"', '"say ""hi"""'),
        ("=a,b", '"\'=a,b"'),
        ("line\nbreak", '"line\nbreak"'),
        ("가속도", "가속도"),
    ],
)
def test_csv_cell(text, expected):
    assert csv_cell(text) == expected


HOSTILE = ['=HYPERLINK("http://example.invalid","x")', "a,b", "가속도", "@cmd", 'q"uote']


def test_export_keeps_hostile_channel_names_in_their_own_cell(results, tmp_path):
    t = results.test
    names = list(t.channel_names)
    for i, c in enumerate(t.responses[: len(HOSTILE)]):
        names[c] = HOSTILE[i]
    res = dataclasses.replace(results, test=dataclasses.replace(t, channel_names=names, units="g,=x"))
    export(res, tmp_path)  # used to raise UnicodeEncodeError on the Korean name (latin-1 header)

    with open(tmp_path / "transmissibility.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))

    def as_read(field: str) -> str:  # what a CSV reader returns for the written field
        return next(csv.reader([csv_cell(field)]))[0]

    assert rows[0] == ["f_hz"] + [as_read(f"{n}_mag") for n in names] + [as_read(f"{n}_phase_deg") for n in names]
    assert all(len(r) == len(rows[0]) for r in rows)
    assert not any(cell and cell[0] in "=+-@" for cell in rows[0])

    with open(tmp_path / "ods_peaks.csv", newline="", encoding="utf-8") as fh:
        table = list(csv.reader(fh))
    assert all(len(r) == 17 for r in table)  # nothing shifted a column
    assert "disp_rel_mm_per_g,=x" in table[0]
    got = {r[3] for r in table[1:]}
    assert {"'" + HOSTILE[0], "a,b", "가속도", "'@cmd", 'q"uote'} <= got


# ---------------------------------------------------------------- HTML viewer


def _data_block(html: str) -> str:
    m = re.search(r'<script id="ods-data" type="application/json">(.*?)</script>', html, re.S)
    assert m, "data block not found"
    return m.group(1)


def test_viewer_embeds_hostile_text_and_non_finite_numbers_safely(results, tmp_path):
    t = results.test
    names = list(t.channel_names)
    hostile = ["<!--<script>", "</script><img src=x onerror=alert(1)>", "a&b>c"]
    for i, c in enumerate(t.responses[: len(hostile)]):
        names[c] = hostile[i]
    T = results.spectra.T.copy()
    T[10, t.responses[0]] = np.nan  # NaN is not JSON and used to blank the whole viewer
    res = dataclasses.replace(
        results,
        test=dataclasses.replace(t, channel_names=names),
        spectra=dataclasses.replace(results.spectra, T=T),
    )
    html = build_viewer(res, tmp_path / "v.html", title="<b>title</b>").read_text(encoding="utf-8")

    block = _data_block(html)
    assert not re.search(r"[<>&]", block)  # nothing the HTML parser could act on
    data = json.loads(block, parse_constant=lambda c: pytest.fail(f"non-JSON constant {c}"))
    assert [ch["name"] for ch in data["ch"]] == names  # JSON.parse gives back the original text
    assert data["meta"]["title"] == "<b>title</b>"
    assert html.count("</script>") == 2  # the data block and the main script, nothing injected


def _csp_hash_and_script(html: str) -> tuple[str, str]:
    m = re.search(r"script-src 'sha256-([A-Za-z0-9+/=]+)'", html)
    assert m, "no script hash in the Content-Security-Policy"
    script = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
    actual = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode()
    return m.group(1), actual


def test_viewer_csp_allows_only_its_own_script(results, tmp_path):
    """The CSP lets only the viewer's own script run. Its hash must match the script exactly,
    including LF line endings, or browsers block the viewer (a blank page)."""
    template = TEMPLATE.read_bytes()
    assert b"\r" not in template
    declared, actual = _csp_hash_and_script(template.decode("utf-8"))
    assert declared == actual, f"script changed: set script-src 'sha256-{actual}' in both viewer templates"

    out = build_viewer(results, tmp_path / "v.html").read_bytes()
    assert b"\r" not in out  # Windows text mode would write CRLF and break the hash
    declared, actual = _csp_hash_and_script(out.decode("utf-8"))
    assert declared == actual
    assert "default-src 'none'" in out.decode("utf-8")
