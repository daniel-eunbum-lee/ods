# ods (Python)

Python implementation of the transmissibility-based operating deflection shape (ODS) tool for
shaker-test data. See the [repository README](../README.md) for what it does and how to use it,
and [`../docs/how-to-use.md`](../docs/how-to-use.md) for the full workflow.

```
uv sync --locked      # create the environment (from this folder)
uv run pytest         # run the tests
uv run ods --help     # command line
```

The same tool is available in MATLAB (see [`../matlab/`](../matlab/)); both read the same test
folders and are checked against the same shared cases in [`../testdata/`](../testdata/).
