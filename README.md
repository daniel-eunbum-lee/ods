# ods

[![Python tests](https://github.com/daniel-eunbum-lee/ods/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/daniel-eunbum-lee/ods/actions/workflows/tests.yml)
[![MATLAB tests](https://github.com/daniel-eunbum-lee/ods/actions/workflows/matlab.yml/badge.svg?branch=main)](https://github.com/daniel-eunbum-lee/ods/actions/workflows/matlab.yml)
[![Python coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fdaniel-eunbum-lee%2Fods%2Fbadges%2Fpython-coverage.json)](https://github.com/daniel-eunbum-lee/ods/actions/workflows/badges.yml)
[![MATLAB coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fdaniel-eunbum-lee%2Fods%2Fbadges%2Fmatlab-coverage.json)](https://github.com/daniel-eunbum-lee/ods/actions/workflows/matlab.yml)
[![License: MIT](https://img.shields.io/github/license/daniel-eunbum-lee/ods)](LICENSE)
![Python 3.11 | 3.14](https://img.shields.io/badge/python-3.11%20%7C%203.14-blue)
![MATLAB latest and GNU Octave 7+](https://img.shields.io/badge/MATLAB-latest%20%C2%B7%20Octave%207%2B-orange)
![Python tested on Linux and Windows](https://img.shields.io/badge/Python%20tested%20on-Linux%20%C2%B7%20Windows-lightgrey)
[![Cite](https://img.shields.io/badge/cite-CITATION.cff-informational)](CITATION.cff)

**Operating deflection shapes (ODS) from shaker random-vibration tests.** Point it at your acceleration time histories, sensor geometry and control channel, and see how the unit actually moved at each resonance.

![ODS viewer: top-panel mode of a box on isolators](docs/images/viewer-shape.jpg)

What it does:
- **Transmissibility-based ODS.** It uses the H1 estimate against the control accelerometer, so the shaped test profile drops out and every channel gets magnitude *and* phase, plus coherence to tell you how far to trust it.
- **Three views of the motion:**
  - **Absolute**: what the accelerometers measured.
  - **Relative to table**: for isolator and rigid-body modes.
  - **Elastic**: least-squares 6-DOF rigid-body motion removed, so you see what's deforming even on isolated units.
- **Automatic peak picking**, gated on coherence, plus an MPC readout that flags mixed or complex shapes.
- **A standalone HTML viewer** in one shareable file with no dependencies. It animates the 3D shape, and you can click any frequency on the spectrum.
- **Report-ready outputs**: CSVs (transmissibility, coherence, ASD, per-peak shapes in mm/g) and an NPZ of everything.
- **Validated** against the exact solution of a base-driven cantilever beam: transmissibility within 0.7 % (p99) away from resonances, peaks at the analytic natural frequencies, and shapes matching the exact ODS to MAC > 0.99999. A synthetic box-on-isolators test with known modes adds peaks within 0.4 % and MAC up to 0.999 ([details](docs/method.md#validation)).

## Quick start

Requires Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/).

```powershell
git clone https://github.com/daniel-eunbum-lee/ods.git
```

```powershell
cd ods/python
```

The Python tool lives in `python/`; run the `uv` commands below from that folder.

```powershell
uv sync
```

```powershell
uv run ods synth
```

```powershell
uv run ods run data/synthetic
```

Then open `outputs/ods_viewer.html` in a browser. To look before installing, download a demo viewer and open it locally: [box on isolators](docs/demo/ods_viewer.html) or the [cantilever beam benchmark](docs/demo/ods_viewer_cantilever.html).

## Your own test

Make one folder per test axis (all channels from one synchronized recording):

```
my_test_z/
  test.json      {"fs": 5120, "units": "g", "excitation_axis": "Z", "time_file": "time.csv"}
  time.csv       time,CTRL,A1Z,A2Z,...
  geometry.csv   node,x,y,z,base
  channels.csv   channel,node,direction,role      (exactly one role=control)
  lines.csv      node_a,node_b                    (optional wireframe)
```

```powershell
uv run ods run my_test_z --out results/my_test_z --title "Unit 3, Z random"
```

Start from the templates in [`examples/template/`](examples/template/).

## MATLAB

A MATLAB version lives in [`matlab/`](matlab/). It reads the same test folders, writes the same outputs and viewer, and needs no toolboxes:

```matlab
run('matlab/toolbox/examples/run_demo.m')             % synthetic demo
res = ods.process('my_test_z', 'results/my_test_z');  % your data (after addpath matlab/toolbox)
```

See [matlab/README.md](matlab/README.md).

## Dependencies

What the tool needs, in two main groups. **Runtime** dependencies are needed to *use* the tool: if one is missing, `ods` does not run. **Development** dependencies are needed only to *work on* the tool (run its tests, measure coverage, check the code style). You never need them just to process your own test data. A third group, **Build**, is only the tool that packages the project when it is built or installed.

### Python (3.11 or newer)

| Package | Group | Minimum version | Locked version* | What it is used for |
|---|---|---|---|---|
| [numpy](https://numpy.org) | Runtime | 2.4.6 | 2.5.5 (2.4.6 on Python 3.11) | Arrays, FFT, linear algebra |
| [scipy](https://scipy.org) | Runtime | 1.17.1 | 1.18.1 (1.17.1 on Python 3.11) | Reading `.mat` files, Welch spectral estimates, peak finding |
| [pytest](https://pytest.org) | Development | 9.2.0 | 9.2.0 | Runs the test suite |
| [pytest-cov](https://pytest-cov.readthedocs.io) | Development | 7.1.0 | 7.1.0 | Measures how much of the code the tests run (coverage) |
| [ruff](https://docs.astral.sh/ruff/) | Development | 0.17.6 | 0.17.6 | Checks the code for likely bugs (lint) |
| [hatchling](https://hatch.pypa.io) | Build | 1.33.0 (pinned exactly) | n/a | Packages the project; only used when building or installing it. Pinned in `pyproject.toml`; build tools are not recorded in `uv.lock` |

\* The exact versions that CI tests are recorded in [`python/uv.lock`](python/uv.lock); the minimums and groups are declared in [`python/pyproject.toml`](python/pyproject.toml). Everything else the tool imports comes with Python itself (`argparse`, `csv`, `json`, `pathlib`, `re`, `zipfile` and similar).

- `uv sync` (from `python/`) installs **both** runtime and development packages, which is what you want when working on the repository.
- `uv sync --no-dev` installs the runtime packages only.
- The `.venv` folder is only where `uv` puts the installed packages. It is generated from `uv.lock` and is not part of the project, so it is not where the list lives.

### MATLAB

| Needs | Group | Notes |
|---|---|---|
| MATLAB, **base product only** | Runtime | No toolboxes are needed: Welch/H1, coherence and peak picking are implemented in the package itself. The numerical work uses base-MATLAB functions such as `fft`, `ifft`, `svd`, `eig`, `pinv` and `jsondecode`. CI passes on MATLAB R2026b. |
| GNU Octave 7 or newer | Runtime (alternative) | Runs the same code and tests; it cannot produce JUnit or coverage reports. |
| MATLAB's built-in unit-testing framework and code-coverage plugin | Development | Used only by `run_all_tests` and `buildtool test` to produce reports; part of MATLAB itself, not a separate download. `buildtool` needs R2022b or newer. |

There is no MATLAB equivalent of `pyproject.toml`; to have MATLAB list the products the code uses, run `matlab.codetools.requiredFilesAndProducts` on the files in `matlab/toolbox`.

## Documentation

| Guide | Contents |
|---|---|
| [How to use](docs/how-to-use.md) | Install, demo, viewer controls, step-by-step setup for your own data, outputs, tuning, troubleshooting |
| [Data format](docs/data-format.md) | Exact spec for every input file |
| [Method](docs/method.md) | H1 and coherence, relative/elastic views, displacement, peak picking, MPC/MAC, validation results, limits |
| [References](docs/references.md) | Sources |

![Spectrum and coherence plots](docs/images/viewer-spectra.jpg)

## Project layout

One repository, two implementations of the same tool, tested against the same shared cases:

```
python/                  Python implementation (pyproject.toml, uv.lock)
  src/ods/
    io.py                load test folders (CSV/NPZ + geometry)
    spectra.py           Welch H1 transmissibility, coherence, ASDs
    shapes.py            relative/elastic transforms, displacement, peak picking, MPC, MAC
    pipeline.py          run() and export()
    viewer.py            builds the HTML viewer from viewer_template.html
    synth.py             synthetic box-on-isolators shaker test with known modes
    __main__.py          `ods synth` / `ods run` command line
  tests/                 pytest suite (analytic benchmarks, unit tests, shared-case runner)
matlab/                  MATLAB implementation
  toolbox/               what a MATLAB user installs: +ods package, resources/, examples/
  tests/run_tests.m      MATLAB/Octave suite (unit tests + shared-case runner)
  buildfile.m            tasks for MATLAB's `buildtool`
testdata/                SHARED by both: cases/*.json (specs + tolerances), data/, generate/
examples/                test-folder templates (same files for both languages)
docs/                    guides, screenshots, demo viewer (apply to both languages)
```

See [`testdata/README.md`](testdata/README.md) for the shared-test format.

## Development

```powershell
cd python
uv run pytest
```

MATLAB (or GNU Octave), from the repository root:

```matlab
addpath('matlab/tests'); run_tests
```

GitHub Actions runs the Python suite on every push to main and every pull request (Python 3.11 and 3.14 on Linux, 3.14 on Windows; see [`.github/workflows/tests.yml`](.github/workflows/tests.yml)), and the MATLAB suite on GNU Octave and, where MathWorks' action can set it up, on MATLAB itself ([`.github/workflows/matlab.yml`](.github/workflows/matlab.yml)). Both run the shared cases in `testdata/`.

[PLAN.md](PLAN.md) records the design decisions made during the initial build.

## License

[MIT](LICENSE)
