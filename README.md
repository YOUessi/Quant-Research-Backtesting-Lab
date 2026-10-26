# Quant Research & Backtesting Lab

**Status: WIP — first CPU research baseline. No verified real-market alpha claims.**

An auditable time-series factor lab aimed at AI/data/quant internships. Code, tests, methodological decisions, and engineering logs live in GitHub; the Mac is used for CPU verification. No NVIDIA GPU is required for v0.

## Roadmap (acceptance gates)
1. Deterministic synthetic OHLCV **smoke test only**; strict feature/label timing and leakage tests.
2. CPU baselines: momentum, Ridge, LightGBM; expanding walk-forward train/validation/test.
3. Daily top-K equal-weight portfolio, transaction costs and a cost-adjusted equal-weight benchmark.
4. Real-data experiments on the exact same code path, with data provenance and point-in-time universe caveats. Optional Qlib Alpha158 adapter.
5. Frozen experiment manifests, metrics, validation evidence and failure log; no cherry-picked results.

**Critical timing:** compute features using data available through close on decision date `t`; enter at next session **open(t+1)** and exit **open(t+2)**. Thus `y_t = open(t+2)/open(t+1)-1`. The latest legally known label at decision close(t) is from t−2. Training and validation are purged accordingly.

## Local Mac setup (Python 3.10+)

```bash
git clone https://github.com/YOUessi/Quant-Research-Backtesting-Lab.git
cd Quant-Research-Backtesting-Lab
$HOME/.local/bin/python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,ml]'
python -m pytest -q
python -m quant_lab.cli demo --model ridge --output runs/demo_ridge
python -m quant_lab.cli demo --model lightgbm --output runs/demo_lgbm
```

On the connected Mac, the system python3 is 3.9.6. The existing executable $HOME/.local/bin/python3.12 is used above to create .venv. Run all three synthetic baselines with a repeatable macOS OpenMP workaround:

    bash scripts/mac_verify.sh

If the system LightGBM cannot load libomp.dylib, this script uses the already installed scikit-learn wheel's trusted OpenMP runtime inside the same virtual environment. This is a **local compatibility workaround**, not a permanent system install. For other systems use the platform's regular libomp installer.

To analyze user-provided real, adjusted OHLCV data:
```bash
python -m quant_lab.cli csv --input path/to/market.csv --provenance 'vendor, adjustment, date, universe' --model lightgbm --output runs/real001
```

CSV required columns: `date,asset,open,close,volume` (adjusted prices consistently handled, positive volumes). Date is daily session date. The v0 implementation expects a fully balanced asset/date panel, intentionally refusing missing/suspended/incomplete panels rather than silently inventing tradable returns. CSV provenance, delistings, corporate actions and a **point-in-time** universe must be documented before drawing real-world conclusions.

`demo` produces **synthetic toy market data**. No simulation result counts as investment performance or evidence of alpha. `runs/` is gitignored; share experiment summaries with exact run configs and source provenance instead of committing user datasets.

## Contents
- `src/quant_lab/`: ingestion, causal factors, supervised models, leakage-safe walk-forward, cost-aware backtest, metrics and CLI.
- `tests/`: targeted look-ahead, purge, fee, panel, determinism regression tests.
- `docs/EXPERIMENT_PROTOCOL.md`: timing, splits, metric definitions, biases and go/no-go gates.
- `docs/ENGINEERING_LOG.md`: problem → root cause → fix → verification → residual risk.
- `docs/JD_REQUIREMENTS.md`: mapping to quant research, AI algorithm and financial time-series JD.
- `.github/workflows/ci.yml`: CPU tests on push and PR.

## Honesty & limitations
This is an **engineering baseline**, not a tradable strategy. The first data is synthetic; Qlib Alpha158 is optional and requires a real dataset and point-in-time audit. Daily open-to-open position accounting ignores market impact, halted stocks, borrow/short restrictions, taxes, exchange auction specifics and changing universe composition. Avoid investment claims. See `docs/EXPERIMENT_PROTOCOL.md`.

## Actual Mac CPU verification (2026-10-26)
- Python 3.12 (isolated venv), pandas 2.3.3, scikit-learn 1.9.1, LightGBM 4.7.0. pytest **9 passed**.
- Synthetic demo, 8 fictional assets, 260 generated sessions, 156 OOS decisions, 10 bps each side of traded notional: factor RankIC +0.03999, Ridge -0.05678, LightGBM -0.01572; cumulative **net** returns: -3.53%, -20.88%, -21.91%, respectively; same-fee equal-weight benchmark -5.26%.
- All numbers above are **synthetic engineering verification**, not real-market performance, estimates of alpha or evidence of investment value. Ridge and LightGBM did not beat the toy equal-weight benchmark. Check docs/ENGINEERING_LOG.md for observed issues.


