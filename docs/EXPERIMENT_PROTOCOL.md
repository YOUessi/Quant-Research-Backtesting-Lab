# Experiment protocol v0.1

## Goal
A reproducible *engineering baseline* for financial data/algorithm internships. It is **not a trading system**; first-stage experiments use deterministic synthetic data to validate the pipeline only.

## Causal chronology (daily bars)
At close of session t, compute features X(t) using only information observed through close(t). Predict the theoretical open-to-open holding return:

    y(t) = open(t+2)/open(t+1) - 1.

Trade at the next open(t+1); exit at open(t+2). Qlib Alpha158 ordinarily defines a next-close/next-next-close label; we intentionally rebuild our label from the next session opens. This is **not** proof that live orders will fill at published open prices.

### Purge rules
- Validation begins at V: training labels must end at V-2, inclusive.
- Test begins at T: final fitting and parameter tuning use labels available at most at T-2.
- For each expanding-window fold, choose hyperparameters on the past-only validation block, refit on all history eligible as of test start, then produce a single held-out test window.
- Do not choose a hyperparameter, feature or displayed run by peeking at held-out test results. Holdout selection must be predeclared.

## Models
- **Factor-only:** rank on 5-day momentum.
- **Ridge:** StandardScaler + Ridge, predetermined alpha grid 0.1 and 10.
- **LightGBM CPU:** fixed 120 trees; predetermined leaves grid 7 and 15. No GPU used.
- **Benchmark:** equal weight on same assets/date range, with same modeled transaction fee.

RankIC = daily cross-sectional Spearman correlation between predictions and realized next-open holding returns, averaged across eligible held-out test dates.

## Backtest and costs
- Each day long top-K equally weighted assets selected from close(t) predictions.
- Inception from cash, then rebalance each following open.
- Fee at rebalance = fee_bps / 10000 * sum(abs(new_asset_weight - previous_asset_weight)).
- Net theoretical return = (1 - fee_fraction) * (1 + gross_holding_return) - 1.
- Equal-weight benchmark is charged under identical fee assumptions.
- No explicit terminal-liquidation fee; weights idealized and not drift-adjusted.
- Important omissions: bid-ask spread variation, slippage, market impact, taxes, transaction limits, delisting/halted sessions, changing stock universes, and exact open auction fill feasibility.

## Experiment artifacts
Runs in a new, non-overwritten output directory contain:
- manifest.json (data kind, SHA256 for CSV, feature list, seed, windows, audit flags)
- folds.json (boundary dates, tuning option and past validation RankIC)
- predictions.csv (out-of-sample rows only)
- daily_returns.csv (gross/net strategy and gross/net benchmark)
- metrics.json (descriptive stats; annualize assuming 252 trading days)

Sharpe/vol/annualized return on short samples are unstable. Add bootstrap/confidence intervals, more seeds, independent periods and cost sensitivity before drawing research conclusions.

## Real-data requirements / unresolved problems
1. Record data vendor, licensing, retrieval/as-of times, price adjustments, corporate actions and trading calendar.
2. v0 rejects any unbalanced asset/date panel to prevent silent stale-price fills. This nevertheless creates **survivorship and static-universe risk**. A point-in-time constituent membership/tradability model is still needed before investment-relevant claims.
3. Qlib adapter fetches Alpha158 *features* only, not its label; verify the handler's fitted transforms and point-in-time normalizers when processing a real dataset.
4. Test on multiple independent periods and compare with cost-adjusted equal-weight/factor baselines. Risk exposures, uncertainty and multiple-hypothesis testing remain future work.
5. Never call synthetic returns market alpha or fabricate a metric.
