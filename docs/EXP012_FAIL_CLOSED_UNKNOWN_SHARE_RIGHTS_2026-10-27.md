# EXP-012 — Censor ex-date nominal marks with unknown issuer share rights; segregate uncredited issuer share claims

Date: 2026-10-27. **Original issuer PDF/full SHA + independently archived raw CSV Mac CPU replay PASSED.** This is a conservative accounting/data-validity correction, **NOT** investor brokerage settlement, executable backtesting, alpha, or a newly untouched test period.

## Finding and fail-closed correction

The prior `simulate_nominal_right(..., share_bonus_ratio=None)` used `bonus=0` internally. Although the output was labeled `CASH_ONLY_ASSUMPTION_STOCK_BONUS_UNVERIFIED`, it still emitted an apparently precise ex-date `nominal_shares`, `share_mark`, `equity_gross_scenario` and `ex_close_total_mark_change`. For an event with an **unknown bonus or capital-transfer term**, this silently prices a *cash-only assumption* as if both share terms were exactly zero. The prior nominal probe also printed the resulting percentage.

**Fix:** Unknown share distribution is no longer equated with zero. At the ex-date and all subsequent observed quote days, `nominal_shares`, `share_mark`, `equity_gross_scenario` and ex-date percentage-change result become JSON `null`, with `CENSORED_UNVERIFIED_ISSUER_SHARE_RIGHTS` status. The existing original-share **record-day** mark and independently evidenced **gross pretax cash receivable** remain separate; the cash continues uncredited after the scheduled issuer pay day. Only a fully original-source-verified *explicit zero or positive* stock-rights ratio permits a **scenario** numeric mark.

For fully issuer-supported rights, the book now separately states `initial_record_day_shares_hypothetical`, `issuer_new_share_claim_uncredited` and `issuer_new_share_claim_price_mark`. Both `broker_confirmed_new_share_quantity` and `broker_confirmed_sellable_share_quantity` are always `null` in this source-only book. **Null means no reliable broker record, not evidence that no shares were delivered.** An issuer-derived claim is not a settled, sellable holding. The legacy `nominal_shares` numeric field in supported cases remains an *issuer-rights claim* for compatibility, NEVER a broker-verified executable quantity. The `pit_nominal_probe` consumer now reports a censored status instead of producing an unsupported percentage.

These safety rules are particularly material because **62/89** existing original issuer cash-event catalog entries lack complete bonus/transfer terms. This run verified the catalog classifications again; it did **not** fabricate quotes or independently price all 62 incomplete events. New unit tests demonstrate that these missing rights cannot produce a numeric after-ex stock mark.

## Original public documents and strict source scope

Offline source replay rehashed/reparsed the archived **89** original issuer-event PDFs and capital arithmetic (27 complete rights, 62 incomplete), plus these **three** pinned original issuer PDFs and independently archived unadjusted OHLCV CSVs. All PDF and CSV SHA256s below are **complete full-byte digests rechecked locally**, not shortened commit IDs:

