# Test-folder template

These are starter files for one shaker run. Copy this folder, edit the rows to match your setup, and add your time-history file (`time.csv` or `time.npz`). There's no time data here, so you can't run it as is.

| File | What to edit |
|---|---|
| `test.json` | Sample rate, units (`g` or `m/s^2`), excitation axis of this run |
| `geometry.csv` | One row per node; `base=1` for points on the shaker table or fixture |
| `channels.csv` | One row per column of the time file. Shows `+`/`-` directions, a skewed sensor (`A3S`), and the single `control` row |
| `lines.csv` | Wireframe edges between nodes, for display only |

The full format is in [docs/data-format.md](../../docs/data-format.md).
