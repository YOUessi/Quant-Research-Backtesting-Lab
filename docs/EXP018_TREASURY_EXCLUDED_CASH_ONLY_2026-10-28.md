# EXP-018 — Original issuer cash-only implementation with repurchased shares excluded

**Research / engineering date:** 2026-10-28 (Asia/Tokyo). **Status:** Mac CPU original evidence replay PASS; historical real executable trading/P&L remains **BLOCK**. Original issuer-source remediation, not a model/portfolio return experiment or an independent financial test.

## Three source-pinned current-plan share-right completions

Reviewed all **49** EXP017 unresolved original issuer PDF filings. Three archived **current implementation** notices explicitly say **本次权益分派实施后，公司总股本保持不变** (for SZ002311, equivalent **实施权益分派前后公司总股本保持不变**), both in the original issuer's introductory explanation and its ex-price calculation section. Separately, their operative **二、本次实施的权益分派/配方案** specifies cash-only distribution with an exact exclusion of shares held in the issuer repurchase securities account; no current positive bonus/transfer issuance is stated. Their original cash totals, total issued share counts, eligible share base and discounted ex-price references reconcile independently. Together, the **current unchanged issued capital + current cash-only distribution + excluded share count arithmetic + full source bytes** support **zero new stock rights under these three distributions**.

This is *not* a rule to infer zero stock rights from the absence of a stock clause, a boilerplate differential-dividend checkbox, a past-period unchanged share count, or conditional incentive-plan language. The proof is limited to exactly three event IDs and three original full PDF SHA256 pins. For SZ002311, a **49,690 restricted-share repurchase cancellation happened before the 2021 dividend**: it is not treated as the current distribution's share issuance/change.

| Event | SZ002311 ex 2021-07-09 | SZ002311 ex 2022-07-07 | SZ300760 ex 2022-05-19 |
|---|---:|---:|---:|
| Original issuer announcement day | 2021-07-02 | 2022-06-30 | 2022-05-11 |
| Conservative first usable exchange day | 2021-07-05 | 2022-07-01 | 2022-05-12 |
| Holder record date | 2021-07-08 | 2022-07-06 | 2022-05-18 |
| Issuer scheduled cash payment (also ex-date) | 2021-07-09 | 2022-07-07 | 2022-05-19 |
| Total originally issued shares | 1,661,161,061 | 1,661,161,061 | 1,212,441,394 |
| Issuer repurchased shares **ineligible for dividend** | 10,272,108 | 10,272,108 | 3,048,662 |
| Issuer dividend-eligible share base | 1,650,888,953 | 1,650,888,953 | 1,209,392,732 |
| **Pretax gross cash per eligible share** | CNY **0.32** | CNY **0.15** | CNY **3.50** |
| Original gross cash total | CNY 528,284,464.96 | CNY 247,633,342.95 | CNY 4,232,874,562.00 |
| **Ex-price cash reference per all issued shares** (truncated to 7dp) | CNY **0.3180212** | CNY **0.1490724** | CNY **3.4911993** |
| New shares caused by *this* cash-only implementation | 0 | 0 | 0 |

**Denominator integrity:** The pretax holder-eligible gross cash per share is **not** the ex-price adjustment reference, which divides total distributed cash by *all issued shares*, including issuer treasury stock. The module independently checks: total issued shares = eligible + excluded repurchased shares; eligible shares × gross eligible cash/share = issuer gross cash total; and the 7-decimal **truncated**, not rounded, ex-price cash reference. It fails on conflicting figures. Neither cash figure proves investor-specific tax, broker posting, receipt or actual ability to execute.

## Original public source identities

- **SZ002311 ex2021-07-09** — original implementation PDF https://static.cninfo.com.cn/finalpage/2021-07-02/1210385811.PDF ; archived *full PDF byte* SHA256 `10c5902cee6513ff6fafaf60f1cbd2f0d75627f3206186730c0b4f35294d280e`; first-page issuer 广东海大集团股份有限公司, code 002311, title 2020年年度权益分派实施公告.
- **SZ002311 ex2022-07-07** — original PDF https://static.cninfo.com.cn/finalpage/2022-06-30/1213878821.PDF ; full SHA256 `b235ff0808d2f271148baf55b9079d479da619bd66c3594608c1c194e72d02d0`; same issuer, title 2021年年度权益分派实施公告.
- **SZ300760 ex2022-05-19** — original PDF https://static.cninfo.com.cn/finalpage/2022-05-11/1213323180.PDF ; full SHA256 `c1c1447f63bbc9d6d7cbc25a70ef80b83b33faa4734a34218aac1df2e1eb623a`; first-page issuer 深圳迈瑞生物医疗电子股份有限公司, code 300760, title 2021年度权益分派实施公告.

