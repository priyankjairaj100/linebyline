# Paper 03 revision notes

## Current manuscript
- `MTT_reveyrand_updated.tex`
- End-to-end writing/consistency pass completed.
- Current manuscript commit: `77d42e8d2ff460a38c2b4b76b2ca4721a0741e10`.

## Manuscript-only consistency fixes completed
- Title now states that the scenarios are heterogeneous and simulated.
- Abstract problem statement corrected and the suspension-bridge overclaim removed.
- Abstract subject--verb agreement corrected.
- One-based longitudinal cell indexing made consistent with the manuscript's (s=1,\ldots,N_x) convention.
- Remaining hard-coded section numbers replaced with LaTeX references.
- Vehicle-weight notation standardized from (W_i) to (w_i).
- Count occupancy (O) and binary support occupancy (B) clarified.
- Undefined occupancy-loss count (N) described.
- Load-consistency wording aligned with the displayed objective.
- ML objective renamed to (\mathcal J) to avoid collision with the mechanical Lagrangian (\mathcal L).
- The controlled model-consistent IDM/MOBIL benchmark is now stated explicitly.
- Algorithm 1 now states that it does not specify a separate future-arrival mechanism.
- Channel-count notation changed from ambiguous (C) to (N_c=4).
- Global RMSE wording now states that it is computed on channel-scaled tensors.
- Common warm-start state is explicitly reused in Algorithm 2.
- Duplicate/mis-captioned use of `18.1.png`--`18.5.png` removed.
- Raw Residual treatment relative to the six-row structural table clarified.
- All remaining active figures and tables are cited in the prose.
- Support-consistency extrema distinguished from sequence-averaged RMSE/MAE.
- Remaining local typo corrected.
- Conclusion limitations aligned with the simulation-only benchmark.

## Static consistency checks
- Missing internal references: none.
- Duplicate labels: none.
- Unreferenced active figures: none.
- Unreferenced active tables: none.
- Hard-coded numbered section references: none.
- Duplicate active `18.1.png`--`18.5.png` block: removed.
- Active `\\end{document}` count: 1.
- Full Overleaf/LaTeX compilation was not performed in this environment.

## Still requires implementation/code verification
These items were deliberately not invented or filled from general knowledge:
- Exact modal mass, stiffness, and damping construction.
- Exact source and implementation of the five adopted modal frequencies.
- Exact lane-equivalent vehicle reduction.
- Exact block entries of the coupled (\mathbf M,\mathbf C,\mathbf K,\mathbf f) system.
- Gravity treatment and kN-to-force/mass conversion.
- Vehicle entry/exit and changing-occupancy handling inside the actual solver/forecast code.
- Exact residual-network architecture beyond the hyperparameters already stated.
- Final numerical values of the occupancy threshold and all loss weights.
- Exact empty-lane handling in the implemented Algorithm 2 equivalent.
- Exact definitions used by code for any plotted metric not already explicitly defined by the manuscript.
