# EXP-022 — two original-issuer approved capital-transfer zeros without inventing bonus rights

**Source-verification date:** 2026-10-28 (Asia/Tokyo). **Evidence status:** issuer corporate-rights *partial* source certification; **real trading execution/P&L remains BLOCK**. No backtest rerun for strategy selection, no model adjustment, no broker/order fabrication, no original source replacement. This increments only two previously unknown **capital-reserve transfer** fields in an independent derived catalog, **not** a complete nominal share multiplier.

## The specific missing rights and original issuer sources

EXP021's frozen 89-event derived catalog (whole SHA256 `db49d725ffb28308c718a44521be11c304bed3ae5d386cc44f718117c5e50147`) still showed **44 complete / 45 unresolved**. Two SH600015 华夏银行 **A-share** ordinary-cash dividend implementation events were unresolved because **both bonus and capitalization transfer ratios** were null; the current issuer implementation notices show cash per old share but do not literally state no stock bonus or zero capital transfer.

This round newly downloaded and whole-file hashed **six official issuer-hosted originals** directly from the bank's investor-relations / temporary-announcements pages. Sources are not inferred from a scraped price panel or a secondary article; the originals visibly bear issuer A-share code 600015, fiscal plan, shareholder-meeting motion, and implementation identity.

| Role / evidence clock (conservative, exchange local) | 2020 fiscal distribution, ex-date **2021-07-09** | 2021 fiscal distribution, ex-date **2022-06-08** |
| --- | --- | --- |
| Board-published profit plan on issuer site | 2021-04-30; usable **2021-05-06** after May Day closure | issuer site 2022-05-05; usable **2022-05-06** (internal PDF signed 2022-04-30; **not** assumed available April 30) |
| Source plan SHA256 | `a88f3c5497bfbd082ec792a4ed4fa51c20896b50550e402cf6630c25629ea56d` | `6de4f0e3c69126f32fc14b939b65c19638f1bcffd320e3d44ef7f3d6822f614f` |
| Original board-plan explicit term | **Does not implement capital-reserve share transfer** for this fiscal distribution | **Does not implement capital-reserve share transfer** for this fiscal distribution |
| Approved at AGM (meeting held) | 2021-05-28 | 2022-05-20 |
| Original issuer AGM resolution hosted/usable | 2021-06-01 / **2021-06-02** | 2022-05-23 / **2022-05-24** |
| AGM resolution SHA256 | `41e8dd72bffba80f149d81dc1a002e5b6b825516421ec4358685533ea3b1ed4b` | `f6f710ffa519ac4f712df26947e9f41a6ed84d9d55c8c7c1ee289b32bf02ab9c` |
| Exact **named** AGM dividend motion, matching cash and old A-share base | Passed; cash **¥3.01/10 old shares**, 15,387,223,983 ordinary shares | Passed; cash **¥3.38/10 old shares**, 15,387,223,983 ordinary shares |
| Final current-implementation notice / earliest usable | 2021-07-05 / **2021-07-06** | 2022-05-30 / **2022-05-31** |
| Current original whole SHA256 (matches prior CNINFO original) | `0f1c725e105c0531c51644a3a2050f06908aa05742ea94b0796b25d1a8ddf1fa` | `1ad0a1fc1f0f00461c6822eed4e6547e5d9f96bfe1b7b752e11d044fbaae0e98` |
| Final issuer gross cash per share, linked to AGM | **¥0.301**, unchanged | **¥0.338**, unchanged |
| **New partial certification** | Capital transfer **0**; bonus **UNKNOWN** | Capital transfer **0**; bonus **UNKNOWN** |

Primary original issuer URLs, complete SHA256, date-only conservative use clocks, event IDs, and negative/non-claims are all in `docs/experiments/2026-10-28_EXP022_SH600015_issuer_approval_partial_transfer_source_audit.json`. Each of the 6 source PDFs is retained only under ignored `data/pit/exp022_exchange_original_20261028/`; originals and their HTTP transfer contents are not included in version control. Archived original 89 implementation PDFs were **also** rechecked by complete SHA256 and first-page A-stock identity, and the newly downloaded current issuer PDF bytes match the frozen original CNINFO hashes exactly.

