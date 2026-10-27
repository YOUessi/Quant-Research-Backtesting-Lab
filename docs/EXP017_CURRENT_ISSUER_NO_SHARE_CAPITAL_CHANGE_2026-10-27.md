# EXP-017 — Two cash-only issuer implementations explicitly preserve total share capital

**Date:** 2026-10-27. **Scope:** original CNINFO issuer PDF bytes, complete SHA256, contemporaneous document dates and conservative availability. **No strategy rerun, portfolio return, real broker fill, broker entitlement credit, new paid feed or model fitting.**

## New issuer-original evidence, with restricted source inference

The archived **SZ300142 云南沃森生物技术股份有限公司** original `2020年年度权益分派实施公告` (2021 execution) and `2021年年度权益分派实施公告` (2022 execution) each state, in their **current** `五、公司总股本变动情况` section:

> 本次权益分派不会导致公司总股本发生变动。

In both announcements the same section prints **identical before/after total share counts**. The implementation scheme itself specifies a cash dividend and **does not** state any issued bonus shares or capital-reserve conversion. Taken together, the contemporaneous issuer statement that *this particular distribution does not change capital*, the unchanged exact before/after count, and cash-only implementation wording support **zero stock-bonus and zero capital-transfer issuance for these two current distributions**. The proof does **not** generalize a mere missing mention, an unchanged company share count in some unrelated report, or the SSE boilerplate `差异化分红送转：否` into zero rights. Boilerplate in option-plan adjustment sections mentioning possible future capital transfers is not evidence of an actual transfer.

| Issuer event | 2021 current distribution | 2022 current distribution |
|---|---|---|
| Symbol | SZ300142 | SZ300142 |
| Original announcement day | 2021-05-12 | 2022-04-20 |
| Conservative first usable Qlib exchange session | 2021-05-13 | 2022-04-21 |
| Registered shareholder record day | 2021-05-18 | 2022-04-25 |
| Ex-date | 2021-05-19 | 2022-04-26 |
| Issuer *scheduled* cash payment (not actual broker credit) | 2021-05-19 | 2022-04-26 |
| Original pre-tax cash per existing share | CNY 0.050 | CNY 0.027 |
| Before and after issued share capital (the issuer's declaration) | 1,566,186,984 shares | 1,601,571,884 shares |
| Original full PDF SHA256 | `d286a7ac7a16d4cd09d477d5df7e8d00ee9d766e509dafb7806997c10667af22` | `8589fb592fa05c8c3ac4a23c663661bc0a99541d33642eac4a95eb2007b1daa6` |
| Original primary PDF URL | https://static.cninfo.com.cn/finalpage/2021-05-12/1209958626.PDF | https://static.cninfo.com.cn/finalpage/2022-04-20/1212978701.PDF |

The original issuer PDF titles, dated URL identities, stock code, cash terms, shareholder registration/ex/issuer scheduled-payment dates, and the whole original PDF bytes were independently checked. Those issuer implementation notices include no source-certified *intraday* release timestamp. Publication is conservatively usable from the **following** Qlib session, not from the issue date itself.

## Immutable evidence and exact scope

The complete **89** archived issuer originals are rehashed and source identities checked on the Mac. Derived catalog starts from the **fully frozen EXP016** `38 complete / 51 unresolved` catalog, SHA256 `60a3187bff82f4d4a0eae82b3cbb83afc0749593a1ebcd817e17145cb7eb2d9d`, and writes a **new** gitignored catalog rather than editing original data, earlier catalogs, PDF bytes or historical study outputs.

Only two pinned SZ300142 event identities gain two source-supported zero stock-right fields each (four fields total), giving **40/89 complete, 49/89 unresolved**. The other **87** event dictionaries remain byte-for-byte JSON-equivalent to the prior source, and all 89 original dates, cash-claim amounts, PDF hashes and issuer URLs remain unchanged. Neither current shares, broker stock delivery nor the cash entitlement is falsely marked as an actual broker posting.

The exact source-proof grade is `CURRENT_ISSUER_IMPLEMENTATION_DIRECT_NO_SHARE_CAPITAL_CHANGE_EXP017`. This is deliberately distinct from EXP016's directly stated `不涉及派送红股或转增股本` category. The current issuer no-share-change statement plus cash-only plan supports an inference of no *new* share issuance under the **two reviewed distributions**; it is not a certified shareholder-by-shareholder brokerage settlement record. An event outside these two hash-pinned originals is **never** upgraded by this module.

New production module: `src/quant_lab/pit_exp017_no_share_capital_change.py`. New regression tests: `tests/test_exp017_no_share_capital_change.py`, including altered PDF hashes, wrong issuer/financial year, prior/other sections, nonzero issued shares, forged proof metadata, silent share-right overwrite, and source clock/cash invariance. Exact replayer: `scripts/mac_exp017.sh`. Machine-readable issuer-only metadata: `docs/experiments/2026-10-27_EXP017_two_current_issuer_capital_unchanged_source_audit.json`.

## Mac CPU validation and Git boundary

On `YOUTangdeMacBook-Air.local` the mandatory `git pull --ff-only` fetched the exact GitHub EXP016 head `754b121550ec6235306aabac793efe52f3b5f4c1` but exited **128** (local `main` commit `10abed9c2d3610d4f3b5172a456567d74396861a` has different ancestry). We did **not** claim that Mac primary checkout was synchronized or reset/rebase/overwrite it. Instead, an exact detached Git worktree at the remotely fetched EXP016 commit was created under gitignored `runs/exp017_source_checkout_20261027/`; the original local PDF archive was read-only.

Offline replay, with prior original-source gates, is:

```bash
QUANT_LAB_ROOT="$PWD" EXP017_SOURCE_DIR="$PWD/runs/exp017_source_checkout_20261027" \
  bash runs/exp017_source_checkout_20261027/scripts/mac_exp017.sh \
  runs/exp017_full_original_replay_20261027
```

After the Mac primary checkout is **actually** updated to the EXP017 remote commit in a safe history-preserving way, the ordinary form is `bash scripts/mac_exp017.sh runs/exp017_unique_replay`. Any existing run destination is rejected. Full source-catalog and whole-PDF SHA checks precede an auditable 2-event replacement; the next session, scheduled cash and broker credit fields are separately enforced.

**Final validation record:** see this run's `docs/ENGINEERING_LOG.md` EXP017 entry and machine-readable audit, cross-checked with the Mac command output. Mac verified suite: **309 passed**, full inherited source replay: **exit 0**, 89 full original SHA checks, 87 untouched rows, 38/51 → 40/49, derived catalog full SHA256 `fbe23fa6692f659c0e9990ce7aa27dabd156f818c4b91f4482e3a35fa3827eb4`.

## The financial BLOCK remains

Still outstanding: 49 incomplete original issuer share-right events; historical issuer amendments, old factor **as-published** vintages, 5 residual SZ002024 early-2021 halt sessions lacking original original-end-date proof, security/day official price limits and ST changes, cash/stock broker account credits, partial opening-auction order-queue fills, delisting cash proceeds, tax and unsellable nominal positions. None of these is proven here. Public-source and regression proof **PASSED**; executed-market and independent-investment performance validity **BLOCK**. No frozen portfolio orders or performance figures were modified.
