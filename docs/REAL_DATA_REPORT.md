# Real Qlib Alpha158 exploration — 2026-10-26

**Finding: none of the three investigated signals outperformed the fixed-basket equal-weight benchmark.** Negative results are retained unchanged. **This is exploratory historical analysis, NOT a tradable strategy, not financial advice, and not evidence of positive alpha.**

## Data source, verified integrity
- Upstream: [chenditc/investment_data](https://github.com/chenditc/investment_data), cited by Microsoft Qlib documentation. Multi-provider crowd dataset involving Tushare, AkShare, Yahoo and other sources. Source quality is not guaranteed.
- **Pinned release tag:** \`2026-10-25\`, publisher's latest trade date \`2026-10-23\`.
- Release archive: \`qlib_bin.tar.gz\`, **569,210,863 bytes**; SHA-256 \`0a2974da97b4737e503ecddeea8bb3b2179e0e16ea0fb19fa373ff14155bf315\`.
- Same-release \`qlib_bin.manifest.json\` checked; **67,904 members** validated for size/hash and unsafe archive entry types/path traversal prior to extraction.
- Mac local-only data: \`data/external/qlib_20261025/\`; source archive and raw prices are \`data/\` (gitignored). Do not redistribute provider content by committing.
- Qlib \`0.9.7\` on macOS Apple Silicon with \`kernels=1\` to prevent spawn-import errors when using interactive stdin.

## Design and reproducibility
- **Analysis:** 2024-01-02 to 2025-12-31. The index member history file is \`instruments/csi300.txt\`; initial membership count **300** confirmed against Qlib \`D.list_instruments\`.
- **Inception basket of 12 stocks selected without future data:** lexicographically earliest 12 symbols from **CSI300 membership at the first decision date**. Not a reconstruction of the full CSI300 or a representative random basket.
- **Per-decision historical membership** is applied, with no filter on future end-date membership. All chosen names happened to remain valid in the analyzed period; this alone is not a complete survivorship or price-adjustment audit.
- **Prices:** Qlib normalized/adjusted open, close and volume; source quality and point-in-time adjustment factor revisions have NOT been independently verified.
- **Factors:** six causal custom features and **158 Qlib Alpha158** features. No Qlib infer/learn processors are pre-fitted across the full analysis period; Ridge median imputation fits per training fold.
- **Timing:** know prices through close(t), enter at open(t+1), exit at open(t+2). Two sessions after final decision are fetched for label settlement. Missing or zero future entry/exit prices for otherwise signal-eligible rows **abort** instead of excluding the asset with hindsight. Observed invalid future entries for this exact sample: **zero**.
- **Cross-validation:** expanding temporal folds, 120 minimum training dates, 35 validation dates, 35 held-out test dates per block (last shorter), **10** folds, **328** held-out sessions. Final training uses labels known at test decision time, with purge between validation/test.
- **Models:** 5-session momentum rank, Ridge with training-fold median imputation and standardization, LightGBM CPU. Choose Ridge/LightGBM fixed small parameter grids using previous validation only.
- **Trading model:** long Top-3, rebalanced at next open, equal weights, charge transaction fees on sum(abs(new-target-weight - prior-target-weight)). Comparing with a similarly fee-adjusted equal-weight portfolio of the **same 12 stocks**. No leverage, no shorting. No actual order execution observed.

## Out-of-sample real price-history study (not investable performance)

All model results are for the same 328 decision sessions, with 10 bps per unit traded notional. Values below are **cumulative returns on normalized Qlib price history**, not a promise of investment return.

| Frozen model | OOS daily RankIC | Portfolio gross | Portfolio net (10bps) | Same-basket equal-weight net |
|---|---:|---:|---:|---:|
| Momentum factor | +0.00054 | -3.32% | **-22.70%** | +13.49% |
| Ridge + Alpha158 | -0.00481 | -1.30% | **-27.21%** | +13.49% |
| LightGBM + Alpha158 | -0.03602 | +2.60% | **-28.60%** | +13.49% |

All three underperformed even before fees relative to the +13.61% gross equal-weight basket. Thus there is no evidence that the current models produce useful stock ranking or positive alpha; large turnover additionally harms post-fee results.

### Fees as a predeclared sensitivity grid

| Model | 0 bps net | 5 bps net | 10 bps net | 20 bps net |
|---|---:|---:|---:|---:|
| Momentum factor | -3.32% | -13.55% | -22.70% | -38.21% |
| Ridge | -1.30% | -15.24% | -27.21% | -46.34% |
| LightGBM | +2.60% | -14.40% | -28.60% | -50.34% |
| Equal-weight basket | +13.61% | +13.55% | +13.49% | +13.38% |

Paired circular 5-session block bootstrap was applied to mean daily **strategy minus benchmark** returns, 1500 resamples, fixed seed; at the 10bps configuration the descriptive 95% intervals were negative for all three. These intervals are **not** calibrated proof of negative/positive tradeable alpha, and do not correct for trying multiple features/models or price-data lookahead concerns. Full values in the linked JSON artifact.

## Known limitations / next experiment decision
1. **Small fixed inception basket**: 12 symbols, not broad index membership or free-floating universe. Even though selection is as-of, extrapolation to a whole exchange/index is invalid.
2. **Historical adjusted price accuracy**: point-in-time revision of adjustment factors and future corporate actions is not audited. Daily auction close-to-next-open timing in documentation does not make official open-price fills guaranteed.
3. **Survivorship beyond basket**: Qlib index intervals guard constituent eligibility, but halted assets, delistings, price limits, realistic commission, slippage and lot sizes are not modeled.
4. **Model power and costs**: all three baselines underperform the basket; no hyperparameters should be retuned on this held-out period. Next step must establish a **new, previously untouched** market period/universe for an improved model.
5. **Statistical significance**: small 12-name cross-section and serial dependence. Bootstrap is a sensitivity indicator only.
6. **Not an execution system**: no market connect, position sizing, broker API or live trading.

## Run from a clean Mac clone

\`\`\`bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test,ml,qlib]'
bash scripts/install_qlib_release.sh
bash scripts/mac_real_qlib.sh
\`\`\`

The second script performs tests and produces all three frozen model runs plus fee sensitivity under a unique gitignored \`runs/\` directory. Ensure enough local space to store a ~569 MB tar archive and the extracted features. The original runs and exact machine-readable summary are recorded in:
- \`docs/experiments/2026-10-26_real_qlib_csi300_exploratory.json\`
- \`docs/ENGINEERING_LOG.md\`
- \`docs/EXPERIMENT_PROTOCOL.md\`

## Hiring relevance
Quant/AI algorithms: temporally purged validation, truthful failure reporting, Alpha158 construction, portfolio fees and signal evaluation are meaningful **engineering and methodological** evidence. Do **not** list this as a profitable factor discovery or production-grade quantitative alpha.
