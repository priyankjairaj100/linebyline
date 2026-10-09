#!/usr/bin/env python3
from __future__ import annotations

import argparse, importlib.util, json, math, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

EPS = 1e-12

def load_solver(path: Path):
    spec = importlib.util.spec_from_file_location("vbi_v3", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load solver: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def denorm_sample(arr, scales):
    return np.asarray(arr, dtype=np.float64) * np.asarray(scales, dtype=np.float64).reshape(1,1,1,-1)

def q(arr, p):
    return float(np.quantile(np.asarray(arr, dtype=float), p))

def bootstrap_mean(diff, B=20000, seed=20261009):
    x=np.asarray(diff,float)
    rng=np.random.default_rng(seed)
    vals=np.empty(B)
    n=len(x)
    for b in range(B):
        vals[b]=x[rng.integers(0,n,size=n)].mean()
    return float(x.mean()), q(vals,.025), q(vals,.975)

def per_window_metrics(gt_d,gt_a,pd_,pa):
    gd=gt_d*1000.0; pp=pd_*1000.0
    return {
        "disp_L4_rmse_mm": float(np.sqrt(np.mean((pp[:,0]-gd[:,0])**2))),
        "disp_L2_rmse_mm": float(np.sqrt(np.mean((pp[:,1]-gd[:,1])**2))),
        "disp_3L4_rmse_mm": float(np.sqrt(np.mean((pp[:,2]-gd[:,2])**2))),
        "acc_L2_rmse_mps2": float(np.sqrt(np.mean((pa[:,1]-gt_a[:,1])**2))),
        "peak_disp_L2_error_mm": float(abs(np.max(np.abs(pp[:,1]))-np.max(np.abs(gd[:,1])))),
    }

def make_matched(raw_y, support_y, weight_idx):
    y=np.array(raw_y, dtype=np.float64, copy=True)
    rw=np.clip(y[...,weight_idx],0,None)
    sw=np.clip(np.asarray(support_y,dtype=np.float64)[...,weight_idx],0,None)
    rt=rw.sum(axis=(1,2))
    st=sw.sum(axis=(1,2))
    factors=np.zeros_like(rt)
    nz=rt>EPS
    factors[nz]=st[nz]/rt[nz]
    rw=rw*factors[:,None,None]
    impossible=(~nz)&(st>EPS)
    if np.any(impossible):
        # No raw spatial support exists; an exactly load-matched spatial scaling is undefined.
        # Leave zero and report count. This is conservative and auditable.
        rw[impossible]=0.0
    y[...,weight_idx]=rw
    return y, int(impossible.sum())

def load_manifest(root: Path):
    p=root/"outputs/forecast_benchmark_seed13/canonical_test600_manifest.csv"
    if not p.is_file(): raise FileNotFoundError(p)
    d=pd.read_csv(p)
    if len(d)!=600: raise ValueError(f"Expected 600 manifest rows, got {len(d)}")
    return d

def verify_aliases(root, C):
    ap=root/"outputs/forecast_benchmark_seed13/vbi_input_A_persistence_physics_residual.npz"
    if not ap.is_file(): return {"A_exists":False}
    with np.load(ap,allow_pickle=False) as A:
        checks={
          "C_Ytest_eq_A_Ytest": np.array_equal(C["Y_test"],A["Y_test"]),
          "C_raw_eq_A_residual": np.allclose(C["Y_persistence"],A["Y_pred"],rtol=0,atol=1e-7),
          "C_physics_eq_A_physics": np.allclose(C["Y_phy"],A["Y_phy"],rtol=0,atol=1e-7),
        }
    if not all(checks.values()):
        raise RuntimeError(f"Canonical alias verification failed: {checks}")
    checks["A_exists"]=True
    return checks

def solver_sanity(mod, C, scales, weight_idx, cfg, saved, sample_ids):
    mapping={
      "ground_truth":("Y_test","ground_truth"),
      "raw_residual":("Y_persistence","persistence"),
      "physics_based":("Y_phy","physics_teacher"),
      "support_consistent":("Y_pred","residual_btpit"),
    }
    n_cells=C["X_test"].shape[3]
    phi=mod.phi_matrix(mod.bridge_coordinates(n_cells,500.0,cfg["L"]),cfg["L"],len(cfg["frequencies"]))
    rows=[]
    for i in sample_ids:
        X=denorm_sample(C["X_test"][i],scales)
        for label,(key,saved_key) in mapping.items():
            Y=denorm_sample(C[key][i],scales)
            r=mod.solve_sample(X,Y,weight_idx,phi,cfg)
            sd=saved[f"{saved_key}_disp_high_m"][i]
            sa=saved[f"{saved_key}_acc_high_mps2"][i]
            rows.append({
              "sample":i,"variant":label,
              "max_abs_disp_diff_m":float(np.max(np.abs(r["disp_high"]-sd))),
              "max_abs_acc_diff_mps2":float(np.max(np.abs(r["acc_high"]-sa))),
            })
    df=pd.DataFrame(rows)
    mx=max(df.max_abs_disp_diff_m.max(),df.max_abs_acc_diff_mps2.max())
    if mx>1e-7:
        raise RuntimeError(f"v3 solver does not reproduce canonical responses; max diff={mx:.3e}")
    return df

def run_load_matched(mod,C,scales,weight_idx,cfg,saved,manifest,out):
    cache=out/"load_matched_responses.npz"
    n=len(C["X_test"])
    n_cells=C["X_test"].shape[3]
    phi=mod.phi_matrix(mod.bridge_coordinates(n_cells,500.0,cfg["L"]),cfg["L"],len(cfg["frequencies"]))
    if cache.is_file():
        zz=np.load(cache,allow_pickle=False)
        md=zz["disp_high_m"]; ma=zz["acc_high_mps2"]
        impossible=int(zz["impossible_frames"][0])
        print("Reusing cached load-matched responses.")
    else:
        D=[]; A=[]; impossible=0
        t0=time.time()
        for i in range(n):
            X=denorm_sample(C["X_test"][i],scales)
            raw=denorm_sample(C["Y_persistence"][i],scales)
            sup=denorm_sample(C["Y_pred"][i],scales)
            match,bad=make_matched(raw,sup,weight_idx); impossible+=bad
            r=mod.solve_sample(X,match,weight_idx,phi,cfg)
            D.append(r["disp_high"]); A.append(r["acc_high"])
            if (i+1)%25==0 or i==n-1:
                print(f"load-matched {i+1}/{n} elapsed={time.time()-t0:.1f}s")
        md=np.asarray(D); ma=np.asarray(A)
        np.savez_compressed(cache,disp_high_m=md,acc_high_mps2=ma,impossible_frames=np.array([impossible]))
    ids=np.asarray(C["abs_ids"] if "abs_ids" in C.files else np.arange(n))
    scen=manifest.scenario_id.astype(str).to_numpy()
    gt_d=saved["ground_truth_disp_high_m"]; gt_a=saved["ground_truth_acc_high_mps2"]
    variants={
      "Raw Residual":(saved["persistence_disp_high_m"],saved["persistence_acc_high_mps2"]),
      "Support-Consistent":(saved["residual_btpit_disp_high_m"],saved["residual_btpit_acc_high_mps2"]),
      "Load-Matched Raw":(md,ma),
      "Physics-Based":(saved["physics_teacher_disp_high_m"],saved["physics_teacher_acc_high_mps2"]),
    }
    rows=[]
    loadcheck=[]
    for i in range(n):
        raw=denorm_sample(C["Y_persistence"][i],scales)
        sup=denorm_sample(C["Y_pred"][i],scales)
        match,_=make_matched(raw,sup,weight_idx)
        rtot=np.clip(raw[...,weight_idx],0,None).sum(axis=(1,2))
        stot=np.clip(sup[...,weight_idx],0,None).sum(axis=(1,2))
        mtot=np.clip(match[...,weight_idx],0,None).sum(axis=(1,2))
        loadcheck.append(float(np.max(np.abs(mtot-stot))))
        for name,(d,a) in variants.items():
            m=per_window_metrics(gt_d[i],gt_a[i],d[i],a[i])
            m.update({"window_index":i,"abs_id":int(ids[i]),"scenario_id":scen[i],"method":name})
            rows.append(m)
    per=pd.DataFrame(rows)
    per.to_csv(out/"load_matched_per_window_metrics.csv",index=False)
    summ=per.groupby("method").agg(
      n=("window_index","size"),
      disp_L4_rmse_mm=("disp_L4_rmse_mm","mean"),
      disp_L2_rmse_mm=("disp_L2_rmse_mm","mean"),
      disp_3L4_rmse_mm=("disp_3L4_rmse_mm","mean"),
      acc_L2_rmse_mps2=("acc_L2_rmse_mps2","mean"),
      peak_disp_L2_error_mm=("peak_disp_L2_error_mm","mean"),
    ).reset_index()
    summ.to_csv(out/"load_matched_summary.csv",index=False)
    scenario=per.groupby(["scenario_id","method"],as_index=False)[
      ["disp_L2_rmse_mm","acc_L2_rmse_mps2","peak_disp_L2_error_mm"]
    ].mean()
    scenario.to_csv(out/"load_matched_scenario_means.csv",index=False)
    comps=[]
    metrics=["disp_L2_rmse_mm","acc_L2_rmse_mps2","peak_disp_L2_error_mm"]
    pairs=[("Raw Residual","Support-Consistent"),("Load-Matched Raw","Support-Consistent"),("Raw Residual","Load-Matched Raw")]
    for Aname,Bname in pairs:
        aa=scenario[scenario.method==Aname].set_index("scenario_id")
        bb=scenario[scenario.method==Bname].set_index("scenario_id")
        for metric in metrics:
            dif=(aa[metric]-bb[metric]).sort_index()
            mean,lo,hi=bootstrap_mean(dif.to_numpy())
            comps.append({
              "comparison":f"{Aname} minus {Bname}","metric":metric,"n_scenarios":len(dif),
              "mean_improvement_if_positive":mean,"ci95_low":lo,"ci95_high":hi,
              "scenarios_positive":int((dif>0).sum()),"scenarios_negative":int((dif<0).sum())
            })
    comp=pd.DataFrame(comps)
    comp.to_csv(out/"load_matched_scenario_bootstrap.csv",index=False)
    control={
      "max_frame_total_load_difference_support_vs_matched_kN":float(max(loadcheck)),
      "undefined_raw_zero_support_positive_frames":int(impossible),
    }
    (out/"load_matched_control_check.json").write_text(json.dumps(control,indent=2))
    return summ,comp,control,md,ma

def choose_sensitivity_indices(manifest,k=3):
    idx=[]
    for _,g in manifest.groupby("scenario_id",sort=True):
        a=g.archive_index.to_numpy(dtype=int)
        picks=np.unique(np.round(np.linspace(0,len(a)-1,min(k,len(a)))).astype(int))
        idx.extend(a[picks].tolist())
    return np.array(sorted(set(idx)),dtype=int)

def run_sensitivity(mod,C,scales,weight_idx,cfg0,saved,manifest,matched_d,matched_a,out,k=3):
    chosen=choose_sensitivity_indices(manifest,k)
    pd.DataFrame({"archive_index":chosen,"scenario_id":manifest.set_index("archive_index").loc[chosen].scenario_id.values}).to_csv(out/"sensitivity_subset.csv",index=False)
    n_cells=C["X_test"].shape[3]
    configs=[
      ("base_zeta0_dt0.02",0.0,0.02),
      ("zeta0.01_dt0.02",0.01,0.02),
      ("zeta0.02_dt0.02",0.02,0.02),
      ("zeta0.05_dt0.02",0.05,0.02),
      ("zeta0_dt0.01",0.0,0.01),
      ("zeta0_dt0.005",0.0,0.005),
    ]
    allrows=[]
    for label,zeta,dt in configs:
        print(f"Sensitivity {label}: {len(chosen)} windows")
        if label=="base_zeta0_dt0.02":
            for i in chosen:
                for name,d,a in [
                  ("Raw Residual",saved["persistence_disp_high_m"][i],saved["persistence_acc_high_mps2"][i]),
                  ("Support-Consistent",saved["residual_btpit_disp_high_m"][i],saved["residual_btpit_acc_high_mps2"][i]),
                  ("Load-Matched Raw",matched_d[i],matched_a[i]),
                ]:
                    m=per_window_metrics(saved["ground_truth_disp_high_m"][i],saved["ground_truth_acc_high_mps2"][i],d,a)
                    m.update({"config":label,"zeta":zeta,"structural_dt":dt,"method":name,"window_index":int(i)})
                    allrows.append(m)
            continue
        cfg=dict(cfg0); cfg["bridge_damping"]=zeta; cfg["structural_dt"]=dt
        phi=mod.phi_matrix(mod.bridge_coordinates(n_cells,500.0,cfg["L"]),cfg["L"],len(cfg["frequencies"]))
        t0=time.time()
        for j,i in enumerate(chosen):
            X=denorm_sample(C["X_test"][i],scales)
            gt=denorm_sample(C["Y_test"][i],scales)
            raw=denorm_sample(C["Y_persistence"][i],scales)
            sup=denorm_sample(C["Y_pred"][i],scales)
            match,_=make_matched(raw,sup,weight_idx)
            rg=mod.solve_sample(X,gt,weight_idx,phi,cfg)
            for name,Y in [("Raw Residual",raw),("Support-Consistent",sup),("Load-Matched Raw",match)]:
                rr=mod.solve_sample(X,Y,weight_idx,phi,cfg)
                m=per_window_metrics(rg["disp_high"],rg["acc_high"],rr["disp_high"],rr["acc_high"])
                m.update({"config":label,"zeta":zeta,"structural_dt":dt,"method":name,"window_index":int(i)})
                allrows.append(m)
            if (j+1)%10==0 or j==len(chosen)-1:
                print(f"  {j+1}/{len(chosen)} elapsed={time.time()-t0:.1f}s")
        pd.DataFrame(allrows).to_csv(out/"sensitivity_per_window_partial.csv",index=False)
    df=pd.DataFrame(allrows)
    df.to_csv(out/"sensitivity_per_window.csv",index=False)
    summ=df.groupby(["config","zeta","structural_dt","method"],as_index=False)[
      ["disp_L2_rmse_mm","acc_L2_rmse_mps2","peak_disp_L2_error_mm"]
    ].mean()
    summ.to_csv(out/"sensitivity_summary.csv",index=False)
    return summ

def rank_corr(x,y):
    a=pd.Series(x).rank(method="average").to_numpy()
    b=pd.Series(y).rank(method="average").to_numpy()
    if np.std(a)<EPS or np.std(b)<EPS: return np.nan
    return float(np.corrcoef(a,b)[0,1])

def run_forecast_mismatch(C,scales,weight_idx,manifest,root,out):
    traj=root/"data/btpit_synthetic_bridge_traffic_trajectories.csv"
    if not traj.is_file():
        return {"status":"skipped","reason":f"missing {traj}"}
    header=pd.read_csv(traj,nrows=0).columns.tolist()
    need=["scenario_id","time_idx","vehicle_id","gross_vehicle_weight_kN"]
    if not all(c in header for c in need):
        return {"status":"skipped","reason":f"trajectory missing required columns {need}"}
    use=need+([ "position_m" ] if "position_m" in header else [])
    wanted=set(manifest.scenario_id.astype(str))
    records={}
    for chunk in pd.read_csv(traj,usecols=use,chunksize=250000):
        chunk["scenario_id"]=chunk["scenario_id"].astype(str)
        chunk=chunk[chunk.scenario_id.isin(wanted)]
        if chunk.empty: continue
        for (sid,t),g in chunk.groupby(["scenario_id","time_idx"],sort=False):
            pos=g["position_m"].to_numpy(float) if "position_m" in g else np.full(len(g),np.nan)
            records.setdefault((str(sid),int(t)),[]).extend(list(zip(g.vehicle_id.astype(str),g.gross_vehicle_weight_kN.astype(float),pos)))
    rows=[]
    Tobs=C["X_test"].shape[1]; Tpred=C["Y_test"].shape[1]
    for i,row in manifest.iterrows():
        sid=str(row.scenario_id); start=int(row.start_index); last=start+Tobs-1
        init=records.get((sid,last),[])
        active={v[0] for v in init}
        active_on_bridge={v[0] for v in init if (not np.isfinite(v[2])) or (0<=v[2]<=500)}
        future_total=future_new=0.0; future_count=future_new_count=0
        traj_totals=[]
        for tt in range(start+Tobs,start+Tobs+Tpred):
            rr=records.get((sid,tt),[])
            rr=[v for v in rr if (not np.isfinite(v[2])) or (0<=v[2]<=500)]
            tot=sum(max(0.0,v[1]) for v in rr); new=sum(max(0.0,v[1]) for v in rr if v[0] not in active)
            future_total+=tot; future_new+=new; future_count+=len(rr); future_new_count+=sum(v[0] not in active for v in rr)
            traj_totals.append(tot)
        gt=denorm_sample(C["Y_test"][i],scales)
        phy=denorm_sample(C["Y_phy"][i],scales)
        raw=denorm_sample(C["Y_persistence"][i],scales)
        sup=denorm_sample(C["Y_pred"][i],scales)
        def total(y): return np.clip(y[...,weight_idx],0,None).sum(axis=(1,2))
        g=total(gt); p=total(phy); r=total(raw); s=total(sup)
        rows.append({
          "window_index":int(row.archive_index),"scenario_id":sid,"start_index":start,
          "active_vehicle_ids_last_obs":len(active),"active_on_bridge_last_obs":len(active_on_bridge),
          "future_new_arrival_weight_share":future_new/(future_total+EPS),
          "future_new_arrival_count_share":future_new_count/(future_count+EPS),
          "physics_total_load_rmse_kN":float(np.sqrt(np.mean((p-g)**2))),
          "raw_total_load_rmse_kN":float(np.sqrt(np.mean((r-g)**2))),
          "support_total_load_rmse_kN":float(np.sqrt(np.mean((s-g)**2))),
          "trajectory_vs_matrix_gt_total_load_rmse_kN":float(np.sqrt(np.mean((np.asarray(traj_totals)-g)**2))),
        })
    df=pd.DataFrame(rows)
    df.to_csv(out/"forecast_mismatch_per_window.csv",index=False)
    x=df.future_new_arrival_weight_share.to_numpy()
    stats={"status":"ok","n_windows":len(df)}
    for col in ["physics_total_load_rmse_kN","raw_total_load_rmse_kN","support_total_load_rmse_kN"]:
        y=df[col].to_numpy()
        stats[f"pearson_arrival_share_vs_{col}"]=float(np.corrcoef(x,y)[0,1])
        stats[f"spearman_arrival_share_vs_{col}"]=rank_corr(x,y)
    stats["mean_future_new_arrival_weight_share"]=float(df.future_new_arrival_weight_share.mean())
    stats["median_trajectory_vs_matrix_gt_rmse_kN"]=float(df.trajectory_vs_matrix_gt_total_load_rmse_kN.median())
    try:
        df["arrival_share_quartile"]=pd.qcut(df.future_new_arrival_weight_share,4,duplicates="drop")
        qsum=df.groupby("arrival_share_quartile",observed=True)[
          ["future_new_arrival_weight_share","physics_total_load_rmse_kN","raw_total_load_rmse_kN","support_total_load_rmse_kN"]
        ].mean().reset_index()
        qsum["arrival_share_quartile"]=qsum.arrival_share_quartile.astype(str)
        qsum.to_csv(out/"forecast_mismatch_quartiles.csv",index=False)
    except Exception as e:
        stats["quartile_error"]=str(e)
    (out/"forecast_mismatch_summary.json").write_text(json.dumps(stats,indent=2))
    return stats

def write_report(out,alias,sanity,control,lm_summary,lm_boot,sens,mismatch):
    lines=[]
    lines += ["STRUCTURES JOURNAL REVISION EXPERIMENTS","="*80,""]
    lines += ["Canonical provenance checks",json.dumps(alias,indent=2),"",
              f"Solver sanity max disp diff: {sanity.max_abs_disp_diff_m.max():.3e}",
              f"Solver sanity max acc diff : {sanity.max_abs_acc_diff_mps2.max():.3e}",""]
    lines += ["Load-matched control check",json.dumps(control,indent=2),"",
              "Full 600-window mean metrics",lm_summary.to_string(index=False),"",
              "37-scenario paired bootstrap (positive means first method has larger error / second is better)",
              lm_boot.to_string(index=False),""]
    lines += ["Sensitivity subset summary",sens.to_string(index=False),"",
              "Forecast mismatch summary",json.dumps(mismatch,indent=2),""]
    (out/"STRUCTURES_REVISION_RESULTS.txt").write_text("\n".join(lines),encoding="utf-8")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=Path.home()/"Downloads"/"btpit_stage4_update_bundle")
    ap.add_argument("--solver",type=Path,default=Path.home()/"Downloads"/"stage6_vbi_v3_fullfield_substep.py")
    ap.add_argument("--out",type=Path,default=None)
    ap.add_argument("--sensitivity-per-scenario",type=int,default=3)
    ap.add_argument("--skip-sensitivity",action="store_true")
    args=ap.parse_args()
    root=args.root.resolve(); solver_path=args.solver.resolve()
    out=(args.out or root/"outputs"/"structures_revision_experiments").resolve()
    out.mkdir(parents=True,exist_ok=True)
    cpath=root/"outputs/forecast_benchmark_seed13/vbi_input_C_residual_support_consistency.npz"
    spath=root/"outputs/stage6_vbi_seed13_test600_C_support_consistent/stage6_v3_bridge_responses.npz"
    cfgpath=root/"outputs/stage6_vbi_seed13_test600_C_support_consistent/stage6_v3_config.json"
    for p in [solver_path,cpath,spath,cfgpath]:
        if not p.is_file(): raise FileNotFoundError(p)
    mod=load_solver(solver_path)
    C=np.load(cpath,allow_pickle=False)
    saved=np.load(spath,allow_pickle=False)
    cfg=json.loads(cfgpath.read_text())
    scales=np.asarray(C["normalization_factors"],float)
    names=[str(x) for x in C["channel_names"]]
    weight_idx=mod.find_channel(names,["weight","load"],2)
    manifest=load_manifest(root)
    alias=verify_aliases(root,C)
    (out/"canonical_alias_check.json").write_text(json.dumps(alias,indent=2))
    samples=[0,1,50,200,514,599]
    sanity=solver_sanity(mod,C,scales,weight_idx,cfg,saved,samples)
    sanity.to_csv(out/"solver_reproduction_sanity.csv",index=False)
    lm_summary,lm_boot,control,md,ma=run_load_matched(mod,C,scales,weight_idx,cfg,saved,manifest,out)
    mismatch=run_forecast_mismatch(C,scales,weight_idx,manifest,root,out)
    if args.skip_sensitivity:
        sens=pd.DataFrame([{"status":"skipped"}])
    else:
        sens=run_sensitivity(mod,C,scales,weight_idx,cfg,saved,manifest,md,ma,out,args.sensitivity_per_scenario)
    write_report(out,alias,sanity,control,lm_summary,lm_boot,sens,mismatch)
    print("\nDONE")
    print("Upload this file to ChatGPT:")
    print(out/"STRUCTURES_REVISION_RESULTS.txt")

if __name__=="__main__":
    main()