| Symbol / ex-date | Original issuer document | PDF SHA256 | unadjusted CSV SHA256 | Issuer NEW-share entitlement on **hypothetical** 1,000 pre-existing shares | Broker-credit / verified sellable share quantity |
| --- | --- | --- | --- | ---: | --- |
| SH600276 / 2021-06-10 | [CNINFO original](https://static.cninfo.com.cn/finalpage/2021-06-04/1210161820.PDF) | `b731dec60e78bc92eab572ed099ec9da59fed84d6f06bb35fab605f4cb00a2f4` | `a80ae4f88ba9270894a9b88fc85bc408ecac27eefa9eeb6b9ea78d1a56e387af` | 200 claimed | **unknown / null** |
| SH600760 / 2021-06-24 | [CNINFO original](https://static.cninfo.com.cn/finalpage/2021-06-16/1210238262.PDF) | `6ee4d90b8e4d0fc49420a70df6a3a1ea148ad5e2d0a99f208fbb2d8358ddfec8` | `3309549d85141db76af7673db4ab4dccd663dd40091861f3a17199b490eb9843` | 400 claimed | **unknown / null** |
| SH603392 / 2022-04-21 | [CNINFO original](https://static.cninfo.com.cn/finalpage/2022-04-15/1212921735.PDF) | `0ee03e64cad8b1b2ed6a2164f212f3d0ece474a99efa52f0dbcde2b021ecc7d1` | `c72a6230fc54f5a6935eb14466e0c4734befd0393b3397f331563169ca63560c` | 450 claimed | **unknown / null** |

The original PDFs validate these hypothetical issuer *entitlements*, not any personal holdings or settlement. Gross pre-tax cash claims in these same examples (CNY 200 / 240 / 200) remain unverified receivables, **not spendable cash**. Source metadata JSON bytes are also hash-pinned in `pit_receivable_due_audit.PINS`. The original vendor HTTP response *body bytes* were **not** retained for a fresh second rehash; only the previously recorded response digest and locally rehashed raw CSV/source-metadata bytes can be confirmed. No raw vendor quotes or issuer PDF bytes were uploaded to GitHub.

The source-generated sanitized output `docs/experiments/2026-10-27_EXP012_issuer_share_claim_source_audit.json` is the byte-identical `audit.json` from the Mac replay (SHA256 `cd5a5d8a23c4d1395d8b4efb4deb202dff5fe02dfe533e978f2e1ee84d1381ce`). It deliberately retains the underlying reused EXP011 audit `kind`; it is not a new independent source download.

## Reproduction / actual Mac results

1. Unmodified local pre-run base checkout at **`7f51c4dc85b53298c2b5ebd5ed2e39c65f07570d`** matched GitHub `main` *before* EXP012; the tree was clean. Normal `git pull --ff-only` **FAILED** after 75.50 seconds trying GitHub port 443. No claim of successful `git pull`, local worktree advance, or remote Git transport recovery is made.
2. Fetched the three **exact base-SHA source blobs** using the authorized GitHub connector, staged all changed code and six new regression tests in **gitignored** `runs/exp012_source_mirror_20261027`, and used an isolated test-only package-path shim to import the modified files while leaving the checkout untouched. Each Mac `git hash-object` matched the exact GitHub-staged blob SHA.
3. Baseline checked-out Mac CPU suite: **188 passed in 11.87 s**. First enlarged suite: **193 passed, 1 failed** due solely to one new fixture checking string `"10000"` against the correct Decimal serialization `"10000.0"`. Fixed the test to compare `Decimal` values, without relaxing production checks; rerun: **194 passed in 7.33 s** (full replay: **194 passed in 7.74 s**).
4. SHA-backed offline original-source replay: the reused EXP011 runner separately reported **188 passed in 6.34 s**, extracted the 89 PDFs/capital proofs, regenerated the **27 complete / 62 incomplete** rights catalog, rehashed/reparsed **three original PDF+raw CSV+metadata** cases, and the EXP012 assertion independently confirmed issuer **200 / 400 / 450** uncredited new-share claims, all broker sellable quantities `null` and no transferred cash/portfolio orders. Exit status **0**.
5. `bash -n` on the new one-command script passed. All outputs stayed under gitignored `runs/exp012_complete_offline_source_replay_20261027_1618`. Earlier raw sources were not mutated.

After a **future genuine fast-forward** to this commit, reproduce using:

```bash
bash scripts/mac_exp012.sh runs/exp012_another_unique_replay
```

The script refuses an existing destination, requires the previously obtained licensed/public raw evidence, runs the CPU tests and the full offline source gates, and neither downloads new datasets nor reruns strategies. For the actual failed-Git-transport Mac run, the exact command was:

```bash
QUANT_LAB_ROOT="$PWD" \
PYTHONPATH="$PWD/runs/exp012_source_mirror_20261027" \
EXP012_EXTRA_TEST_DIR="$PWD/runs/exp012_source_mirror_20261027/tests" \
bash runs/exp012_source_mirror_20261027/mac_exp012.sh \
  runs/exp012_complete_offline_source_replay_20261027_1618
```

## Unresolved gates / explicit NON-claims

- Complete all original issuer bonus/transfer/cash terms and revision/publication histories for the remaining **62/89** incomplete cases; establish holder-specific broker credited bonus/new shares, payment tax/net settlements and reliable actual inventory. This commit only enforces a safe valuation **absence** where those terms are not known.
- Remaining five 2021-06-16 through 2021-06-22 SZ002024 issuer-primary, reason-specific full-interval halt days remain unproven (prior 134/139 original-source status unchanged).
- Historical stock/day official upper and lower price limits including ST/exemptions, halt/resume, opening auction queue and actual partial fills, delisting payment recovery and credible illiquid-position mark remain unavailable.
- Contemporary factor-vintage/point-in-time adjustment evidence remains missing. Prior seen EXP002 2021–2022 research was **not retrained, rerun or relabeled independent**. No financial performance, realized portfolio valuation, authorized broker transaction, or real-money trade was established.

**Decision:** engineering invariant + public original-source replay PASSED; **real broker-/exchange-grade financial validity remains BLOCKED**.
