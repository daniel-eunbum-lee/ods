# Input data format

One folder holds **one synchronized run** (one test axis). File names are fixed except for the time file, which `test.json` names. A ready-to-edit set is in [`examples/template/`](../examples/template/).

The Python tool refuses any of these files (and `truth.npz`) if it is a link that leads outside the folder, so a symlinked shared `geometry.csv` kept elsewhere must be copied into the folder instead.

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
| `excitation_axis` | the control channel's direction | `"X"`, `"Y"` or `"Z"` (optionally signed, e.g. `"-Z"`), in global axes. Set it whenever the control isn't mounted along a global axis, so a tilted control is corrected (see [method.md](method.md#2-three-views-of-the-motion)). Any other value is an error |
| `time_file` | first of `time.npz`, `time.mat`, `time.csv` that exists (MATLAB: `time.mat`, `time.csv`) | A relative path inside the test folder, subfolders allowed (`raw/run3.csv`), ending in `.npz` (Python only), `.mat` or `.csv`. Absolute paths, network (UNC) paths, `..`, Windows device names (`NUL`, `CON`, `COM1`, …) and (Python) links that lead outside the folder are rejected, because a test folder may come from someone else |

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

From a MAT file only `data`, `channels` and `fs` are read; `data` and `fs` must be numeric and `channels` text. A time file whose `data`, `channels` and `fs` would take more than 8 GiB in memory (about 10⁹ samples as double) is refused before loading: the size comes from the file's headers (NPZ, MAT) or is estimated from the first lines (CSV). For a compressed MAT file the size is the one the file *declares*, so a deliberately crafted file can still use more memory than it declares; the limit protects against honest mistakes and oversized files, not against that. Raise `ods.io.MAX_TIME_DATA_BYTES` (Python) or the limit in `loadTest.m` (MATLAB) if you really need more. (GNU Octave reads a MAT file in full to list it, so there the check comes after reading.)

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
| `x, y, z` | Global coordinates, finite numbers. Any length unit works as long as it's consistent; it only affects the drawing and the rigid-body fit |
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
| `excitation_axis must be X, Y or Z (optionally signed)` | `excitation_axis` in `test.json` is something else (e.g. `"vertical"` or a number). Use `null` or leave it out to take the control's direction |
| `time_file must be a relative path inside the test folder` / `must end in ...` / `must not name a Windows device` | `time_file` is absolute, a network path, contains `..`, names a device, or has another extension |
| `... is a link to a file outside the test folder` | (Python) A file in the folder is a symbolic link to somewhere else |
| `holds more than one variable named data` | (Python) A MAT file with duplicate variables |
| `time data would take ... GiB, above the ... limit` | The time file declares more data than the memory limit (see [Time histories](#time-histories)) |
| `geometry.csv has non-finite coordinates` (MATLAB: `non-numeric or non-finite values`) | A coordinate is `nan` or `inf`; in MATLAB also a node id or coordinate that is not a number |
| `variable "..." has class ...` (MATLAB also: `"data" and "fs" must be numeric`) | A MAT file holds something other than numbers in `data`/`fs` or text (cell or char) in `channels` |
