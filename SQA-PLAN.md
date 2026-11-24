# SQA plan — CI evidence and quality gates

Goal: make every CI run leave reviewable, reproducible evidence, following a graded
(lightweight) software-quality-assurance approach suited to engineering/R&D software that is
not safety-critical. Guidance drawn on (listed in `docs/references.md`):
IEEE 730 (SQA processes), IEEE 1012 and ASME V&V 10 (verification and validation of
computational models), NASA-STD-8739.8 (software assurance), *Good Enough Practices in
Scientific Computing*. This is not a claim of compliance with any of them.

Decisions (user, 2026-11-24): add `pytest-cov` and `ruff` as dev dependencies; keep CI
artifacts 90 days and attach the evidence bundle to releases.

## Existing controls (kept)
- `main` ruleset: PR required, 3 status checks required, no deletion, no force-push.
  CI job names are therefore load-bearing — do not rename them.
- Actions pinned to commit SHAs; uv pinned; `uv sync --locked`. (Paths below are as of that change; the project
  was later split into `python/` and `matlab/`, see `docs/sqa.md`.)
- Analytical cantilever benchmark with stated, margin-justified tolerances.

## Phases

### 1. Evidence capture in CI
- [x] Dev deps `pytest-cov`, `ruff` (`uv add --dev`; `uv.lock` revision line kept at 3).
- [x] `pytest` writes `junit.xml`, `coverage.xml`, HTML coverage into `evidence/`.
- [x] `.github/scripts/provenance.py` writes `evidence/provenance.json` (commit, run URL,
      `uv.lock` SHA-256, Python/numpy/scipy/pytest versions, OS, UTC time).
- [x] Upload `evidence/` per matrix leg (`retention-days: 90`, `if: always()`).

### 2. Verification metrics
- [x] `tests/conftest.py`: `record_metric` fixture; writes `verification_metrics.json`
      only when `ODS_EVIDENCE_DIR` is set (no effect on local runs).
- [x] Record the benchmark's measured errors next to their limits (value, limit, comparison).

### 3. Quality gates
- [x] Ruff lint (`E4,E7,E9,F,B`, line length 150, `B905` ignored) — passes with no code changes.
- [x] Coverage floor below the measured baseline.
- [x] Not gated, flagged: `ruff format` (7 files would change at line length 150);
      `B905` (`zip` without `strict=`, 8 sites).

### 4. Documentation
- [x] `docs/sqa.md`: scope, V&V approach, requirement-to-test traceability, change control,
      evidence, anomaly handling, known gaps.
- [x] `docs/references.md`: add the standards above.

### 5. Release evidence
- [x] `release-evidence.yml`: on release, run the tests via `workflow_call`, bundle all
      evidence, attach it to the release. Untested until a release is published.

## Out of scope / recommendations
- CLI (`__main__.py`) has 0 % coverage — add tests in a separate change.
- MATLAB code has its own tests (`matlab/tests`) that CI does not run.