The evidence chain is intentional: a **board proposal alone is not an implemented right**. The AGM resolution approves the exact named dividend proposal with matching cash/share base, and the final A-share implementation identifies the same annual AGM and per-share cash/base. This provides source-backed continuity for the explicit zero **capital-reserve transfer** of the approved distribution. However, none of the three notice types supplies an explicit **no bonus shares** statement adequate for the frozen rules, so **no full share-rights certification** is claimed. Later amendments, exact intraday web publication, and brokerage postings are **not** exhaustively established.

## Engineering and scope

New module `src/quant_lab/pit_exp022_issuer_approved_partial_transfer.py` refuses changed original file hashes, wrong A-stock headers/title/year, wrong AGM resolution or vote status, changed cash/share base, absent or contradicted explicit zero capitalization, publisher URL/date mismatch, unverified or premature source clock, already-specified rights, and output overwrite. It validates the **frozen EXP021 parent catalog whole SHA256** and rechecks all **89** archived original implementation PDFs. In the child catalog, only **two original transfer-null fields become 0.0**, while both original bonus fields remain null, full nominal multipliers remain null, and both remain **unresolved**. The other **87 event rows** are identical to the parent as JSON values, and original event cash, record/ex/availability dates, broker, factor-vintage, and actual trading flags are unchanged.

| Machine-checked finding | Before EXP022 | EXP022 |
| --- | ---: | ---: |
| Whole issuer implementation originals verified | 89 | 89 |
| Additional issuer-hosted independent original PDF files | 0 | **6** |
| Full nominal rights source-supported | 44 | **44** |
| Still missing full rights | 45 | **45** |
| Exact new partial capitalization fields resolved | — | **2** |
| Bonus fields resolved for those two events | — | **0** |
| Other event dictionaries modified | — | **0** |

**Derived (ignored) child catalog full SHA256:** `b29464c49a2e1abc7241d2e8148ccd00bd110e8b55b868726d6810e096873c00`.

**Public metadata-only audit full SHA256:** `34fb428eebf3ba87d44afca25f067783450ad2976ca88f2cd7c7d319371ea657`.

## Errors discovered and remediation

