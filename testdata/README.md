# Shared test data and cases

Language-neutral tests that both the Python (`python/`) and MATLAB (`matlab/`) implementations
must pass. Each language has one thin runner that reads the same files, so the two cannot drift:

| Language | Runner |
|---|---|
| Python | `python/tests/test_shared_cases.py` |
| MATLAB / Octave | `testSharedCases` in `matlab/tests/run_tests.m` |

```
testdata/
  cases/      one JSON spec per case: input folder, options, expected file, checks and tolerances
  data/       input test folders (ods data format, see docs/data-format.md) and golden outputs
  generate/   scripts that (re)create golden outputs; run with the Python environment
```

## Case format (`cases/*.json`)

| Field | Meaning |
|---|---|
| `id` | Unique name, shown in test reports |
| `description` | What the case verifies, and where the golden values come from |
| `input` | Test folder, relative to `testdata/` |
| `options` | Pipeline options: `df` (Hz) and `band` (`[fmin, fmax]` Hz) |
| `expected` | Golden outputs (`.mat`, readable from both languages), relative to `testdata/` |
| `checks` | List of `{quantity, rtol, atol, atol_fullscale}`; `quantity` is a variable name in the golden file |

Every check uses the same rule, element by element (complex values compare by modulus of the difference):

```
|actual - expected| <= atol + atol_fullscale * max|expected| + rtol * |expected|
```

All three tolerances at 0 means exact equality (counts, peak bins). `atol_fullscale` absorbs
round-off in small elements that remain after cancellation (they differ between BLAS builds).
Arrays are compared as flat lists of numbers, so only the element count must match (a transposed
array of the same size is compared in a different order by the two languages and will fail).
NaN must appear in the same places, and an empty expected array passes. A case must have at
least one check. Every field is always present and in the same order, so MATLAB's `jsondecode`
returns a struct array.

## Adding a case

1. Put the input folder in `data/<name>/` and write the golden outputs (extend a script in `generate/`).
2. Add `cases/<name>.json`. A runner needs a new quantity only if it is not already one of
   the names both runners expose (`T`, `coh`, `Gbb`, `Gxx`, `T_rel`, `T_el`, `disp_el`, `rigid_R`,
   `nfft`, `n_avg`, `f`, `peak_index`, `peak_f`, `peak_mpc`, `peak_coh`); add it to both.
3. Run both suites. Do not loosen a tolerance to make a case pass without saying why in the PR.

## Regenerating the parity golden file

`parity-box-z` is produced by the Python pipeline, so it detects drift between the two
implementations but cannot say which is wrong. Regenerate only after an intended behaviour change:

```
cd python && uv run python ../testdata/generate/make_parity_fixture.py
```
