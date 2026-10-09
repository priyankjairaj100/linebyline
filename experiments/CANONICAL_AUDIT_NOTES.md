# BT-PIT / VBI: canonical code audit (9 October 2026)

Scope: assessment of the five user-uploaded Python source files for the additional journal experiments.
**This is not an executed empirical result or a complete audit of the 600-window canonical solver.**

## Critical finding: legacy Stage 6 differs from manuscript

Uploaded \`btpit_stage6_vbi_response_coupling.py\` is self-described as a lightweight downstream modal Euler--Bernoulli beam test. Defaults:
- bridge_length_m = 500, dt_s = 0.5, n_modes = 6, damping_ratio = 0.02
- modal properties from the ideal simply supported beam, omega proportional to n^2
- mass/stiffness/damping are mode-diagonal scalars; no lane-equivalent vehicle vertical DOF in the solver

The manuscript uses a 318 m structural span, 0.02 s integration, five prescribed frequencies, zero structural damping, and a coupled bridge/lane-equivalent-vehicle formulation.

**Do not run the new manuscript experiments with the uploaded old Stage 6 script.**

The local inventory contains canonical outputs:
- \`outputs/stage6_vbi_seed13_test600_A/stage6_v3_*\`
- \`outputs/stage6_vbi_seed13_test600_B/stage6_v3_*\`
- \`outputs/stage6_vbi_seed13_test600_C_support_consistent/stage6_v3_*\`

We need the **actual script implementing stage6_v3**, its configuration and saved canonical arrays to reproduce Tables II--III.

## Code-to-manuscript discrepancies requiring verification

1. Stage 5 occupancy probability is implemented by clamping predicted normalized occupancy count times its normalization factor; the manuscript describes a distinct sigmoid logit.
2. Stage 5 empty-cell loss penalizes occupancy when both data and physics target are empty, rather than a squared weight-channel penalty across all reference-empty cells as in the manuscript.
3. Stage 5 load conservation compares total weight per frame summed across lane and space, rather than the manuscript's per-position longitudinal load target.
4. The Step 3 physics rollout carries forward vehicles in the last observed state and removes exits, but adds no new arrivals. The dataset describes future vehicle arrivals.
5. The uploaded \`btpit_synthetic_data_generator(1).py\` contains only a comment; it is not the generator.
6. The Step 3 trajectory loader does not request the \`min_gap_m\` field in \`usecols\`, although the vehicle initialization supports that field. It consequently uses a default; this could contribute to physics forecast mismatch.
7. In old Stage 6, the occupancy threshold is applied to the denormalized count channel, whereas Stage 5 threshold sweeps evaluate the normalized count channel. Reusing thresholds without conversion can change the mask. The actual v3 preprocessing needs to be verified.
8. Stage 4 and Stage 5 are different training formulations. Confirm the canonical seed-13 model checkpoint/config before comparing manuscript losses against code.

## Immediate next step

Run \`experiments/collect_canonical_review.ps1\` on the local project and upload \`BT_PIT_CANONICAL_METADATA.zip\`. This package collects canonical configs, manifests, per-window metrics and script candidates, but excludes large arrays, trajectories and checkpoints.

Next identify and upload the actual v3 VBI source. Then select canonical data arrays based on their keys, sample identity and format. We must verify all sample-to-scenario correspondence before drawing confidence intervals.

## Planned empirical additions

1. Raw Residual vs Support-Consistent Residual vs frame-total-matched scaled raw loads.
2. Random-mask controls matched for number or amount of removed loads, with reproducible seeds.
3. Paired scenario-cluster bootstrap confidence intervals (37 held-out test scenarios).
4. Forecast mismatch diagnostics, separating existing-vehicle continuation from unobserved arrivals, using original trajectory IDs.
5. VBI damping and structural-step convergence; finer traffic sampling only if genuine higher-resolution trajectories/loads are available.

For all variants: freeze canonical split, same shared observed-history initialization, same solver and reference, report both pooled metrics and paired scenario-level metrics, preserve raw outputs and configs.


## Canonical metadata export findings (9 October 2026)

This section is grounded in the user's \`BT_PIT_CANONICAL_REVIEW.txt\`, which exports the 600-window metadata and scenario-level results. These are previously computed outputs; no VBI experiment was rerun here.

### Configuration and split
- A, B and C have identical VBI config JSON: L=318 m, modal frequencies [0.758, 1.533, 2.345, 3.506, 4.022] Hz, structural_dt=0.02 s, traffic_dt=0.5 s, bridge_damping=0, m_ref=63294 kg, k_ref=1903172 N/m, c_ref=7882 N s/m, beta=.25, gamma=.5, max_iter=8, tol=1e-8.
- The manifest maps archive_index 0--599 to 37 scenario IDs and time-window starts.
- Saved Stage-5 residual occupancy calibration chose threshold 0.23 (normalized occupancy channel). The canonical residual has lambda_occ_bce=.25 and lambda_empty=1.2, not the uploaded script's defaults.

### Structural three-way comparison

| Saved group / internal key | Interpreted model identity (matches manuscript metric signature) | Mean disp RMSE (L/2, mm) | Mean acc RMSE (m/s^2) |
|---|---|---:|---:|
| A: persistence | Persistence | 4.3922 | 0.028118 |
| A: physics_teacher | Physics-Based | 3.4270 | 0.026938 |
| A: residual_btpit | Raw Residual | 4.2193 | 0.055189 |
| B: persistence | ConvLSTM | 7.2359 | 0.100555 |
| B: physics_teacher | Transformer | 5.1603 | 0.079210 |
| B: residual_btpit | Direct Prediction | 5.1357 | 0.086900 |
| C: persistence | Raw Residual | 4.2193 | 0.055189 |
| C: physics_teacher | Physics-Based | 3.4270 | 0.026938 |
| C: residual_btpit | Support-Consistent Residual | 3.7266 | 0.032129 |

**CAUTION:** These B aliases are deduced by exact metric matching to manuscript Table III. Need canonical NPZ schema / keys for independent identity verification. Do not rely on the generic \`model\` column at face value.

A raw residual has mean per-window total-load RMSE 447.41 kN; C support-consistent mean per-window total-load RMSE 812.01 kN. These are averaged per-window RMSEs, a different aggregation from Table II's full-pool total-load RMSE 512.02 kN. At the 15 s horizon, the saved removal diagnostic reports 56.70% predicted load removed.

### Scenario-level exploratory paired analysis

Computed from the existing \`R4_support_consistency/paired_scenario_errors.csv\`, 37 independent scenarios, 20,000 resampled scenario clusters. Positive = raw error minus support-consistent error.

| Metric | Mean improvement | 95% bootstrap CI (approx, deterministic LCG) | Wins / 37 | Mean excluding S0219 |
|---|---:|---|---:|---:|
| disp_L2_rmse_mm | +0.4337 mm | [-0.4211, +1.5997] | 20 | -0.0181 mm |
| acc_L2_rmse_mps2 | +0.02162 | [+0.00585, +0.04841] | 21 | +0.00988 |
| peak_disp_L2_error_mm | +1.8692 | [+0.3528, +4.0940] | 27 | +0.9435 mm |

The unweighted scenario estimand differs from the 600-window pooled one. Displacement-RMSE advantage is strongly affected by scenario S0219; cannot claim uniform scenario-wise improvements. Python reproducibility script added at \`experiments/analyze_support_scenarios.py\` (uses NumPy's seeded generator; its intervals will vary slightly from this preliminary JS bootstrap).

### Provenance discrepancies to resolve

1. A \`forecast_metrics_seed13_test600.csv\` has \`IDM/MOBIL\` exactly equal to \`Persistence\`, and a raw residual row with FPR .9975. The paper-facing \`paper_figures_vbi/forecast_metrics_table.csv\` reports Physics rollout global RMSE .1310 and Residual forecast global RMSE .1568. These two tables correspond to different evaluation stages; they must not be merged without tracing the forecast archive.
2. The saved paper-facing residual occupancy metrics are F1=.509625 and FPR=.071744, whereas manuscript Table II reports F1=.5370 and FPR=.0334. This likely involves a later calibration/evaluation pass but is **not resolved** by the metadata export.
3. \`SCRIPT_CANDIDATES.csv\` found only legacy \`scripts/btpit_stage6_vbi_response_coupling.py\` inside the bundle. No canonical v3 solver source appears in its Python/PowerShell file inventory. Search other local project folders / chat exports before implementing further VBI experiments.

### Created reproducibility assets

- \`experiments/analyze_support_scenarios.py\`: scenario bootstrap, leave-one-out influence, saves CSV.
- \`experiments/inspect_canonical_npz.py\`: inspect saved NPZ array keys/shapes and ID previews without uploading arrays.
- \`experiments/find_canonical_v3_source.ps1\`: read-only search under local Downloads/Desktop for actual v3 solver.

**Next decision gate:** Recover the real canonical v3 source OR reconstruct it and verify exact numerical agreement to the saved A/B/C reference responses before running any new load-matched/damping/time-step controls. Also inspect key names and IDs to prevent false experiment alignment.
