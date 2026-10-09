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
