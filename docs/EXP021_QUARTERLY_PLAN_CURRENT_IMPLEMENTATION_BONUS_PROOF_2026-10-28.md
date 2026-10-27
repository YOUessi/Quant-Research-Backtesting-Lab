# EXP-021 — frozen bonus-share unknown resolved by two contemporaneous issuer originals

**Evidence date:** 2026-10-28 (Asia/Tokyo). **Financial validity:** historical source-grade original rights verification only; real investable P&L / fills / shareholder account settlement remain **BLOCK**. No model training, no backtest recomputation, no simulated broker orders or strategy enhancement. This increment certifies **one missing original-share bonus right**, not a newly discovered actual trading result.

## Research question and new original source

Frozen EXP018 rights catalog contains 89 original issuer events, of which **43** have complete bonus plus capital-transfer ratios and **46** are unresolved. For the **SZ300751** 2020 fiscal distribution (ex-date **2021-05-18**, event `4172b0cd291fcc8ead62d3fa`), the **2021-05-10 approved implementation original** had already proven capital-reserve shares **0.8/new per old** and gross cash **CNY 1.50 per old nominal share**, but *did not independently supply an explicit zero bonus statement*. The bonus ratio was therefore correctly left unknown. That prevented a precise post-ex-date nominal-share multiplier.

This increment obtained an **additional historical primary source** directly from the Shenzhen Stock Exchange original issuer filing endpoint (Mac HTTPS response saved once to a **new gitignored** read-only-evidence path; no old PDF changed):

- **Earlier original issuer 2021 Q1 report (2021-04-28, issuer report no. 2021-041):** `https://disc.static.szse.cn/download/disc/disk02/finalpage/2021-04-28/f26e0b8e-fed8-42cb-92dc-5567c9d13ffa.PDF`
- **Complete original Q1 PDF SHA256:** `7875834e9055ac8914d9db533f1aa811fefeb6244c18f5c8ddfd315d3509e68f`. Byte count approximately **647 KiB** (see local filesystem; never tracked).
- **Already archived approved 2021-05-10 issuer implementation notice:** `https://static.cninfo.com.cn/finalpage/2021-05-10/1209949702.PDF`
- **Complete original implementation PDF SHA256:** `85d4cd86d50e4740767ed517454a7a1db69994ac5b6837e74ae11b3d7cf4984d`.

The quarter report refers to the **2020 annual distribution proposal** approved at the **2021-04-09 board meeting** and states **explicitly no bonus shares**, **8 capital-reserve transfer shares per 10**, and **CNY 15 per 10** before shareholder approval. **Critically, it was still a proposal as of April 28:** it explicitly said the 2020 AGM must still approve the terms. We do **not** treat that preliminary proposal alone as proof that a distribution took effect.

The later archived **May 10 implementation notice** independently states the April 30 shareholder approval, explicitly reports unchanged **bonus / transfer / cash per-share ratios from the approved proposal**, and states that the implemented plan is consistent with the approved plan. It confirms 8 capital shares per 10, cash 15 per 10, and before/after shares. A **separate 1,500-share capital increase** from equity-incentive exercise between original proposal and implementation is recorded, not confused with distribution bonus shares.

