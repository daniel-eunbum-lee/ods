"""Bad time data or settings must stop with a clear message, not give silent or cryptic results."""

from __future__ import annotations

import dataclasses
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from ods.io import load_test
from ods.pipeline import run
from ods.synth import build_box_model, simulate, write_test


@pytest.fixture(scope="module")
def good(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("validation") / "good"
    model = build_box_model()
    write_test(d, model, simulate(model, "Z", fs=1024.0, duration=4.0, seed=5), fmt="npz")
    return d


def _variant(good: Path, tmp_path: Path, edit_npz=None, **meta) -> Path:
    d = tmp_path / "t"
    shutil.copytree(good, d)
    if edit_npz is not None:
        z = dict(np.load(d / "time.npz"))
        edit_npz(z)
        np.savez(d / "time.npz", **z)
    m = json.loads((d / "test.json").read_text(encoding="utf-8"))
    m.update(meta)
    (d / "test.json").write_text(json.dumps(m), encoding="utf-8")
    return d


def test_the_unedited_folder_loads(good, tmp_path):
    load_test(_variant(good, tmp_path))


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_non_finite_samples_are_rejected_and_the_channel_is_named(good, tmp_path, bad):
    def edit(z):
        z["data"][100, 3] = bad

    name = str(np.load(good / "time.npz")["channels"][3])
    with pytest.raises(ValueError, match="NaN or infinite") as e:
        load_test(_variant(good, tmp_path, edit))
    assert name in str(e.value)


def test_fewer_channel_names_than_data_columns_is_rejected(good, tmp_path):
    def edit(z):
        z["channels"] = z["channels"][:-1]

    with pytest.raises(ValueError, match="channel names but data has shape"):
        load_test(_variant(good, tmp_path, edit))


@pytest.mark.parametrize("fs", [0, -5, "fast", float("nan")])
def test_bad_sample_rate_is_rejected(good, tmp_path, fs):
    # json.dumps writes NaN as the bare token NaN, which json.loads reads back as nan
    with pytest.raises(ValueError, match="fs"):
        load_test(_variant(good, tmp_path, fs=fs))


def test_missing_test_folder_is_a_file_not_found_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="Test folder not found"):
        load_test(tmp_path / "nope")


def test_constant_control_channel_is_rejected(good):
    test = load_test(good)
    data = test.data.copy()
    data[:, test.control] = 0.0
    with pytest.raises(ValueError, match="Control channel .* constant"):
        run(dataclasses.replace(test, data=data), df=4.0)


@pytest.mark.parametrize("df", [0.0, -1.0, float("nan")])
def test_bad_resolution_is_rejected(good, df):
    with pytest.raises(ValueError, match="df must be a positive"):
        run(load_test(good), df=df)


def test_record_with_no_samples_is_rejected(good, tmp_path):
    def edit(z):
        z["data"] = z["data"][:0]

    with pytest.raises(ValueError, match="N >= 1 samples"):
        load_test(_variant(good, tmp_path, edit))
