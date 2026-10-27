# EXP-014 — Four additional SHA-pinned original issuer stock-rights completions

Date: **2026-10-27**. Scope: offline original-document evidence and conservative issuer-rights accounting only. **NOT** actual brokerage settlement, historical factor-version validation, confirmed trading execution, delisting value, independent holdout, or investment-grade strategy performance.

## Summary: immutable 32/57 -> separate 36/53 catalog

The existing frozen evidence ladder remains intact: EXP012 original **27 known / 62 unknown**, EXP013 additive **32 known / 57 unknown**. This EXP014 step verified four *different, already locally archived original issuer implementation PDFs* by complete SHA256 and created another **additive** rights catalog: **36/89 complete and 53/89 unresolved**.

Two Shanghai Stock Exchange issuer PDFs explicitly state that the **current approved implementation only distributes cash** and that circulating shares do not change (including the issuer's `流动股份变动比例` literal typo). Two Shenzhen Stock Exchange issuer PDFs for the same company state the exact reporting-year decision **does not capitalize reserves and does not issue bonus shares**, and separately confirm the currently implemented plan agrees with the year-matched approved plan and share-capital records have not changed. For those two events, prior original analysis already independently proved zero bonus shares; only the missing capital-transfer category was upgraded.

Thus EXP014 adds **four event completions, six newly proven category zeros** (2+2+1+1), not six new issuers, new financial returns, new PDFs, new holdout data, or any broker receipt.

## Four original source proofs

| Source primary A-stock / ex-day | Issuer announcement / prior conservative first usable trading day | Original CNINFO issuer PDF / full original byte SHA256 | Tax-inclusive gross cash per eligible old share | Newly source-proven zero categories |
|---|---|---|---|---|
| SH600276 / 2022-07-05 | 2022-06-29 / 2022-06-30 | [original PDF](https://static.cninfo.com.cn/finalpage/2022-06-29/1213853521.PDF), `48b04cf9ac8bc55f84b1cfd6b91056ccc8e10760260a6501ea5de045819ef91d` | CNY 0.16 | zero bonus and zero capital transfer |
| SH601225 / 2021-07-09 | 2021-07-03 / 2021-07-05 | [original PDF](https://static.cninfo.com.cn/finalpage/2021-07-03/1210399285.PDF), `f40033ab555ffa4f8f02d9030f1a1bafe1305ab818f8e0e75f0148eb23f1b8b6` | CNY 0.80 | zero bonus and zero capital transfer |
| SZ300676 / 2021-07-07 | 2021-06-29 / 2021-06-30 | [original PDF](https://static.cninfo.com.cn/finalpage/2021-06-29/1210355525.PDF), `fe930ea2ab5fa604e77400435677832031a79129d5779cb752f1556ebb021c5c` | CNY 0.35 | zero capital transfer (prior zero bonus retained) |
| SZ300676 / 2022-07-06 | 2022-06-28 / 2022-06-29 | [original PDF](https://static.cninfo.com.cn/finalpage/2022-06-28/1213834897.PDF), `f318dbe9d4e53b1c6777a3760f41356bfee9ce1472bfc4b3baf02fd069df380f` | CNY 0.35 | zero capital transfer (prior zero bonus retained) |

Checks for **each** upgraded event: complete PDF SHA256 matched archived raw bytes; exact issuer A-stock identifier and implementation headline on first PDF page; exact event ID and pinned hash; relevant **current approved implementation** wording; no conflicting positive numeric share rights; original record/ex dates; exactly one original gross tax-inclusive cash amount; original URL announcement calendar date; and conservative earliest-usable-exchange-day chronology inherited from the frozen catalog. The module refuses new unreviewed source identities, incompatible years, weak generic zero narratives, conflicting positive rights, incomplete/mutated PDFs and changes to prior cash/broker fields.

**Notable schedule distinction:** For SZ300676 ex 2022-07-06, the old catalog's scheduled cash payment date is `null` because the original legacy SZ date parser required a comma after the record date. The original issuer PDF uses **no comma** but explicitly states record **2022-07-05**, ex **2022-07-06**, and scheduled cash payment **2022-07-06**. EXP014 adds a **source-identity-bounded literal parsing fallback** and records that source date in the audit proof. The already frozen catalog cash payment field **remains null**: this round does not retroactively recognize actual brokerage credit or rewrite old cash accounting.

For both 2021 and 2022 SZ300676 the source payment statement may discuss ChinaClear or brokerage *scheduled distribution mechanics*; **it is not any holder-specific confirmed cash receipt**. The code does not convert issuer scheduled payment into spendable cash, and it does not infer any newly delivered saleable shares or actual orders.

## Full source integrity and reproducibility

The connected Mac `YOUTangdeMacBook-Air.local` had clean local `main` at exact GitHub commit `94b7dca4da999446763e06b99031fcadd8868047`. Normal `git -c http.lowSpeedLimit=100 -c http.lowSpeedTime=15 pull --ff-only` was **attempted and failed**, reporting GitHub HTTPS throughput below 100 bytes/sec for the final 15 seconds. **Do not call this a successful Mac synchronization.** The untouched Mac checkout remains at that old SHA.

The GitHub connector downloaded six exact unchanged GitHub-source module files and the prior EXP013 runner at that commit into **gitignored** `runs/exp014_source_mirror_20261027/`. Mac `git hash-object` checks agreed with **all seven original GitHub blob SHAs** before testing; the mirror has an explicitly test-only `__init__` package path extender to fall back to unchanged base-SHA modules. All new code and tests were written and executed exclusively in this ignored mirror. All raw issuer PDFs, original unadjusted quotes, earlier JSON evidence and the checkout's tracked files remained unchanged.

Mac CPU results after correcting an early new-code typo:

- Initial expanded suite: **225 passed, 5 failed**. Root cause: `append_source_proof` referenced the undefined name `PINN` instead of `PINNED`; one-line fix in the **isolated new module**, no original validation relaxed.
- After fix: **230 passed** in 6.41 seconds (210 pre-existing tests plus 20 new tests, including parametrizations).
- Complete one-command offline replay: exit **0**, 52.38 seconds; Mac suite **230 passed**, prior original-source regression gates **210 passed** and **210 passed**; EXP012 issuer 89-source/27-62 original proofs, three SHA-verified raw unadjusted quote cases, EXP013 full 89-SHA/32-57 original-source proofs, and EXP014 all **89** original issuer PDF SHA files with **four exact additional approvals**.
- `bash -n` for the runner, new Python compile, clean tracked worktree and `git diff --check`: **passed**.

Canonical complete byte-digests reproduced on Mac:

| Artifact | SHA256 |
|---|---|
| Immutable EXP013 input rights catalog | `54c3a094fa49614145db2434180a6cf4326ba1c8abf807a9e667fa8b19b8cfcf` |
| EXP014 new derivative rights catalog (local, gitignored; not raw data) | `f47b34380951ea998f9c494687d2d8f0f2355cea4bfd0ef000bf5eece6ea19d2` |
| Sanitized public EXP014 source audit JSON | `a26b6b01bf8c87347f8b9ef338b59dd2c69fceefabb16e079d016d9c417eddfb` |

Run the source/CPU suite in a **future successfully updated** real Mac checkout:

```bash
bash -n scripts/mac_exp014.sh
bash scripts/mac_exp014.sh runs/exp014_new_unique_replay
```

Or replay the actually tested local isolated implementation without advancing Mac Git:

```bash
QUANT_LAB_ROOT="$PWD" EXP014_ISOLATED_SOURCE_DIR="runs/exp014_source_mirror_20261027" \
  bash runs/exp014_source_mirror_20261027/scripts/mac_exp014.sh \
  runs/exp014_another_unique_isolated_replay
```

Both refuse pre-existing run destinations and require original SHA-pinned locally archived PDFs. Sanitized machine-readable evidence is in `docs/experiments/2026-10-27_EXP014_original_issuer_zero_rights_source_audit.json`. No original PDF, vendor feed/HTTP source, raw unadjusted price dataset or broker trade was newly downloaded or overwritten.

## Remaining strict BLOCK

**53/89** original issuer cash-right events still have incomplete bonus/transfer proof. Source amendment/revision histories and independently as-published factor vintages, the 5 remaining SZ002024 2021 full halt-days, official per-security/per-day actual up/down limit PRICE levels and ST exceptions, auction queues/partial fills, delisting cash settlement, unsellable nominal share valuation, and holder-specific actual broker share/cash credits remain unresolved. This fixes evidence completeness, **not financial backtest validity**.

No frozen EXP002 strategy/price/return history was rewritten, no model was tuned, no observed window relabeled as untouched test data, and no verified brokerage transaction is asserted.
