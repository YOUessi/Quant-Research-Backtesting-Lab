# Engineering log (observed issues and planned mitigations)

Recording format: timestamp · environment · symptom/reproduction · root cause · fix · verification command + output · remaining uncertainty.

## 2026-10-26: design and GitHub initialization
- **Q-001 Possible look-ahead:** using close(t)-to-close(t+1) returns as though a close(t) order could be filled. Preventive fix: explicit features through close(t), target next-open(t+1) to following-open(t+2). Automated feature/label tests. Status initially pending execution.
- **Q-002 Model selection leakage:** tuning on future test data or training labels unavailable at a fold boundary. Preventive fix: two-session date separation for labeled observations at validation and test starts; select candidate only on preceding validation data. Boundary assertions and tests. Status initially pending execution.
- **Q-003 Transaction-cost understatement:** switching a position sells old + buys new; net vs gross benchmark unfair. Fix: charge absolute weight change to both model and equal-weight benchmark; test a two-session switch.
- **Q-004 Invalid market claim:** toy data can produce convincing but meaningless Sharpe. Fix: mark synthetic source explicitly in README, CLI manifest and output.
- **Q-005 Dynamic universe / halted asset problem:** cannot safely forward-fill an open price for an untradeable asset. Fix in v0: reject unbalanced panels. Remains **open**: survivorship bias, changing membership, corporate actions, liquidity.
- **Q-006 Platform dependency:** Mac system Python was reported as 3.9.6 (too old for project) and base system lacked numpy/pandas/sklearn/lightgbm/pytest. Fix: use existing Python 3.12 located at ~/.local/bin/python3.12 in a project .venv. Verification pending actual install and test result.
- **Q-007 GitHub action source preparation:** a multi-file upload script was rejected by the JS parser before any new files from that batch were created. Fix: split into smaller, syntactically isolated GitHub file commits. Verification: targeted GitHub create_file commits for tests, followed by repo inspection.

## Mac validation
**Not yet recorded as successful.** Add exact command output, failing assertions, root causes, commits and rerun status after executing tests.

## Real-market experiments
**Not run.** Qlib integration is optional/untested with real datasets; any true financial performance statement must include source, timestamps, point-in-time/universe analysis, fee assumptions and out-of-sample results.

## 2026-10-26: actual macOS CPU validation (observed)
- **Host:** YOUTangdeMacBook-Air.local (Apple Silicon arm64). Repo cloned to ~/Documents/jobsearch/Quant-Research-Backtesting-Lab. GitHub main was pulled before validation. Tang GPU was not used.
- **Q-006 resolved:** system /usr/bin/python3 = 3.9.6 and had none of the test packages. An existing ~/.local/bin/python3.12 created .venv; command: ~/.local/bin/python3.12 -m venv .venv && .venv/bin/python -m pip install -e '.[test,ml]'. Actual versions: Python 3.12, pandas 2.3.3, NumPy 2.5.4, scikit-learn 1.9.1, LightGBM 4.7.0, pytest 9.1.1. No system Python files were modified.
- **Q-007 test confirmation:** exact command .venv/bin/python -m pytest -q -> 9 passed in 4.75s (after pulling latest docs). Earlier first run -> 9 passed in 36.08s. This confirms CPU-code regression tests, not real-market alpha.
- **Q-008 macOS LightGBM OpenMP missing:** .venv/bin/python -m quant_lab.cli demo --model lightgbm --output runs/first_lgbm failed with OSError: dlopen(lib_lightgbm.dylib): Library not loaded: @rpath/libomp.dylib. Root cause: pip LightGBM macOS wheel requires an OpenMP runtime; no Homebrew libomp installed. **Fix:** located trusted libomp.dylib at .venv/lib/python3.12/site-packages/sklearn/.dylibs/libomp.dylib (also found a Miniforge OpenMP runtime), set DYLD_LIBRARY_PATH to the sklearn wheel directory *for the subprocess only*. Test import -> LightGBM 4.7.0 and scikit-learn 1.9.1 successfully imported. Full LightGBM demo -> success. Reusable project script scripts/mac_verify.sh committed; no system-wide binary installation.
- **Reproduced synthetic demos** using Mac .venv/bin/python and --seed 42, 260 generated sessions/8 fictional stocks, 156 OOS decision dates with 10 bps fees:
  - momentum factor: OOS RankIC +0.03999; model cumulative net -0.03527; equal-weight net -0.05264; average traded notional 0.5406.
  - Ridge: OOS RankIC -0.05678; model cumulative net -0.20882; equal-weight net -0.05264; average traded notional 0.9679.
  - LightGBM: OOS RankIC -0.01572; model cumulative net -0.21913; equal-weight net -0.05264; average traded notional 1.0705.
- **Interpretation:** test confirms deterministic pipeline construction and execution, NOT a positive trading strategy. Ridge and LightGBM underperform the synthetic equal-weight benchmark. No real-data IC, alpha, Sharpe significance or investment result was claimed.
- **Artifacts:** runs/first_factor, runs/first_ridge, runs/first_lgbm on Mac; runs/ is gitignored. Each includes metrics.json, folds.json, predictions.csv, daily_returns.csv, manifest.json.
- **Open next tasks:** Qlib Alpha158 integration with licensed data; factor exposure controls and a point-in-time asset universe; halt/delist/split/dividend-aware execution; independent out-of-sample period and benchmark uncertainty.
