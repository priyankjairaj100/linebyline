#!/usr/bin/env python3
"""Paired 37-scenario analysis for the canonical BT-PIT Raw/Support-Consistent VBI study.

Reanalyzes EXISTING saved results; it does not run a structural solver.
Primary estimand: unweighted mean over independent test scenarios of
(raw scenario mean error - support-consistent scenario mean error).
Positive = support-consistent has lower error. This is different from
window-weighted or pooled-time-series RMSE in manuscript Table III.

Example:
  py experiments/analyze_support_scenarios.py --root "$HOME/Downloads/btpit_stage4_update_bundle"
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RELATIVE = Path("outputs/paper_additional_clusters_only/R4_support_consistency/paired_scenario_errors.csv")
DEFAULT_ROOT = Path.home() / "Downloads" / "btpit_stage4_update_bundle"


def analyze(df: pd.DataFrame, bootstrap_repeats: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {"scenario_id", "metric", "raw", "support_consistent"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    if df.duplicated(["scenario_id", "metric"]).any():
        raise ValueError("Duplicate scenario/metric combinations; cannot perform paired analysis.")
    if df[list(required)].isna().any().any():
        raise ValueError("Missing scenario IDs, metric names, or paired errors.")

    scenario_sets = [set(g.scenario_id) for _, g in df.groupby("metric")]
    if scenario_sets and any(s != scenario_sets[0] for s in scenario_sets):
        raise ValueError("Different scenarios appear for different metrics.")

    summary = []
    influence = []
    for metric, group in df.groupby("metric", sort=True):
        group = group.sort_values("scenario_id").reset_index(drop=True)
        scenarios = group.scenario_id.astype(str).to_numpy()
        raw = group.raw.to_numpy(dtype=np.float64)
        masked = group.support_consistent.to_numpy(dtype=np.float64)
        difference = raw - masked  # positive means the mask helps
        if not np.isfinite(difference).all():
            raise ValueError(f"Non-finite differences in {metric}")

        n = len(group)
        # Resample independent scenario clusters, not their overlapping windows.
        rng = np.random.default_rng(seed)
        means = np.empty(bootstrap_repeats, dtype=np.float64)
        for i in range(bootstrap_repeats):
            idx = rng.integers(0, n, size=n)
            means[i] = float(np.mean(difference[idx]))
        lo, hi = np.quantile(means, [0.025, 0.975])

        full_mean = float(difference.mean())
        excluded = difference[scenarios != "S0219"]
        summary.append(
            {
                "metric": metric,
                "n_scenarios": n,
                "raw_scenario_mean": float(raw.mean()),
                "support_scenario_mean": float(masked.mean()),
                "improvement_raw_minus_support": full_mean,
                "ci95_low": float(lo),
                "ci95_high": float(hi),
                "scenarios_improved": int(np.sum(difference > 0)),
                "scenarios_worsened": int(np.sum(difference < 0)),
                "scenarios_tied": int(np.sum(difference == 0)),
                "exclude_S0219_mean_improvement": float(excluded.mean()) if len(excluded) else np.nan,
                "bootstrap_repetitions": bootstrap_repeats,
                "bootstrap_seed": seed,
            }
        )
        for i, scenario in enumerate(scenarios):
            others = np.delete(difference, i)
            influence.append(
                {
                    "metric": metric,
                    "excluded_scenario_id": scenario,
                    "scenario_improvement": float(difference[i]),
                    "full_mean_improvement": full_mean,
                    "leave_one_out_mean_improvement": float(others.mean()) if len(others) else np.nan,
                    "change_after_exclusion": float(others.mean() - full_mean) if len(others) else np.nan,
                }
            )

    summary_df = pd.DataFrame(summary)
    influence_df = pd.DataFrame(influence)
    return summary_df, influence_df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--source", type=Path, default=None,
                    help="Optional direct path to paired_scenario_errors.csv")
    ap.add_argument("--out_dir", type=Path, default=None)
    ap.add_argument("--bootstrap", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=20261009)
    args = ap.parse_args()
    if args.bootstrap < 100:
        ap.error("--bootstrap must be >= 100")

    source = args.source if args.source is not None else args.root / RELATIVE
    if not source.is_file():
        raise SystemExit(f"Required saved results missing: {source}")

    output = args.out_dir or (args.root / "outputs" / "journal_revision" / "scenario_uncertainty")
    output.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(source)
    summary, influence = analyze(df, args.bootstrap, args.seed)

    summary.to_csv(output / "scenario_cluster_bootstrap.csv", index=False)
    influence.to_csv(output / "scenario_leave_one_out.csv", index=False)
    print("\nPaired scenario-cluster analysis (positive improvement favors masking):")
    print(summary.to_string(index=False, float_format=lambda v: f"{v:.6f}"))
    print("\nLargest single-scenario influences:")
    for metric, sub in influence.groupby("metric"):
        print(f"\n{metric}")
        print(sub.assign(abs_impact=sub.change_after_exclusion.abs())
              .nlargest(5, "abs_impact")
              [["excluded_scenario_id", "scenario_improvement", "leave_one_out_mean_improvement"]]
              .to_string(index=False, float_format=lambda v: f"{v:.6f}"))
    print(f"\nSaved outputs to: {output}")
    print("Interpretation: exploratory reanalysis of saved scenario-level scores;")
    print("not a new VBI experiment, and not a load-matched causal control.")


if __name__ == "__main__":
    main()
