# Software quality assurance

`ods` is engineering / R&D software: its results inform engineering judgement but it is not
safety-critical. The approach is therefore *graded*: the practices of IEEE 730, IEEE 1012,
ASME V&V 10, NASA-STD-8739.8 and *Good Enough Practices in Scientific Computing*
([references](references.md), items 10-14) that give the most assurance per unit of effort.
**This is not a claim of compliance with any of them.**

## 1. Verification and validation approach

| Level | What | Where |
|---|---|---|
| Code verification, exact reference | The pipeline is run on a simulated test whose exact answer is known in closed form (uniform Euler-Bernoulli cantilever on a shaker). The reference formula is itself checked three ways first, so an error in it cannot hide behind the pipeline. | `python/tests/test_benchmark_cantilever.py` |
| Code verification, estimation theory | The measured H1 error is compared with the random error that Bendat & Piersol predict, which catches wrong scaling, window or averaging conventions. | same file, `test_random_error_matches_theory` |
| Unit tests | Spectral estimation, projections, unit conversions, MAC/MPC, parsing, input validation, export. | `python/tests/test_ods.py` |
| Cross-implementation check | The Python and MATLAB versions run the **same language-neutral cases** (`testdata/cases/*.json`: input, options, golden outputs, per-quantity tolerances) through one thin runner each. The current golden file comes from the Python pipeline, so this detects drift between the two implementations, not which one is wrong. | `python/tests/test_shared_cases.py`, `testSharedCases` in `matlab/tests/run_tests.m` |
| Validation against measurements | **Not yet done.** The benchmark and the synthetic box model are simulations. No real shaker data set is used. | gap, see section 6 |

Where a tolerance is derived, the derivation is stated beside the assertion (for most benchmark
limits: the worst of 82 independent noise seeds, plus margin; one cites 20 seeds, and some
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
| `provenance.json` | Commit, run URL, OS, Python, numpy/scipy/pytest versions, SHA-256 of `uv.lock`, UTC time. On pull-request runs the commit is GitHub's temporary merge commit, not the branch head; on pushes to `main` and on releases it is the exact commit. |

When a release is published, `release-evidence.yml` re-runs the tests and attaches all of this,
zipped with a SHA-256 file, to the release. That is the permanent record of a released version.

To reproduce a run locally:

```
cd python
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
  Changes are also gone over by a separate AI reviewer agent (see `CLAUDE.md`). That is a useful
  check, but it is a practice, not independent review in the SQA sense.

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
| R9 | The Python and MATLAB versions give the same results on the shared cases, within each stated tolerance (Python: pytest; MATLAB: Octave in CI, and MATLAB where available) | `test_shared_case` (one per check; `test_cases_are_present`, `test_case_specs_are_well_formed` guard the spec), `testSharedCases` (MATLAB) |
| R10 | The synthetic test generator is well posed, its modal formula matches an SDOF reference, and it matches its stated input level | `test_box_model_is_well_posed`, `test_modal_transmissibility_matches_sdof`, `test_input_level_matches_profile` |
| R11 | Files that must exist twice (the MATLAB toolbox must be self-contained; a Python build cannot reach the repo root) stay identical | `test_matlab_viewer_template_matches_python`, `test_python_license_copy_matches_root` |
| R12 | A test folder from someone else cannot make the tool read outside it (Python also refuses links that lead out; MATLAB has no link check), is refused when the size it declares is above the limit (a crafted compressed MAT file can still exceed what it declares; a `.mat` `channels` cell and `truth.mat` are not size-bounded; on GNU Octave the MAT-file checks run after the file is read), cannot make the tool load anything but the expected arrays, and text from it cannot act as a spreadsheet formula, shift CSV columns, or inject markup or script into the viewer | `python/tests/test_input_safety.py` (`test_time_file_outside_the_test_folder_is_rejected`, `test_time_file_in_a_subfolder_is_accepted`, `test_link_to_a_file_outside_the_test_folder_is_rejected`, `test_time_data_above_the_size_limit_is_refused_before_loading`, `test_npz_member_named_data_counts_against_the_limit`, `test_mat_with_a_second_data_variable_is_refused`, `test_mat_data_in_a_cell_is_refused_before_loading`, `test_csv_size_estimate_is_close_to_the_real_size`, `test_mat_loads_only_the_variables_it_uses`, `test_non_finite_coordinates_are_rejected`, `test_csv_cell`, `test_export_keeps_hostile_channel_names_in_their_own_cell`, `test_viewer_embeds_hostile_text_and_non_finite_numbers_safely`, `test_viewer_csp_allows_only_its_own_script`); `testUntrustedInput`, `testSafeOutput` (MATLAB) |

When behaviour is added or changed, update this table in the same pull request.

## 5. Problems found

A bug is fixed together with a test that fails without the fix, and the pull request says what
was wrong and what results it could have affected (for example PR #13, a control-gain error).

## 6. Known gaps

- No validation against real measured data (section 1).
- `python/src/ods/__main__.py` (the command line) has no tests: 0 % coverage.
- The MATLAB suite runs in CI on GNU Octave (a different implementation of the language) and on real MATLAB (the latest release; R2026b at first run, including `buildtool test`) in a non-blocking job, because its set-up depends on MathWorks' action and licensing. Neither CI job is a required check on `main` unless the ruleset is changed. The analytic cantilever benchmark is Python-only: it needs a 60 s noise record (~22 MB) that is generated, not stored.
- MATLAB results (JUnit, coverage; for Octave only the log) are uploaded as separate CI artifacts (`matlab-report`, `matlab-octave-report`, 90 days) but are not part of the release evidence bundle, because `release-evidence.yml` reuses only `tests.yml`. The same reports can be produced on any machine with `run_all_tests` (see `matlab/README.md`).
- `ruff format` is not enforced (it would reformat 7 files), and `zip()` without `strict=` is
  allowed (8 places): both are left for separate changes.
- No independent code review (single maintainer).
- No security or dependency-vulnerability scan.
