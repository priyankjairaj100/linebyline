#!/usr/bin/env python3
"""Inspect keys/shapes/types of canonical forecast and VBI archives.

Creates a small JSON file. Does not copy or upload numerical arrays.
Uses NumPy only, and loads each compressed array separately to read its shape.
No checkpoint unpickling or model retraining is performed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path.home() / "Downloads" / "btpit_stage4_update_bundle"
FILES = [
    "outputs/forecast_benchmark_seed13/canonical_seed13_split_and_test600.npz",
    "outputs/forecast_benchmark_seed13/canonical_seed13_genuine_physics.npz",
    "outputs/forecast_benchmark_seed13/final_forecast_predictions_seed13_test600.npz",
    "outputs/forecast_benchmark_seed13/forecast_predictions_clean_seed13_test600.npz",
    "outputs/forecast_benchmark_seed13/vbi_input_A_persistence_physics_residual.npz",
    "outputs/forecast_benchmark_seed13/vbi_input_B_convlstm_transformer_direct.npz",
    "outputs/forecast_benchmark_seed13/vbi_input_C_residual_support_consistency.npz",
    "outputs/forecast_benchmark_seed13/stage5_seed13_clean_residual/stage5_test_predictions_full.npz",
    "outputs/stage6_vbi_seed13_test600_A/stage6_v3_bridge_responses.npz",
    "outputs/stage6_vbi_seed13_test600_B/stage6_v3_bridge_responses.npz",
    "outputs/stage6_vbi_seed13_test600_C_support_consistent/stage6_v3_bridge_responses.npz",
]
SAMPLE_ID_KEYS = {"abs_ids", "archive_index", "indices", "test_indices",
                  "test_idx", "sample_indices", "scenario_ids", "scenario_id"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    root = args.root.resolve()
    dest = args.out or root / "CANONICAL_NPZ_SCHEMA.json"
    report = {"root": str(root), "files": []}

    for relative in FILES:
        path = root / relative
        item = {"relative_path": relative, "exists": path.is_file(), "arrays": []}
        if not path.is_file():
            report["files"].append(item)
            continue
        item["size_bytes"] = path.stat().st_size
        try:
            with np.load(path, allow_pickle=False) as archive:
                for key in archive.files:
                    try:
                        arr = archive[key]
                        desc = {"key": key, "shape": list(arr.shape), "dtype": str(arr.dtype)}
                        if key.lower() in SAMPLE_ID_KEYS and arr.size <= 200000:
                            # Record only a short sample identity preview.
                            desc["first_ids"] = arr.reshape(-1)[:6].tolist()
                            desc["last_ids"] = arr.reshape(-1)[-6:].tolist()
                        item["arrays"].append(desc)
                        del arr
                    except Exception as error:
                        item["arrays"].append({"key": key, "inspection_error": str(error)})
        except Exception as error:
            item["error"] = str(error)
        report["files"].append(item)
        print(f"{'OK' if 'error' not in item else 'ERROR'}: {relative}")
        for a in item["arrays"]:
            print("   ", a.get("key"), a.get("shape"), a.get("dtype"), a.get("inspection_error", ""))

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved small metadata-only report: {dest}")


if __name__ == "__main__":
    main()
