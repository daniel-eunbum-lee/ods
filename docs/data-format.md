# Input data format

One folder holds **one synchronized run** (one test axis). File names are fixed except for the time file, which `test.json` names. A ready-to-edit set is in [`examples/template/`](../examples/template/).

| File | Required | Purpose |
|---|---|---|
| `test.json` | recommended | Sample rate, units, excitation axis, time-file name |
| `time.csv`, `time.mat` or `time.npz` | yes | Time histories (`.npz` is Python-only) |
| `geometry.csv` | yes | Node coordinates |
| `channels.csv` | yes | Channel → node, direction, role |
| `lines.csv` | no | Wireframe for the viewer |

CSV headers are case-insensitive, and surrounding spaces are trimmed.

## `test.json`

```json
{ "fs": 5120, "units": "g", "excitation_axis": "Z", "time_file": "time.csv" }
```

| Key | Default if missing | Notes |
|---|---|---|
| `fs` | `fs` inside the MAT/NPZ, or from the CSV `time` column ((N−1)/time span) | Sample rate in Hz. If given here it always wins over the time file |
| `units` | `"g"` | Acceleration units. `"g"` is converted with g₀ = 9.80665 m/s² for displacement; anything else is treated as m/s² |
| `excitation_axis` | the control channel's direction | `"X"`, `"Y"` or `"Z"`, in global axes |
| `time_file` | first of `time.npz`, `time.mat`, `time.csv` that exists (MATLAB: `time.mat`, `time.csv`) | |

## Time histories

**CSV**: the first row is the channel names. An optional first column named `time` (seconds) is used to infer `fs` if `test.json` doesn't give it, and is otherwise ignored.

```
time,CTRL,A1Z,A2Z,...
0.0000000,0.0123,-0.0045,0.0211,...
0.0001953,...
```

**NPZ** (`numpy.savez`): `data` is an array of shape (N samples × n channels), `channels` is an array of names in column order, and `fs` (optional) is a scalar.

```python
np.savez("time.npz", data=data, channels=np.array(names), fs=5120.0)
```

**MAT** (works in both Python and MATLAB): the same variables, with `channels` as a cell array of names.

```matlab
save('time.mat', 'data', 'channels', 'fs')   % data N x nch, channels {1 x nch} or {nch x 1}
```

The Python tool can write one: `uv run ods synth --format mat`.

Every channel name must appear in `channels.csv`.

## `geometry.csv`

```
node,x,y,z,base
1,0.000,0.000,0.000,0
5,0.150,0.100,0.120,0
100,0.150,0.100,-0.020,1
```

| Column | Notes |
|---|---|
| `node` | Integer id |
| `x, y, z` | Global coordinates. Any length unit works as long as it's consistent; it only affects the drawing and the rigid-body fit |
| `base` | Optional. `1` marks a shaker-table or fixture point. These are not measured: they are drawn at rest in Relative/Elastic views and moving with the table in Absolute view |

## `channels.csv`

```
channel,node,direction,role
CTRL,100,+Z,control
A1Z,1,+Z,response
A5Y,5,-Y,response
A3S,3,0.707 0 0.707,response
```

| Column | Notes |
|---|---|
| `channel` | Must match the time-file column name exactly |
| `node` | A node from `geometry.csv` |
| `direction` | The sensor's positive axis in global coordinates: `+X`, `-Y`, `Z`, … or three components `dx dy dz` (normalized automatically) |
| `role` | `control` for exactly one channel (the input reference); `response` or blank for the rest |

Nodes can have 1, 2 or 3 (or more) sensors. Node motion is solved per node by least squares from its sensors. Directions with no sensor are shown as zero motion.

## `lines.csv`

```
node_a,node_b
1,2
1,5
```

These are display-only edges. Lines can include `base` nodes, for example to draw isolators down to the table.

## Validation the loader performs

| Error | Meaning |
|---|---|
| `Channels in time data but not in channels.csv: [...]` | Name mismatch |
| `channels.csv references nodes missing from geometry.csv` | Node id typo |
| `Need exactly one channel with role=control` | Zero or several control rows |
| `Bad direction '...'` | Not `±X/Y/Z` and not three numbers |
| `Sample rate unknown` | No `fs` anywhere and no `time` column |
