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
