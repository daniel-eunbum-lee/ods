"""The command line: ``ods synth`` and ``ods run``, called in-process and as ``python -m ods``."""

from __future__ import annotations

import subprocess
import sys

import pytest

from ods.__main__ import main


@pytest.fixture(scope="module")
def synth_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("cli") / "s"
    main(["synth", "--out", str(d), "--fs", "1024", "--duration", "8", "--seed", "3"])
    return d


def test_synth_writes_a_test_folder_and_lists_the_true_modes(tmp_path, capsys):
    out = tmp_path / "s"
    main(["synth", "--out", str(out), "--fs", "1024", "--duration", "4", "--format", "csv"])
    text = capsys.readouterr().out
    assert "True modes" in text
    assert {p.name for p in out.iterdir()} >= {"time.csv", "test.json", "geometry.csv", "channels.csv", "lines.csv", "truth.npz"}


def test_run_writes_outputs_and_compares_with_the_truth(synth_dir, tmp_path, capsys):
    out = tmp_path / "o"
    main(["run", str(synth_dir), "--out", str(out), "--df", "2", "--fmax", "400", "--title", "cli test"])
    text = capsys.readouterr().out
    assert "peaks:" in text and "MAC abs" in text  # truth.npz in the folder triggers the comparison
    names = {p.name for p in out.iterdir()}
    assert names >= {"ods_results.npz", "ods_peaks.csv", "transmissibility.csv", "coherence.csv", "asd.csv", "ods_viewer.html"}
    assert "cli test" in (out / "ods_viewer.html").read_text(encoding="utf-8")


def test_missing_test_folder_exits_with_a_message(tmp_path):
    with pytest.raises(SystemExit) as e:
        main(["run", str(tmp_path / "nope"), "--out", str(tmp_path / "o")])
    assert "ods: error: Test folder not found" in str(e.value)


def test_invalid_data_exits_with_a_message(synth_dir, tmp_path):
    with pytest.raises(SystemExit, match=r"ods: error: df must be a positive"):
        main(["run", str(synth_dir), "--out", str(tmp_path / "o"), "--df", "0"])


def test_no_subcommand_is_a_usage_error():
    with pytest.raises(SystemExit) as e:
        main([])
    assert e.value.code == 2


def test_python_dash_m_ods_runs_and_reports_errors(tmp_path):
    ok = subprocess.run([sys.executable, "-m", "ods", "--help"], capture_output=True, text=True)
    assert ok.returncode == 0 and "synth" in ok.stdout
    bad = subprocess.run([sys.executable, "-m", "ods", "run", str(tmp_path / "nope")], capture_output=True, text=True)
    assert bad.returncode == 1 and "ods: error:" in bad.stderr and "Traceback" not in bad.stderr
