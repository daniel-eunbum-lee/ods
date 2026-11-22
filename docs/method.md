# Method

This is what the tool computes, why, and how it was validated. Notation:
- b(t): control (table) acceleration
- xᵢ(t): response channel i
- dᵢ: sensor direction (unit vector)
- e: excitation axis
- ω = 2πf

References in brackets are listed in [references.md](references.md).

## ODS vs. modal analysis

An **operating deflection shape** is how the structure actually moved at one frequency in this test. It includes every mode that contributes there, any forced response, and fixture motion. A **mode shape** is a property of the structure alone, extracted by fitting [Richardson 1997]. This tool produces ODS. When a resonance is well separated, the ODS at its peak closely matches the mode shape (see [Validation](#validation)). When modes are close together, it shows their mix, and that is what the hardware actually did.

On a shaker the input is measured, so this tool uses **transmissibility** to the control accelerometer. That removes the shaped test profile from the shapes. Output-only OMA [Brincker & Ventura 2015] isn't needed.

## 1. Spectra and H1 transmissibility

Welch averaging [Welch 1967] uses a Hann window, 50 % overlap, and constant detrending per segment, with nfft = the smallest power of two giving Δf ≤ `--df`.

```
Tᵢ(f)  = g · G_bxᵢ(f) / G_bb(f)                 (H1 estimator; g = d_ctrl·e, see §2)
γ²ᵢ(f) = |G_bxᵢ|² / (G_bb · G_xᵢxᵢ)              (ordinary coherence)
```

H1 is unbiased by noise on the response channels and biased low by noise on the control channel [Bendat & Piersol 2010]. A clean control accelerometer makes that bias negligible. Coherence below 1 flags noise, nonlinearity (rattles, gaps), leakage at sharp peaks, or a second unmeasured input. T is dimensionless (g/g), and complex: it has magnitude and phase.

## 2. Three views of the motion

| View | Per channel | What it shows |
|---|---|---|
| Absolute | Tᵢ | Total measured motion, including the table |
| Relative to table | Tᵢ − dᵢ·e | Motion relative to the fixture |
| Elastic | R · (T − d·e) over the response channels | Deformation only: rigid-body motion removed |

**Relative.** The table moves rigidly at T = 1 along e. A sensor reads the table's contribution as dᵢ·e. So "T − 1" is correct only for sensors parallel to the excitation; cross-axis sensors subtract nothing, and skewed ones subtract their projection.

The control itself reads g = d_ctrl·e of the table acceleration (−1 if mounted upside down, 0.8 if tilted 37°). The raw H1 against it is therefore T_true/g, so the pipeline multiplies H1 by g to make every T per unit table acceleration. The control's own column then reads g, and its relative motion is 0. A control more than 60° off the excitation axis (|g| < 0.5) is rejected as a probable setup error. This assumes the table moves only along e: any cross-axis table motion leaks into a tilted control in proportion to the sine of the tilt angle. (A closed-loop controller that uses a tilted control also overdrives the table by 1/|g|.)

**Elastic.** A small rigid motion (translation t, rotation θ) is seen by a sensor at pᵢ (taken about the centroid) as

```
dᵢ·t + dᵢ·(θ × pᵢ) = dᵢ·t + θ·(pᵢ × dᵢ)
```

Stacking rows [dᵢ, pᵢ × dᵢ] gives A (k × 6). The projector R = I − A A⁺ removes the least-squares rigid-body part. It needs at least 6 channels, spread out so all six motions are observable. With fewer, the pseudo-inverse removes only what it can observe.

**Why not always use Relative?** On an isolated unit, above the isolation frequency the unit barely moves, so T ≈ 0 and T − 1 ≈ −1 on every Z sensor. What you then see is the table moving under a still unit. That flat "floor" hides elastic resonances. The Elastic view removes it, and peak picking uses Absolute T (§4).

## 3. Displacement

Converting in the frequency domain is exact for a steady-state harmonic, and avoids the drift you get from integrating in time:

```
u(f) = T_view(f) · g₀ / (−ω²)        [m per g]  → reported in mm per g of table input
```

(g₀ = 9.80665 m/s² when units are g, and 1 when units are m/s².) The DC bin is set to 0. Per node, k sensors give D u = s, solved as u = D⁺ s. That's least squares for ≥ 3 non-coplanar sensors; with fewer, unmeasured directions come out as zero. The animation draws Re{u · e^{jφ}} for φ going from 0 to 2π.

## 4. Peak picking

A peak indicator is formed as the channel norm of the absolute transmissibility, ‖T(f)‖ = √Σ|Tᵢ|². With a single reference this plays the role of a CMIF. Peaks are found with `scipy.signal.find_peaks` and must pass four gates:

- inside `[fmin, fmax]` (the search runs on the whole curve and out-of-band peaks are dropped afterwards, so a band edge on a slope is never reported as a peak);
- prominence ≥ `--prominence` dB;
- at least 3 Hz from any higher peak (within 3 Hz only the highest survives);
- |T|²-weighted coherence ≥ `--min-coh`.

The weighting asks whether the channels that carry the shape are trustworthy. An unweighted mean gets dragged down by quiet channels sitting at their noise floor.

## 5. MPC and MAC

**MPC** (modal phase collinearity) [Pappa et al. 1993] measures whether a complex shape vector is a standing wave. Points that all lie on one line through the origin of the complex plane give MPC = 1. It is computed from the eigenvalues λ₁ ≥ λ₂ of the 2×2 covariance of (Re, Im):

```
MPC = ((λ₁ − λ₂) / (λ₁ + λ₂))²
```

It's deliberately not mean-centred, because the line must pass through the origin. MPC = 1 is a standing wave; values near 0 look like a travelling wave, which points to closely spaced modes or non-proportional damping.

**MAC** (modal assurance criterion) [Allemang & Brown 1982] measures how alike two shapes are:

```
MAC(a, b) = |aᴴb|² / ((aᴴa)(bᴴb))
```

## Validation

### Analytical benchmark: base-driven cantilever

The first check is against a textbook problem with an exact answer. A uniform Euler–Bernoulli cantilever (aluminium strip, 200 × 25 × 3 mm, hysteretic loss factor η = 0.04) is clamped to the table and driven along Z. Its absolute transmissibility is exact in closed form, with λ = βL, β⁴ = ρAω² / (EI(1 + jη)) and ξ = x/L:

```
T(ξ) = ½(cosh λξ + cos λξ)
       + [sinh λ sin λ (cosh λξ − cos λξ) − (cosh λ sin λ + cos λ sinh λ)(sinh λξ − sin λξ)] / (2(1 + cos λ cosh λ))
```

The denominator vanishes on the cantilever frequency equation 1 + cos λ cosh λ = 0 (λₙ = 1.8751, 4.6941, 7.8548 [Blevins 1979]), giving 61.7, 386.6 and 1082.5 Hz in the 20–1500 Hz band. The test suite first verifies the formula itself: against Blevins' roots, a direct 4 × 4 boundary-value solve (to 1e-8) and a 64-mode modal sum (to 2e-5).

60 s of white base acceleration is passed through T exactly, 1e-3 g rms sensor noise is added to every channel, and the files go through the normal load → run → export path at Δf = 0.3125 Hz (36 averages). The normalised-error band follows from estimation theory; the other limits are empirical, set with margin over 82 independent seeds:

| Check | Limit | Worst of 82 seeds |
|---|---|---|
| \|T − T_exact\| / \|T_exact\| away from resonances (±3 half-power bandwidths): median / p99 / max | 0.1 % / 1.2 % / 8 % | 0.033 % / 0.66 % / 5.8 % |
| Phase error away from resonances | 4° | 2.6° |
| Error normalised by the theoretical random error [Bendat & Piersol 2010]: p95, p99 (Rayleigh: 1.73, 2.15) | 1.65–1.95, 2.05–2.50 | 1.77–1.83, 2.21–2.31 |
| Peaks found | exactly the 3 modes | always 3 |
| Peak frequency vs fₙ | max(1.5 Δf, 0.1 ηfₙ) | 0.19, 0.66, 1.57 Hz |
| 1 − MAC, measured vs exact ODS at each peak | 1e-5 | 2.2e-6 |
| Tip amplitude at each peak (also in `ods_peaks.csv`, mm/g) | 8 %, 1.5 %, 1.5 % | 5.3 %, 0.74 %, 0.39 % |

The normalised-error check is the strictest. Its centre sits a few % above the Rayleigh values because the random-error formula is a large-sample one and coherence estimated from 36 averages reads slightly high. It passes only if H1 is unbiased, so a wrong spectral convention or scaling shows up even where the absolute error looks small. The looser limit on the first peak is real estimator behaviour, not slack. That peak is only about 8 bins wide, so the Hann window smears it and the coherence dips there. The Hann window alone biases a peak low by about 7 % at 4 bins across its half-power bandwidth and about 2 % at 8 bins. Random error comes on top, which is why the first peak reads 0.2–5.3 % low here. So the [Resolution](#assumptions-and-limits) minimum of 3 bins is not enough for accurate amplitudes.

The test was also checked against planted bugs. It fails for a conjugated cross-spectrum, a mis-scaled H1, a half-bin frequency shift, a missing g → m/s² or 2π factor in the displacement, and a wrong table subtraction in the relative view. Picking peaks on relative T is invisible on a cantilever (the peaks coincide), but the box-model tests below catch it.

### Synthetic box on isolators

The synthetic model ([`src/ods/synth.py`](../src/ods/synth.py)) is a 9-node lumped-mass box on 4 isolators:

| Part | Values |
|---|---|
| Box | 0.30 × 0.20 × 0.15 m, 3.8 kg; 0.8 kg extra on one top corner (CG offset) |
| Isolators | k = 50/50/120 kN/m (x/y/z) per corner |
| Box structure | Bar springs (edges + face diagonals) |
| Top panel | Centre node on soft-Z bushings |
| Damping | Modal: 4 % below 200 Hz, 2 % above |

Its transmissibility is exact in closed form:

```
T(ω) = r + ω² Σₙ φₙ (φₙᵀ M r) / (ωₙ² − ω² + 2jζₙωₙω)
```

The base input is complex-Gaussian random with the NAVMAT P-9492 shape [NAVMAT 1979]: +3 dB/oct over 20–80 Hz, 0.04 g²/Hz over 80–350 Hz, −3 dB/oct over 350–2000 Hz, 6.06 grms. Each channel gets 1e-6 g²/Hz of white sensor noise. The run used 60 s at 5120 Hz, Δf = 0.625 Hz and 74 averages:

| ODS peak (Hz) | True fₙ (Hz) | MAC, Absolute | MAC, Relative | MAC, Elastic | MPC | γ² weighted |
|---:|---:|---:|---:|---:|---:|---:|
| 54.38 | 54.60 (bounce) | 0.998 | **0.999** | 1.000 | 0.992 | 0.978 |
| 77.50 | 77.70 (rock) | **0.928** | 0.774 | 0.791 | 0.740 | 0.990 |
| 222.50 | 222.75 | **0.681** | 0.016 | 0.467 | 0.158 | 0.994 |
| 282.50 | 283.34 (panel) | 0.982 | 0.155 | **0.999** | 0.933 | 0.995 |
| 348.12 | 348.69 | 0.932 | 0.033 | **0.960** | 0.766 | 0.994 |
| 531.25 | 531.79 | 0.909 | 0.004 | **0.963** | 0.740 | 0.969 |
| 631.25 | 633.38 | 0.675 | 0.002 | **0.831** | 0.226 | 0.856 |
| 733.12 | 734.78 | 0.873 | 0.002 | **0.942** | 0.653 | 0.875 |
| 985.00 | 983.31 | 0.889 | 0.032 | **0.898** | 0.734 | 0.952 |
| 1296.88 | 1300.95 | 0.977 | 0.002 | **0.985** | 0.932 | 0.935 |
| 1621.25 | 1621.87 | 0.618 | 0.000 | **0.698** | 0.218 | 0.506 |

(For the Elastic column, MAC is computed after removing rigid-body motion from the true mode too.) What the table shows:

- Every peak lands within 0.4 % of a true mode (up to about 6 bins at 1.3 kHz), offset partly by the bin spacing, the Hann window and neighbouring modes.
- Relative is the right view for the rigid-body bounce. Above isolation it collapses to the table floor (MAC ≈ 0), exactly as §2 predicts.
- Where modes are well separated, the Elastic view matches the true shape with MAC ≥ 0.94.
- Low MPC flags the peaks where nearby modes mix (77.5, 222.5, 631 Hz), and those also have lower MAC. That's the ODS honestly showing a mix, not an error.

The pytest suite ([`tests/test_ods.py`](../tests/test_ods.py)) checks all of this. It compares H1 against the analytic SDOF transmissibility and checks unit scaling (1 g at 10 Hz = 2.484 mm). It also checks rigid-body removal and the CSV/NPZ loaders, and runs end to end on a 20 s synthetic test with MAC thresholds.

## Assumptions and limits

- **Linear, stationary, steady-state response.** Rattles, gaps and amplitude-dependent isolators show up as low coherence.
- **Single input along one axis per run.** Shapes from separate runs can't be combined unless they share a common reference.
- **ODS, not modes.** For modal parameters (fₙ, ζ, clean shapes for FE correlation), fit the transmissibilities with a modal-fit tool, e.g. MATLAB `modalfit` or a rational-fraction / pLSCF fit.
- **Resolution.** For a lightly damped peak the half-power bandwidth is 2ζfₙ. Use ≥ 3 bins across it, or the peak will be under-resolved and its amplitude biased low. The Hann window alone reads the peak about 7 % low at 4 bins and about 2 % low at 8 bins, before random error (see the cantilever benchmark).
- **Partly instrumented nodes** are drawn with zero motion in unmeasured directions. That's a display assumption, not a measurement.
