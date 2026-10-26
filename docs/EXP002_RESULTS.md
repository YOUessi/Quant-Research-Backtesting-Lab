# EXP-002 — independent 2021–2022 historical-constituent / execution-uncertainty study

**Verification date:** 2026-10-26. **Data:** Qlib community release \`2026-10-25\` (last market date 2026-10-23), SHA-256 \`0a2974da97b4737e503ecddeea8bb3b2179e0e16ea0fb19fa373ff14155bf315\`.

**This is NOT a profitable strategy result, point-in-time adjustment-certified return, or observed broker execution.** It is a pre-registered independent-period experiment whose cash-constrained portfolio estimates use **adjusted-series entitlement proxy units** and hypothetical next-open fills. The independent evaluation period has now been observed and **must not be reused as an untouched holdout** for further optimization.

## Registration and reproducibility

Before computing EXP-002 returns, the dates/rules were written to [EXP-002 pre-registration](EXP002_PRE_REGISTRATION.md) (commit \`4fe6b95614b63c531013b91bb6dfec41b7cbac94\`):

- 2021-01-04 through 2022-12-30, **485** daily exchange sessions; deliberately nonoverlapping with EXP-001's 2024–2025 experiments.
- No training on the independent period; compare the **same 5-session momentum signal** (A) Top-10 daily rebalance, (B) Top-10 every 5 sessions. Both long-only with identical event-driven fill/fee assumptions.
- Primary cost 10 bps on executed notional; 0/20 bps descriptive stress, not post hoc hyperparameter selection.
- Historical **daily CSI300 membership** from \`instruments/csi300.txt\` (not today's constituents). The full **union of 433 tickers** is represented, and index eligibility is decided separately as of each day.
- Daily/suspension/exit constraints are checked when attempting next-session execution, not used to backfilter yesterday's signal. Index exit and **exchange delisting** use different historical files.
- Optional ±9.8% *raw-price* opening-gap proxy flags possible limit orders, but **NOT official exchange up/down limits** (not present in bundle). Corporate-action cash/share settlement is not available.

To rerun from current GitHub checkout on a Mac CPU:

\`\`\`bash
.venv/bin/python -m pip install -e '.[test,ml,qlib]'
bash scripts/install_qlib_release.sh
bash scripts/mac_exp002.sh
\`\`\`

The setup script verifies the pinned publisher manifest, actual archive bytes, SHA-256 and safe tar members; raw data and day-level trade events stay in gitignored \`data/\` and \`runs/\`.

## Expanded universe and time/price-source audit

| Audit item | Observation |
|---|---:|
| Historical unique CSI300 member symbols (analysis+warmup interval) | **433** |
| Daily CSI300 member count, minimum/maximum | 300 / 300 |
| Explicit crosschecks against Qlib index-membership API | 2021-01-04, 2021-12-31, 2022-12-30 — matched |
| Real evaluation exchange sessions | **485** |
| Per-session *causally* eligible signal candidates | 297–300 |
| Historical constituent-days with missing/invalid observed closes or volume | **139** |
| Union-wide asset/day rows through source/warmup history | 273,223 |
| Nonmissing adjusted close bars | 268,121 |
| Exchange listing-end records among the wider historical union in EXP-002 | 1 |
| Factor ratio steps >1% on evaluation days among index members | **396** |
| Qlib adjusted/raw roundtrip errors at float32 appropriate tolerance | **0** |
| Real historical adjustment-factor release snapshots | **not available** |

**Important:** the 396 factor steps are not 396 verified dividend/split events. Across all candidate symbols (including days not in index) there are 528 >1% steps. With this source snapshot alone we can verify \`Qlib-adjusted quote = estimated nominal quote × factor\` up to observed float32 precision (maximum tested relative reconstruction error about 6×10^-8). We **cannot** reconstruct what adjusted-factor values were published on each historical day or actual corporate-action cash payouts. No investment-grade point-in-time factor certificate is claimed. See <https://github.com/microsoft/qlib/blob/main/docs/component/data.rst>.

## Independent 2021–2022 estimated valuation results — ALL strategies NEGATIVE

These numbers are **cumulative Qlib-adjusted-price portfolio proxy valuations**, not real trade returns. A full fill is assumed for every unblocked next-open order; intraday fill probability/impact are unobserved.

| Frozen Top-10 rule | 0 bps | **10 bps primary** | 20 bps |
|---|---:|---:|---:|
| Five-day momentum, daily rebalance | -57.51% | **-73.14%** | -83.01% |
| Five-day momentum, every 5 sessions | -51.64% | **-59.64%** | -66.31% |

The weekly rule's primary-case proxy is **13.50 percentage points less negative** than the daily rule, but both remain far below the initial capital. Not a positive return, investable alpha, or statistically established cross-market improvement.

### Operational risk / fill evidence at 10 bps

| Counter | Daily | Every 5 sessions |
|---|---:|---:|
| Hypothetical next-open order fills (*model assumed*, NOT broker confirmed) | 7,057 | 1,873 |
| Days with held-position stale closing marks | 5 | 0 |
| Held-position adjusted factor steps >1% | 11 | 7 |
| Nonexecutions due to missing opening price or volume | 6 | 0 |
| Observed held-position missing/suspended opens | 5 | 0 |

The 5 daily stale-mark days are **not certified daily portfolio valuations**. The weekly result carries no such days in this particular sample, but still relies on adjusted snapshot rights-entitlement proxies, idealized opening fills and limited execution rules.

A separate **unofficial** ±9.8% opening-gap proxy stress gate blocked 3 attempted buys for the weekly 10-bps method. It produced a -58.68% proxy. The percentage MUST NOT be interpreted as actual exchange limit-price enforcement; ST/STAR/ChiNext rules differ and regulatory limit values were absent.

### Benchmark censoring is intentional

An attempted **point-in-time dynamic-constituent equal-weight** accounting baseline was **CENSORED** on **2021-02-05**: held ticker \`SH600340\` lacked a fresh valuation for 6 consecutive sessions. Simulated cashout at the last close or removing that ticker from the past would bias the benchmark. The algorithm instead produced \`CENSORED_UNRESOLVED_POSITION\` and **withheld full-horizon benchmark return**. This is a meaningful negative risk-model finding, not an absent benchmark zero return.

A separate Qlib \`SH000300\` **CSI300 price-only index reference** changed **-26.50%** across 2021-01-04 to 2022-12-30. This index-level **price-only** change excludes dividends, trading fees and replicating-order constraints, unlike the portfolio price-adjusted proxy; it is useful as **market background only**, **not** a valid net investable benchmark.

## What is genuinely improved?

- 12 fixed names → historical union of **433** ticker candidates, 300 index members per day; explicit index-entry/exit and separate exchange listing history.
- 0 tolerated missing bars → 139 historical constituent-day unavailable observations preserved as state flags, not future-screened.
- Single hypothetical cost formula → event-level cash, no borrowing, sell-first/buy-second, deferred/blocked halted orders and explicit stale valuation.
- Unrecorded delisting risks → censored state where held delisting has no verified settlement; first full equal-weight study was intentionally blocked instead of fabricated.
- Ad hoc selection → preregistered untouched 2021–2022 independent historical test with transparent negative results; no strategy was changed after seeing this result.
- Current snapshot's Qlib factor issue → float32 numeric reconstruction tested, factor jumps counted, but release-time point-in-time factor and entitlement validity clearly **NOT verified**.

## Remaining blockers / go-no-go

**Not ready for deployable quant or alpha claims** until independently completing:
1. historical daily vendor adjustment factors and split/dividend entitlements with *as-of release timestamps*;
2. official stock price-limit up/down, special treatment, intraday tradability, auction/closing depth and realistic broker fills;
3. exchange suspension and delisting settlement/closeout rules including unknown recoveries for long-held positions;
4. valid dynamic equal-weight portfolio benchmark with censored constituent valuation resolved;
5. new future-free independent holdout after **pre-registering** changes, avoiding reuse of EXP-002 now inspected.

**Result:** engineering, causal method and honest risk-reporting deliverables are demonstrated. No financially validated positive strategy is demonstrated.

**Source artifacts:** [historical-universe/factor audit](experiments/2026-10-26_exp002_full_universe_audit.json), [execution proxy & frozen result manifest](experiments/2026-10-26_exp002_independent_execution_proxy.json), and [CSI300 price-only context](experiments/2026-10-26_exp002_csi300_price_index_context.json). All primary event logs/price data remain on the Mac, not committed.
