# EXP-002 pre-registration — independent historical full-constituent study

**Frozen before examining EXP-002 returns (2026-10-26).** EXP-001 2024–2025 12-name results remain unchanged. Data quality metadata may be inspected without using realized returns to optimize EXP-002.

## Fixed data/time design
- Source: pinned community Qlib 2026-10-25 bundle with SHA256 `0a2974da97b4737e503ecddeea8bb3b2179e0e16ea0fb19fa373ff14155bf315`.
- Index: CSI 300, **dynamic historical membership**, not today's membership. Candidate symbols = all ever members during warmup + analysis, with eligibility tested as-of each decision date.
- Independent evaluation **2021-01-04 through 2022-12-30** (not used in the previous 2024–2025 comparison). No model or parameter may be chosen by evaluating this period and then re-labeling it an untouched holdout. Using the period once makes it exploratory for subsequent iterations.
- Warmup: from 2020-06-01 or earliest available 60 sessions before evaluation; do not build features with future bars. We will first run *pre-specified rule-based* momentum so no training data enters this initial comparison.
- **Frozen strategy definitions:** (A) 5-day momentum top-10, daily rebalance; (B) exact same momentum top-10, rebalance every 5 sessions. No rank buffer, sector filters or fee optimization before first holdout report.
- Start cash 1.0, long-only, no leverage, up to 10 equal-weight names; execution attempted at following day **open**, no lookahead selection.
- Fixed fees: 10 bps of traded notional for main report; display 0/10/20-bps as descriptive stresses, not a parameter sweep to pick a winning strategy.
- Benchmark: dynamic point-in-time index-membership equal-weight *idealized* baseline if feasible; any inability to value halted/delisted constituents is explicitly reported as unresolved, not hidden. A secondary zero-position cash baseline is transparent.

## Frozen execution and uncertainty treatment
- Asset qualifies as signal candidate only if index membership **as of close(t)** and positive observed close(t) and volume(t), enough past-only history for momentum.
- A missing/nonpositive open or zero volume at attempted fill => do NOT fill; if previously held, carry pending and mark stale with transparent valuation limitations.
- Exact price limits are **unavailable** in this dataset (`$up_limit/$down_limit` absent). Optional ±9.8% raw-price threshold is labeled **proxy stress scenario**, NOT regulatory price-limit inference; report this separately.
- For held positions, use adjusted-price total-return proxy for corporate actions while disclosing absent actual cash dividend/split entitlement and point-in-time factors. More than 5 consecutive missing-valuations or unresolved delisting => **fail-closed** or mark partial, never silently cash out at last price and claim portfolio return.
- No future tradability data may change t-close ranking; execution failure is observed only on attempted day.
- No use of `Ref(-1)` or fit transforms over the independent evaluation period. `factor` and implied raw price = adjusted / factor will be audited for missing, changes and future adjustment revision risk. Without historical vendor snapshots, **true point-in-time factor revisions cannot be proven**, and investment-grade certification remains blocked.

## Primary outcomes and stop conditions
- Prioritized validity gates: dynamic constituent counts vs Qlib; no hindsight filtering; missing/halted and deletion case tests; nonzero trade restrictions; factor flags; run metadata.
- Outputs: events / portfolio net/gross / turnover / broker fill assumptions / unresolved censoring status, with equal-weight comparison only if separately auditable.
- If held positions become unvalued, the **strategy return is withheld** as not interpretable; still report coverage, event counters and first unresolved case.
- If EXP-002 2021–2022 result is poor, publish negative evidence unchanged. No search over strategy rules after reading holdout outcomes.

## Research caveats
Historical reconstruction is only a *proxy*: current adjustment factors may encode future events, exact open auction liquidity not observed, ST / STAR / ChiNext varying statutory price limits cannot be inferred from ±10% alone, and continuous delisting payouts are not in Qlib OHLCV. Profitability claims are prohibited until independently reconciled.