1. Official SSE archive URLs surfaced in a third-party announcement index responded HTTP 200 with **3,872 bytes of HTML**, not PDF. The downloader correctly refused them rather than saving an HTML challenge as a purported original. We instead located and downloaded the same specific documents on **the issuer's own official archived PDF pages** (source URLs above in machine audit).
2. The first new code version required the 2022 final document's cash phrase without the literal `人民币` appearing in the actual original. Tightened a **source-specific literal** to the original, preserving the cash/share and whole-SHA gates.
3. First Mac targeted test run returned **6 failed / 48 passed**. Two invalid-cash mutations raised `decimal.InvalidOperation` rather than an auditable ValueError (fixed fail-closed error type); two tampered-vote tests altered an unrelated AGM motion instead of the target motion (fixed test to target exact named motion); two source-clock tests expected the wrong failure diagnostic (fixed test setup to mutate the board plan's effective clock). The correction did **not** loosen production evidence gates.

Targeted Mac CPU regression rerun **54 passed in 29.45 seconds**. First original-byte source replay verified **89 archived originals + 6 issuer-hosted originals**, **44/45 unchanged**, **87 unaffected events**, **two transfer zeros**, and whole audit/catalog hashes above.

**Full inherited Mac regression and complete nested offline original-source replay** are run separately and their final output is recorded in `docs/ENGINEERING_LOG.md` after successful completion, rather than claimed from the first trial. Runner: `scripts/mac_exp022.sh`.

## Git provenance and executable use boundaries

Actual `git pull --ff-only` from authorized Mac fetched remote `main=bce50b13d6cf03a926ec682e0234733181db744e` then **refused divergence (exit 128)**. Primary Mac `main=10abed9c2d3610d4f3b5172a456567d74396861a` remains **clean but not synchronized**. No force/rebase/reset was used. EXP022 was built in a gitignored, detached worktree `runs/exp022_source_checkout_20261028/` from the exact GitHub remote HEAD and pre-modification tree `01cd74d4bf95ead18b2e440febbc610288149315`. An explicit unique `runs/*` output path and `git check-ignore` gate protect prior results.

After safe normal synchronization on the Mac, repeat with a fresh ignored output:

```bash
bash scripts/mac_exp022.sh runs/exp022_another_fresh_replay
```

Without modifying the original divergent `main`, the same verified isolated-source runner is:

```bash
QUANT_LAB_ROOT="$PWD" \
EXP022_SOURCE_DIR="$PWD/runs/exp022_source_checkout_20261028" \
bash runs/exp022_source_checkout_20261028/scripts/mac_exp022.sh \
     runs/exp022_another_fresh_isolated_replay
```

## Remaining hard blockers

**45** rights events still lack complete issuer bonus and transfer proofs. For SH600015 itself, bonus is still unknown, so no nominal-after-ex-date share multiplier is released. Source plan/meeting matching does not prove amendment-chain exhaustiveness, historic factor-vintage availability or broker credit. Independently, SZ002024's 5 stock sessions still need original halt termination evidence; exchange-specific daily individual ST and listing-exemption price limits and open-auction fill queues are not certified; nominal untradable stock, actual cash credit, delisting settlement and tax remain unresolved. Strategy real investability remains **BLOCK**, regardless of engineering source PASS.

## Final Mac CPU acceptance and this-run transport verification

An independent *fresh-path* replay was rerun on the authorized Mac after the original EXP022 development/tests, without modifying the frozen source PDFs, Qlib historical inputs, original workspace or prior replay outputs:

```bash
cd "$HOME/Documents/jobsearch/Quant-Research-Backtesting-Lab"
QUANT_LAB_ROOT="$PWD" \
EXP022_SOURCE_DIR="$PWD/runs/exp022_source_checkout_20261028" \
bash runs/exp022_source_checkout_20261028/scripts/mac_exp022.sh \
     runs/exp022_automation11_fresh_replay_20261028
```

**Observed exit 0 in 249.07s.** Full combined Mac CPU suite **487 passed in 42.49s**, independently followed by inherited full replay suites **433 / 395 / 366 / 347 / 309 / 278 / 257 / 257 / 257 / 257**, all passed. Fresh original-source replay verified **89 frozen issuer implementation PDF whole-file SHA256s**, **six distinct issuer-hosted original PDF whole-file SHA256s**, exact issuer A-stock/company/event/approval chains, 44 complete and 45 unresolved events, exactly two capitalization-transfer zeros, 87 completely unchanged other rows, and unchanged bonus unknowns and nominal multipliers. Derived catalog full SHA256: `b29464c49a2e1abc7241d2e8148ccd00bd110e8b55b868726d6810e096873c00`. Public metadata audit full SHA256: `34fb428eebf3ba87d44afca25f067783450ad2976ca88f2cd7c7d319371ea657`. Fresh output and test log are Mac-local and ignored by Git.

During this independent replay, a **new** bounded Mac original-main `git pull --ff-only` attempt (Git HTTP low-speed guard and Python 65s timeout) timed out at **65.22s** before any successful synchronization. The prior diverged original Mac `main` stayed at `10abed9c2d3610d4f3b5172a456567d74396861a` and was observed clean. All work remained in the Git-ignored exact-GitHub-`bce50b13d6cf03a926ec682e0234733181db744e` isolated checkout. A verified test run and deterministic issuer-rights reconstruction **do not** establish comprehensive amendment history, exchange/broker credits, executable trades or historically investable returns; all remain **BLOCK**.

Final publishing gate additionally detected one trailing whitespace byte in a new **test fixture**, corrected it, and reran the final combined Mac CPU suite: **487 passed in 42.98s, exit 0**. No production code, original PDF or derived source-audit bytes changed in this correction; `git diff --check` now passes.
