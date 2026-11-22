# ods

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
- **Validated** on a synthetic shaker test with known modes: peaks within 0.4 % of the true frequencies, and MAC up to 0.999 ([details](docs/method.md#validation)).

## Quick start

Requires Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/).

```powershell
git clone https://github.com/daniel-eunbum-lee/ods.git
```

```powershell
cd ods
```

```powershell
uv sync
```

```powershell
uv run ods synth
```

```powershell
uv run ods run data/synthetic
```

Then open `outputs/ods_viewer.html` in a browser. To look before installing, download [`docs/demo/ods_viewer.html`](docs/demo/ods_viewer.html) and open it locally.

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
run('matlab/run_demo.m')                              % synthetic demo
res = ods.process('my_test_z', 'results/my_test_z');  % your data (after addpath matlab)
```

See [matlab/README.md](matlab/README.md).

## Documentation

| Guide | Contents |
|---|---|
| [How to use](docs/how-to-use.md) | Install, demo, viewer controls, step-by-step setup for your own data, outputs, tuning, troubleshooting |
| [Data format](docs/data-format.md) | Exact spec for every input file |
| [Method](docs/method.md) | H1 and coherence, relative/elastic views, displacement, peak picking, MPC/MAC, validation results, limits |
| [References](docs/references.md) | Sources |

![Spectrum and coherence plots](docs/images/viewer-spectra.jpg)

## Project layout

```
src/ods/
  io.py          load test folders (CSV/NPZ + geometry)
  spectra.py     Welch H1 transmissibility, coherence, ASDs
  shapes.py      relative/elastic transforms, displacement, peak picking, MPC, MAC
  pipeline.py    run() and export()
  viewer.py      builds the HTML viewer from viewer_template.html
  synth.py       synthetic box-on-isolators shaker test with known modes
  __main__.py    `ods synth` / `ods run` command line
tests/           pytest suite (analytic SDOF checks + end-to-end synthetic validation)
matlab/          MATLAB version: +ods package, run_demo.m, tests (incl. parity with Python)
examples/        test-folder templates
docs/            guides, screenshots, demo viewer
```

## Development

```powershell
uv run pytest
```

[PLAN.md](PLAN.md) records the design decisions made during the initial build.

## License

[MIT](LICENSE)
