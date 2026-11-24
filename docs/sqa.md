# Software quality assurance

`ods` is engineering / R&D software: its results inform engineering judgement but it is not
safety-critical. The approach is therefore *graded*: the practices of IEEE 730, IEEE 1012,
ASME V&V 10, NASA-STD-8739.8 and *Good Enough Practices in Scientific Computing*
([references](references.md), items 10-14) that give the most assurance per unit of effort.
**This is not a claim of compliance with any of them.**

## 1. Verification and validation approach

| Level | What | Where |
|---|---|---|
| Code verification, exact reference | The pipeline is run on a simulated test whose exact answer is known in closed form (uniform Euler-Bernoulli cantilever on a shaker). The reference formula is itself checked three ways first, so an error in it cannot hide behind the pipeline. | `tests/test_benchmark_cantilever.py` |
| Code verification, estimation theory | The measured H1 error is compared with the random error that Bendat & Piersol predict, which catches wrong scaling, window or averaging conventions. | same file, `test_random_error_matches_theory` |
| Unit tests | Spectral estimation, projections, unit conversions, MAC/MPC, parsing, input validation, export. | `tests/test_ods.py` |
| Cross-implementation check | The MATLAB port is compared with the Python results on a frozen fixture. | `test_matlab_parity_fixture_is_current`, `matlab/tests/` |
| Validation against measurements | **Not yet done.** The benchmark and the synthetic box model are simulations. No real shaker data set is used. | gap, see section 6 |

Where a tolerance is derived, the derivation is stated beside the assertion (for most benchmark
limits: the worst of 82 independent noise seeds, plus margin; a few cite 20 seeds, and some
checks have no derivation). By convention, a tolerance is changed only with a stated reason in
the pull request; this is a working agreement, not an enforced gate.

## 2. Evidence kept from every CI run

Each run of the `tests` workflow (Linux Python 3.11 and 3.14, Windows Python 3.14) uploads an
`evidence-<os>-py<version>` artifact, kept 90 days:

| File | Content |
|---|---|
| `junit.xml` | Result of every test |
| `coverage.xml`, `htmlcov/` | Line and branch coverage |
| `verification_metrics.json` | The main benchmark errors (transmissibility, random-error statistics, peak frequency and coherence, ODS shape and amplitude) next to their limits (value, limit, comparison), so accuracy can be compared between runs and versions, not only pass/fail. Not every assertion is recorded. |
| `provenance.json` | Commit, run URL, OS, Python, numpy/scipy/pytest versions, SHA-256 of `uv.lock`, UTC time |

When a release is published, `release-evidence.yml` re-runs the tests and attaches all of this,
zipped with a SHA-256 file, to the release. That is the permanent record of a released version.

To reproduce a run locally:

```
uv sync --locked
ODS_EVIDENCE_DIR=evidence uv run pytest -ra --junitxml=evidence/junit.xml --cov
```

## 3. Change control

- Changes reach `main` only through a pull request. The repository ruleset also requires the three
  `Python ...` checks to pass, and forbids force-push and deletion of `main`.
  **The CI job names are part of that rule: renaming them breaks it.**
- Dependencies are pinned in `uv.lock`; CI runs `uv sync --locked` with a pinned uv version, and
  GitHub Actions are pinned to commit SHAs.
- `.gitattributes` fixes text files to LF so results and hashes do not depend on the checkout OS.
- Quality gates in CI: `ruff check` (bug-finding rules, `pyproject.toml`) and a coverage floor
  (`fail_under`, currently 78 % against a measured 82 %).
- The ruleset requires no approving review (single maintainer): there is **no independent review**.

## 4. Requirements and traceability

| ID | Requirement | Verified by |
|---|---|---|
| R1 | H1 transmissibility and coherence are estimated correctly, with the requested resolution; records too short are rejected | `test_nfft_for_resolution`, `test_h1_recovers_sdof_transmissibility`, `test_csd_broadcasting_matches_per_channel_loop`, `test_record_shorter_than_nfft_raises` |
| R2 | Motion relative to the table is correct for any sensor direction and control sensor (inverted, skewed, negative axis); invalid setups are rejected | `test_relative_transmissibility_subtracts_projection_only`, `test_inverted_control_gives_same_views`, `test_skewed_control_gives_same_views`, `test_control_perpendicular_to_excitation_raises`, `test_excitation_axis_accepted`, `test_excitation_axis_invalid_raises`, `test_negative_excitation_axis_end_to_end` |
| R3 | Acceleration converts to displacement with correct units and sign (mm per g) | `test_accel_to_displacement_units_and_sign`, `test_exported_peak_table_in_mm_per_g` |
| R4 | Shapes, projections and indicators (MAC, MPC) are correct | `test_mpc_and_mac`, `test_rigid_body_projector_removes_rigid_motion_only`, `test_node_projectors_triax_and_partial`, `test_parse_direction`, `test_ods_matches_true_modes` |
| R5 | Resonance peaks are found at the right frequencies, with no spurious or missing peaks | `test_peaks_are_the_cantilever_modes`, `test_no_spurious_peak_at_band_edge` |
| R6 | Input files (NPZ, CSV, `test.json`) are read correctly and malformed input is rejected | `test_csv_input_matches_npz`, `test_csv_with_bom_short_rows_and_case`, `test_duplicate_channel_rows_raise`, `test_fs_from_rounded_time_column`, `test_test_json_fs_wins_over_time_file` |
| R7 | Exported tables and the HTML viewer carry the right numbers | `test_export_and_viewer`, `test_export_with_no_peaks` (export and viewer survive an empty peak list), `test_viewer_reports_table_rms_for_skewed_control`, `test_exported_transmissibility_csv_matches_exact` |
| R8 | The full pipeline reproduces an exact analytical solution within stated tolerances | `test_reference_frequency_equation_matches_blevins`, `test_reference_matches_direct_boundary_value_solve`, `test_reference_static_limit_and_modal_sum`, `test_transmissibility_matches_exact_away_from_resonance`, `test_random_error_matches_theory`, `test_ods_at_each_peak_matches_exact_shape` |
| R9 | The Python output matches the frozen fixture that the MATLAB port is tested against (MATLAB itself is not run in CI) | `test_matlab_parity_fixture_is_current` |
| R10 | The synthetic test generator is well posed, its modal formula matches an SDOF reference, and it matches its stated input level | `test_box_model_is_well_posed`, `test_modal_transmissibility_matches_sdof`, `test_input_level_matches_profile` |

When behaviour is added or changed, update this table in the same pull request.

## 5. Problems found

A bug is fixed together with a test that fails without the fix, and the pull request says what
was wrong and what results it could have affected (for example PR #13, a control-gain error).

## 6. Known gaps

- No validation against real measured data (section 1).
- `src/ods/__main__.py` (the command line) has no tests: 0 % coverage.
- The MATLAB tests (`matlab/tests/`) are not run by CI; only the parity fixture is checked from Python.
- `ruff format` is not enforced (it would reformat 7 files), and `zip()` without `strict=` is
  allowed (8 places): both are left for separate changes.
- No independent code review (single maintainer).
- No security or dependency-vulnerability scan.
