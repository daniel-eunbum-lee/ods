# ODS tool — plan

Goal: transmissibility-based Operating Deflection Shape (ODS) pipeline for shaker
test data, validated on a synthetic test whose true modes are known, with a
standalone HTML animation viewer.

## Phase 1 — Project setup
- uv project (`pyproject.toml`, `.venv`), deps: numpy, scipy; dev: pytest.
- Layout: `src/ods/` package, `tests/`, `data/synthetic/`, `outputs/`.

## Phase 2 — Synthetic shaker test (`ods.synth`)
- 9-node lumped-mass model of a small box on 4 corner isolators:
  - 8 box corners joined by axial bar springs (edges + face diagonals → elastic box modes, ~1 kHz+).
  - 4 isolators (bushings, kx/ky/kz) from bottom corners to the shaker table → rigid-body modes (~40–120 Hz).
  - Top-panel centre node on soft-in-Z bushings → "panel drum" mode (~350 Hz).
  - Extra mass on one top corner → bounce/pitch/roll couple under Z excitation.
- Relative-coordinate EOM: `M z'' + C z' + K z = -M r a_b`; modal damping (2–4 %).
- Base accel: band-limited random 20–2000 Hz with a *shaped* (non-flat) ASD so we can
  confirm transmissibility removes the profile.
- Responses computed by FFT filtering (steady-state, periodic), + sensor noise.
- Writes the same files a real test would: `time.npz` (or CSV), `geometry.csv`, `lines.csv`.
- Ground truth: natural frequencies + mode shapes from the eigen-solve (`truth.npz`).

## Phase 3 — Processing pipeline
1. `ods.io` — load time data (CSV/NPZ) + geometry (channel, node, x, y, z, direction).
2. `ods.spectra` — Welch ASDs, H1 transmissibility `T = G_bx/G_bb`, coherence (Hann, 50 % overlap).
3. `ods.shapes`
   - Relative motion: `T_rel = T − d·e` (d = sensor direction, e = excitation axis).
     *Note: "T − 1" is only right for sensors parallel to the excitation; cross-axis
     sensors have no base term to subtract.*
   - Displacement: `T_rel · g0 / (−ω²)` → mm per g of input.
   - Peak picking on the channel-norm of `T_rel` (scipy `find_peaks`, prominence).
   - Complexity check per shape: MPC (modal phase collinearity).
   - MAC utility for comparing shapes.
   - Per-node 3×k pseudo-inverse to turn channel values into node vectors (unmeasured DOFs → 0).
4. `ods.export` — `outputs/ods_results.npz` + CSVs (T, coherence, ASDs, peak shapes).
5. `ods.viewer` — standalone HTML (no CDN): spectrum + coherence plots (click to pick f),
   peak list, 3D canvas animation of `Re{shape·e^{jωt}}`, orbit/zoom, ghost undeformed shape.
6. `ods.cli` — `python -m ods synth` / `python -m ods run <data dir>`.

### Change after the trial run
Peak picking on the norm of `T_rel` found only 2 of ~10 resonances. On the isolated box
`T − 1 ≈ −1` above ~80 Hz (the table moving under a still unit), and that floor buries the
elastic modes. Peak picking now uses absolute `T` with a |T|²-weighted coherence gate. An
"elastic" view (6-DOF rigid-body least-squares removal) was added for showing those modes.

## Phase 4 — Verification
- pytest: SDOF analytic transmissibility vs H1 estimate; units/scaling of shapes;
  synthetic end-to-end: ODS peaks within one bin of true fn, MAC(ODS, true mode) > 0.9
  for well-separated modes.
- Small trial (short record) first, then full 60 s run.
- Open the viewer in the browser pane and check it renders/animates.
