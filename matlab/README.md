# ods for MATLAB

This is the MATLAB version of the ODS tool. It reads the same test folders, writes the same CSVs, and builds the same interactive HTML viewer as the Python version. It also adds a native MATLAB animation.

- **Base MATLAB only.** No Signal Processing Toolbox is needed: Welch/H1, coherence and peak picking are implemented directly.
- **Matches the Python version to round-off (verified on GNU Octave 7.3 and on MATLAB R2026b in CI; other releases untested).** A parity test runs both on the same data.
- **Plain syntax** (char/cellstr, no `arguments` blocks), so it should also run in GNU Octave 7+.

> **Status:** The test suite (below) passes under GNU Octave and under MATLAB R2026b (the latest release when the CI job was first run, pull request #17). CI runs it on Octave and on the latest MATLAB for every change; the MATLAB job is non-blocking because it depends on MathWorks' action and licensing. The algorithms were also checked against scipy, and the results agree with the Python version on the shared cases in `testdata/`. If you find a failure that is specific to MATLAB, please report it.

## Quick start

From the repository root in MATLAB:

```matlab
run('matlab/toolbox/examples/run_demo.m')
```

The demo:
1. builds the synthetic box-on-isolators test (60 s, Z random, 6.06 grms) in `matlab/data/synthetic`;
2. processes it into `matlab/outputs`, printing the peaks and a comparison against the true modes;
3. opens the HTML viewer in your browser and animates the 283 Hz panel mode in a figure.

## Your own test

The folder layout is the same as for Python ([docs/data-format.md](../docs/data-format.md)). The time file must be `time.mat` or `time.csv`; MATLAB can't read `.npz`.

```matlab
addpath('matlab/toolbox')
data = myAccels;                         % N x nch, g
channels = {'CTRL','A1Z','A2Z', ...};    % one name per column, matching channels.csv
fs = 5120;
save('my_test_z/time.mat', 'data', 'channels', 'fs')

res = ods.process('my_test_z', 'results/my_test_z', struct('title', 'Unit 3, Z random'));
ods.animateShape(res, 283, 'el')         % nearest bin to 283 Hz; 'abs' | 'rel' | 'el'
```

Options for `ods.process` / `ods.runPipeline` (all optional):

| Field | Default | Meaning |
|---|---|---|
| `df` | 0.625 | Target frequency resolution, Hz |
| `band` | `[20 2000]` | Peak-search band, Hz |
| `prominenceDb` | 3 | Minimum peak prominence, dB |
| `minCoh` | 0.5 | Minimum |T|²-weighted coherence at a peak |
| `title` | folder name | Viewer heading (`process` only) |

## Outputs

These are the same as the Python version, except that `ods_results.mat` replaces `ods_results.npz`. The variable names are identical: `f`, `T`, `T_rel`, `T_elastic`, `coherence`, `Gxx`, `Gbb`, `peak_f`, `peak_index` (1-based), `peak_shapes_mm_per_unit`, `peak_shapes_elastic_mm_per_unit`, `rigid_R`, …

## Functions

| Function | Purpose |
|---|---|
| `ods.process` | Test folder → all outputs (the twin of `ods run`) |
| `ods.loadTest`, `ods.readCsv`, `ods.splitCsvLine` | Read a test folder; small quote-aware CSV reader |
| `ods.computeSpectra` | Welch ASDs, H1 transmissibility, coherence |
| `ods.runPipeline` | Spectra → relative/elastic views → peaks |
| `ods.findPeaks` | Coherence-gated peak picking (reproduces `scipy.signal.find_peaks`) |
| `ods.relativeTransmissibility`, `ods.rigidBodyProjector`, `ods.accelToDisplacement` | The three views and the conversion to displacement |
| `ods.nodeProjectors`, `ods.nodeShapes` | Sensor values → xyz motion per node |
| `ods.mpc`, `ods.mac` | Shape complexity and similarity |
| `ods.exportResults`, `ods.buildViewer`, `ods.animateShape` | MAT/CSV export, HTML viewer, MATLAB figure animation |
| `ods.synthBoxModel`, `ods.synthSimulate`, `ods.synthWriteTest`, `ods.compareTruth` | Synthetic test with known modes |

Every function has `help` text, e.g. `help ods.computeSpectra`. The method is described in [docs/method.md](../docs/method.md).

## Layout and what is not (yet) provided

`toolbox/` is what a user installs (the `+ods` package, `resources/`, `examples/`); `tests/` and `buildfile.m` are for developers, following [MathWorks' toolbox best practices](https://github.com/mathworks/toolboxdesign). Not provided yet: `doc/GettingStarted`, `Contents.m`, `functionSignatures.json`, a MATLAB project / `.mltbx` package, and `matlab.unittest`-based tests (the suite uses plain asserts so that Octave can run it too).

## Tests

```matlab
addpath('matlab/tests'); run_tests
```

Or, in MATLAB (R2022b+), from the `matlab` folder: `buildtool test`. GNU Octave has no `buildtool`. This runs 19 tests:
- analytic SDOF H1, units, MPC/MAC, rigid-body removal, node projection, direction parsing, plateau and band-edge peaks, CSV quoting, tilted controls (g = ±0.8), invalid excitation_axis;
- untrusted input (time_file outside the folder, non-numeric .mat contents, non-finite geometry) and safe output (formula-like and comma names in CSVs, markup in the viewer data);
- the synthetic model;
- **the shared cases** in `testdata/cases/` (the same JSON files the Python suite runs: T, coherence, ASDs, elastic view and peaks must match the golden file within each check's stated tolerance);
- an end-to-end synthetic run with MAC thresholds.

The golden file is generated by the Python tool. If the Python numerics change on purpose, regenerate it (see [`testdata/README.md`](../testdata/README.md)):

```powershell
cd python
uv run python ../testdata/generate/make_parity_fixture.py
```

The Python suite runs the same cases, so a change that breaks either implementation fails its tests.