| Source-pinned arithmetic (issuer aggregate, not an individual's settled shares) | Count |
| --- | ---: |
| Earlier proposal base, 2021 Q1 report | 57,277,225 |
| Earlier proposed 8-for-10 capital transfer | 45,821,780 |
| Earlier hypothetical after-proposal count | 103,099,005 |
| Interim employee-option share exercise | **+1,500** |
| Final May 10 implementation old base | **57,278,725** |
| Actual announced 8-for-10 capitalization addition | **45,822,980** |
| Final implementation announced aggregate new base | **103,101,705** |
| Original-source explicit bonus ratio in Q1 plan | **0**, carried forward by approved unchanged-plan chain |
| Original-source capitalization transfer per old share | **0.8**, unchanged |
| **Declared nominal multiplier** | **1.8** |

Historical availability is conservative: quarter report dated 2021-04-28 is usable **no earlier than 2021-04-29**; final original implementation dated 2021-05-10 is usable **no earlier than 2021-05-11**; record day 2021-05-17, ex-date 2021-05-18. These are **date-only publishing conventions**, not certified intraday dissemination times. The original issuer promise of transfer to registration accounts is **not** independent proof of individual broker allocation/actual sellability; scheduled pay date remains **unknown in the frozen record**, regardless of contextual dates elsewhere.

## Engineering and exact source checks

Added `src/quant_lab/pit_exp021_cross_notice_bonus.py` as a strictly identity-pinned, fail-closed original-source evaluator. It requires the **entire original PDF SHA256** for both notices, first-page issuer/report type and fiscal year, explicit **no bonus** clause in the original 2021 Q1 proposal, the later AGM approval and literal unchanged-plan clause, effective cash/transfer ratios and both before-and-after issue arithmetic, historically available dates, original frozen event ID and all existing cash/source/broker flags. It rehashes and header-verifies **all 89** original implementation notices before any upgrade; a mismatched source, ratio, clock, claimant, or previous already-proven value refuses certification.

Immutable parent EXP018 catalog whole-file SHA256: `62f50f8294adde17712136108b4e74fd84e18ddbe68ce04d3a5efb9042ba8122`. New derived evidence catalog contains exactly **44 complete and 45 unresolved** of 89: only **SZ300751 / 2021-05-18** newly completes one **bonus=0** field and **multiplier=1.8**. The other **88 event rows remain byte-for-byte JSON-value equal**. No prior source, cash/dated fields, transfer ratios, shareholder payment flags, historical prices, model results, or frozen returns modified. The new catalog is **only** in gitignored `runs/`, and public tracked audit contains **source hashes/URLs and aggregate arithmetic only**, not the original PDF body.

### Reproduction on authorized Mac CPU

The Mac original main was clean but previously historically divergent at `10abed9c2d3610d4f3b5172a456567d74396861a`. Actual `git pull --ff-only` attempted in this run returned a GitHub HTTPS receive/reset error after ~199 s. We **did not** reset/rebase/modify or claim primary main synchronization. The isolated, gitignored detached source worktree `runs/exp020_source_checkout_20261028/` was originally created from the exact EXP020 published source, with base Git tree `9f3bf8bf8cbc1c30deee02d8d9cfa8d21bb5d14e` matching current GitHub `main`. The source module, tests, report, runner and audit are authored and verified in that isolated worktree; the Mac original checkout remains untouched.

Run after ordinary safe synchronization, or run with separate tested source while preserving the original checkout:

```bash
QUANT_LAB_ROOT="$PWD" \
EXP021_SOURCE_DIR="$PWD/runs/exp020_source_checkout_20261028" \
bash runs/exp020_source_checkout_20261028/scripts/mac_exp021.sh \
     runs/exp021_another_fresh_replay
```

Replay checks complete 89 frozen originals + extra new entire Q1 PDF; it inherits EXP020, EXP019, EXP018, EXP017, EXP016 and earlier regression/primary-source reruns. Output paths must not exist. **Mac CPU test result and source-audit hashes are separately recorded in the engineering log after verification**; do not infer success from this report alone.

## Strict non-claims and follow-up

This is **source-level completeness**, not evidence the brokerage account received all fractional/whole new shares, that shares can be sold on ex-date, that dividends are net-of-tax paid, that ex-price/factor as-of vintages are complete or that later issuer amendments are exhaustively archived. No authorized original exchange auction queue or actual broker transaction receipts. True execution and financial strategy validity remain **BLOCK**.

Continue the other **45** unverified issuer distribution events; check amended announcements and timing; SZ002024's five 2021 sessions lacking independently pinned halt end; historical per-security official daily limits and ST exceptions; delisted/untradeable positions and claimant-specific outstanding cash/new shares. Do not tune models or recycle inspected backtest holdouts.