All **89** locally archived original issuer PDF file bodies were rehashed against the frozen catalog. Three new proofs require first-page title/security, operative cash-only plan, two explicit current no-capital-change clauses, original capital/treasury/eligible counts, gross cash/ex-price arithmetic, official source URL date, unchanged prior notice/cash/date/rights metadata, original exact record/ex/scheduled-pay dates and conservative source availability from the **following** exchange day. No independently certified *intraday* publication timestamp exists for these PDFs. These were **previously archived** files rather than new downloads; original HTTP transmission-body bytes were not separately archived or reverified.

## Immutability and test outputs

Frozen EXP017 input full catalog SHA256 `fbe23fa6692f659c0e9990ce7aa27dabd156f818c4b91f4482e3a35fa3827eb4` (40 complete / 49 unknown). A new, separate **gitignored** EXP018 derived catalog SHA256 `62f50f8294adde17712136108b4e74fd84e18ddbe68ce04d3a5efb9042ba8122` has **43 complete / 46 unknown**: three new exact current-plan no-stock proofs filling six missing bonus/transfer zero categories; the other **86 original event records remain unchanged**. Original PDF, prior catalog, holder-eligible gross cash, issuer publication clock, broker-credit fields and frozen returns are untouched. Detailed metadata-only audit is `docs/experiments/2026-10-28_EXP018_treasury_excluded_current_cash_only_source_audit.json`, SHA256 `882bafbfa9ddb1289dd5859a70b9b6925748306316f74242db82188660cc98b3`.

Source module `src/quant_lab/pit_exp018_treasury_cash_only.py`; negative tests `tests/test_exp018_treasury_cash_only.py`; safe no-overwrite replay `scripts/mac_exp018.sh`.

**Authorized Mac state:** `YOUTangdeMacBook-Air.local` online; primary clean checkout HEAD `10abed9c2d3610d4f3b5172a456567d74396861a`. The actual bounded `git pull --ff-only` fetched remote head `a47f2204f3c88947264397c703de3a5507f847a4` but exited **128** because histories diverge. No rebase, reset, force push or claim that original Mac main is synced. An exact remote-head **detached worktree** at gitignored `runs/exp018_source_checkout_20261028/` was used for Mac CPU code, tests and immutable PDF replay. The remote publication/code-tree equality is recorded separately in the engineering log.

**Negative-fixture issue and repair:** First targeted run had **3 failures / 35 passes**, because three negative mutations looked for literal `3.2` although the positive fixture constructed `3.20`, silently changing no bytes. Corrected **test fixture replacements only**, without relaxing the production verifier. Targeted suite then **38 passed**; expanded full Mac CPU test suite **347 passed in 9.51 s**. One-command replay:

```bash
QUANT_LAB_ROOT="$PWD" EXP018_SOURCE_DIR="$PWD/runs/exp018_source_checkout_20261028" \
  bash runs/exp018_source_checkout_20261028/scripts/mac_exp018.sh runs/exp018_final_replay_20261028_001
```

Replay exited **0 in 134.89 s**, with **347 passed in 9.61 s**; nested EXP017 **309 passed in 8.37 s**, EXP016 **278 passed in 8.90 s**, and four older inherited source suites **257 passed** each. Complete 89 original PDF full-byte SHA source gate, 86 unchanged rows, no prior output overwrite and no broker/limit/fill certification were verified again. Audit file and derived catalog were deterministic across the initial source trial and this replay.

## Remaining financial BLOCK

**46/89** issuer original bonus/transfer proofs still incomplete; as-published issuer amendments and historical factor vintages, original end-date for first five SZ002024 2021 halt sessions, authoritative per-security/day price-limit/ST exceptions, opening-auction queue/partial real fills, unsellable/delisted nominal share valuation, actual holder cash/share posting and taxes all remain unresolved. No existing model, frozen P&L/order, historical test or raw source datum was altered. **Engineering tests/source proofs PASS ≠ real executable market-financial validity.**