## Stage 2 — real historical Qlib Alpha158 research (2026-10-26)

**Status: REAL DATA EXPERIMENTS VERIFIED, but no profitable strategy demonstrated.** Full report: [Real data report](docs/REAL_DATA_REPORT.md), [experiment metrics](docs/experiments/2026-10-26_real_qlib_csi300_exploratory.json), and [engineering failure/fix log](docs/ENGINEERING_LOG.md).

On the Mac, with Python 3.12 and a project-only virtual environment:

\`\`\`bash
.venv/bin/python -m pip install -e '.[test,ml,qlib]'
bash scripts/install_qlib_release.sh
bash scripts/mac_real_qlib.sh
\`\`\`

This will verify/download the **pinned 2026-10-25** community Qlib archive (569.21 MB compressed, SHA256 from its same-release manifest), load CSI300 membership as of 2024-01-02, select a **predeclared first-12-ticker slice**, compute 158 Qlib Alpha158 + six causal handcrafted features, produce expanding purged walk-forward predictions, and compute gross/net portfolio, turnover and fee sensitivity. No source market data is ever committed to GitHub.

For the exact verified experiment: 2024-01-02 to 2025-12-31 with 328 out-of-sample dates. At 10 bps traded-notional cost, the **portfolio cumulative net returns** are momentum -22.70%, Ridge -27.21%, LightGBM -28.60%, versus **same 12-name equal-weight** +13.49%. These are modeled returns on real historical *adjusted* data, **not executable investment profits**. A fixed 12-name inception cohort is not CSI300 replication; index eligibility is checked as-of each date, but price-adjustment revision, halts, actual open fills, slippage and broader universe effects are not fully modeled.

The project has been tested on Mac CPU; Tang and any NVIDIA GPU remain unnecessary. **Do not state that the model achieved positive alpha or beat the benchmark.**


## Stage 3 — EXP-002 independent 2021–2022 historical-universe risk audit

**Completed (Mac CPU, 2026-10-26):** Expanded from the prior 12-stock illustration to **433 distinct CSI300 historical-member symbols**, with 300 index constituents as of each evaluated date, **485 independent 2021–2022 sessions**, explicit index-vs-exchange listing histories, halt/nonfill detection, no borrowing, stop-on-unvalued delisting/held positions, float32 factor audit and a separate hypothetical opening price-limit proxy. [Read the EXP-002 results](docs/EXP002_RESULTS.md) and [pre-registered plan](docs/EXP002_PRE_REGISTRATION.md).

Run the preregistered 433-symbol study with no NVIDIA GPU:

\`\`\`bash
.venv/bin/python -m pip install -e '.[test,ml,qlib]'
bash scripts/install_qlib_release.sh
bash scripts/mac_exp002.sh
\`\`\`

Detailed reproducible machine-readable experiment records:
- [Full-universe and factor-quality audit](docs/experiments/2026-10-26_exp002_full_universe_audit.json)
- [Daily vs every-five-day historical adjusted-price **PROXY** execution study](docs/experiments/2026-10-26_exp002_independent_execution_proxy.json)
- [CSI300 price-only **REFERENCE**, not executable benchmark](docs/experiments/2026-10-26_exp002_csi300_price_index_context.json)
- [Problems, root causes, fixes and Mac verification](docs/ENGINEERING_LOG.md)

Frozen 10bps fee result on 2021–2022: daily Top-10 momentum **−73.14%**, every-five-session Top-10 **−59.64%**, each based on hypothetical filled orders and historical adjusted-price units; both strategies have negative results, while the full 300-member equalweight accounting benchmark was **CENSORED** because one held asset lacked six successive marks. The market-reference CSI300 price index changed **−26.50%**, but it is *not* a fee-adjusted executable total-return benchmark. Never advertise these proxy percentages as realized investment returns or positive alpha.

**What still cannot be certified:** retroactive revisions to price adjustment factors at each historical publication date, corporate-action cash/share rights, exact limit prices and opening-auction order fills, market impact, and delisting settlement. These deficits remain prominently marked; the independent period has now been evaluated and cannot be recycled as an untouched holdout.

On the connected Mac, the original Git checkout remains behind GitHub due to intermittent Git network failures. Exact GitHub source files were relayed into a gitignored isolated mirror for verification; **27 tests passed** against that mirror and complete multi-strategy results reproduced exactly in a second full pipeline run. The mirror is not a git commit, and GitHub remains authoritative.
