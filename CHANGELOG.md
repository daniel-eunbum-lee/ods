# Changelog

## 0.1.0

First tagged release. The MATLAB version does not yet have the Python input checks listed below, so this is 0.x rather than 1.0.

- Transmissibility-based ODS from shaker tests (H1, coherence, absolute / relative / elastic views, peak picking, MPC/MAC), in Python and in MATLAB, with a standalone HTML viewer.
- Checked against the exact solution of a base-driven cantilever beam, and Python against MATLAB on shared cases (`docs/sqa.md`).
- Input folders are treated as untrusted; CSV and viewer output is safe to open.
- Python: bad input now stops with a clear message (the MATLAB version does not check these yet): NaN or infinite samples, channel names that do not match the data columns, a non-positive sample rate or resolution, a constant control channel, a missing test folder. The command line prints a one-line `ods: error:` and exits with code 1 instead of a traceback.
- Two demo viewers in `docs/demo/`: the synthetic box on isolators and the cantilever benchmark. Rebuild them with `testdata/generate/make_demo_viewers.py`.

Known limits: the MATLAB loader lacks the new input checks; not validated against real measured data; `ruff format` is not enforced. See `docs/sqa.md`, section 6.
