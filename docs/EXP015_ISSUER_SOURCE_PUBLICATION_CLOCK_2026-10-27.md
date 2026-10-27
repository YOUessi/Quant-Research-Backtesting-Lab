# EXP-015 — SHA-pinned original issuer source-clock and unresolved rights gate

Date: **2026-10-27**. Scope: original-document provenance, day-only release embargo, fail-closed stock-rights accounting. **No new trading PnL, official exchange status, order queue, broker credits, backtest-model improvement or untouched holdout.**

## Engineering addition and evidence

Introduced `src/quant_lab/pit_rights_publication_gate.py`, `tests/test_exp015_rights_publication_gate.py` and `scripts/mac_exp015.sh`. The verifier refuses modified full-byte source inputs and checks EVERY event in the frozen EXP014 issuer catalog against the existing archived original issuer PDF and historical Qlib exchange calendar, then evaluates three decision times per event (session before source first eligibility, first eligible session, record session).

| Strict recheck | Result |
| --- | ---: |
| Frozen EXP014 issuer events | 89 |
| Complete SHA256 of locally archived issuer PDF bytes | 89 / 89 match catalog |
| PDF first-page original A-stock and issuer announcement identity | 89 / 89 |
| Conservative original announcement day -> exact next historical Qlib exchange session | 89 / 89 match |
| As-of decision source/rights leakage probes | 267 / 267 pass |
| Explicitly complete bonus+capital rights | **36** |
| **Still incomplete** issuer stock rights | **53** |
| Missing both bonus and capital-transfer fields | **52** |
| Missing one rights category | **1** |
| Newly proven original stock-rights completions | **0** |

The single partially known event is **SZ300751 ex 2021-05-18**: capital-transfer ratio is independently known, bonus ratio remains **UNKNOWN**, so an after-ex nominal multiplier is deliberately withheld. It is not correct to count an unknown bonus ratio as zero. The other 52 incomplete events have neither stock-rights category fully established. All 53 remain censored even after their source became date-eligible.

The original notice date is a **calendar-day value from the previously audited CNINFO issuer record and exact archived URL**. It is NOT a proven intraday publication timestamp. The *next* historical exchange session is a conservative embargo for day-only disclosures. Even if a source is eligible, its bonus/capital fields remain unknown until independently supported; eligibility is not proof of broker credits, saleable shares, market orders, or historical execution.

## Exact data pins (no source redistribution or raw mutation)

- Frozen EXP014 derived rights catalog SHA256: `f47b34380951ea998f9c494687d2d8f0f2355cea4bfd0ef000bf5eece6ea19d2`.
- Already archived Qlib historical trading-day calendar SHA256: `245bb32a907fe942c1a4c3671e35c0c5f7ecbb73b5aae90bbbc4ff7e7e83ae46`, 6,494 sessions, 2000-01-04 through 2026-10-23.
- 89 original PDFs are matched by complete SHA256 to the immutable catalog and their first pages rechecked for A-stock and announcement identity. Exact per-event PDF SHA, source URL, status and release day appear in the offline full report; **53 unresolved event IDs and source SHA values** are included in the sanitized GitHub gap queue.
- No fresh source PDFs or official exchange timestamps were obtained. The archived Qlib calendar is a historical provider artifact, **not** independent authoritative exchange timestamp proof. The original HTTP provider response-byte history and subsequent issuer amendment/revision records remain unverified.

An original source **before** its earliest eligible session cannot be used. A numerically complete issuer share *claim* **after** eligibility still does not constitute holder-specific brokerage credit or sellable shares. The conservative event-source evaluator rejects incorrectly promoted intraday, factor-vintage or broker flags.

## Mac synchronization, isolated validation and observed fixes

At run start the connected GitHub `main` head was **`ce79305a1735ca66da51925e2d88d287a1e39be9`**. The authorized Mac `YOUTangdeMacBook-Air.local` had a **clean but older** real checkout at **`94b7dca4da999446763e06b99031fcadd8868047`**. The normal safe `git -c http.lowSpeedLimit=100 -c http.lowSpeedTime=15 pull --ff-only` **failed** due GitHub HTTPS low-speed timeout (15.73 seconds). **The tracked Mac Git checkout was not updated.**

The existing gitignored `runs/exp014_source_mirror_20261027` held the upstream source fetched earlier. This run re-read **eight exact GitHub repository paths at the full `ce79305a...` SHA** through the GitHub connector and confirmed their Git blob SHA against Mac `git hash-object`: EXP014 implementation, source parser dependencies, existing EXP014 tests, and runner. EXP015 changes were developed and tested exclusively in a new gitignored `runs/exp015_source_mirror_20261027` overlay, with unchanged exact-source modules available through the previous mirror and untouched old checkout. **Do not conflate isolated-source verification with Mac Git synchronization.**

Observed test corrections: (1) initial new-test collection failed because a long synthetic calendar fixture omitted one closing parenthesis; corrected the test syntax. (2) first enlarged suite returned **254 passed, 1 failed**, because the synthetic weekend test calendar omitted the immediately preceding historical trading session and the verifier correctly rejected a missing predecessor. Added that Friday to the *test fixture*; no production source/time guard was relaxed. Added two further tamper tests for source-day identity and independently pinned calendar hash.

Final Mac CPU:
- `bash -n` and `py_compile`: **pass**.
- Full checkout + both isolated EXP014/015 test modules: **257 passed** (230 previous, 27 new cases including parameterizations).
- Original EXP014 replay nested tests: **230 passed**, plus prior EXP013/012 replays **210 passed** and **210 passed**.
- Complete second offline source audit rehashed **89 issuer PDF files**, regenerated old 27/62, 32/57 and 36/53 catalogs, checked 89 notice-next-session dates and 267 time probes, and returned **exit 0**.
- Outputs stay in gitignored `runs/exp015_final_original_sources_replay_20261027_1920/`; the sanitized 53-item blocker queue is separately committed to `docs/experiments/2026-10-27_EXP015_source_clock_rights_gap_queue.json`. No original issuer PDFs, Qlib bars or frozen strategy returns were changed.

After a genuine later Mac fast-forward, rerun from a **fully updated real checkout** with the same authorized original sources:

```bash
bash scripts/mac_exp015.sh runs/exp015_new_unique_replay
```

For the **actually tested** isolated-source overlay without advancing the current Mac checkout:

```bash
QUANT_LAB_ROOT="$PWD" \
EXP015_ISOLATED_SOURCE_DIR=runs/exp015_source_mirror_20261027 \
EXP014_ISOLATED_SOURCE_DIR=runs/exp014_source_mirror_20261027 \
bash runs/exp015_source_mirror_20261027/scripts/mac_exp015.sh runs/exp015_new_unique_isolated_replay
```

## Remaining mandatory BLOCK

**53 incomplete issuer bonus/capital rights** remain, including one partially positive SZ300751 event; exact historical issuer corrections and independently *as-published* adjustment-factor vintages, 5 reason-specific original SZ002024 June 2021 first-halt stock-days, issuer-specific official daily limit PRICE files and all historical ST/exemption transitions, genuine auction queue/partial fills, delisting settlement and illiquid stock valuation, holder-specific tax/cash/share brokerage entries are not proved.

This round adds an auditable **source-time gate and actionable exact-SHA gap queue**; it does **not** upgrade financial backtest validity, invent stock rights or identify a new independent holdout.

## Later Mac synchronized-checkout independent source replay (2026-10-27)

After the earlier *isolated* verification described above, the authorized Mac connection recovered. This follow-up **successfully** executed the real `git -c http.lowSpeedLimit=100 -c http.lowSpeedTime=15 pull --ff-only` from local `94b7dca4da999446763e06b99031fcadd8868047` to exact GitHub `main` `ce79305a1735ca66da51925e2d88d287a1e39be9`; its worktree was clean before the change. The five EXP015 delivery files were individually compared against the previously tested local SHA-pinned bundle, copied to **new** tracked project paths, and the unmodified, original-source Mac environment reran `bash scripts/mac_exp015.sh runs/exp015_synced_checkout_full_sources_20261027_2105` with exit **0**. The synced-checkout suite and three nested suite gates each returned **257 passed**. All 89 archived PDF SHA256s, first-page identity checks, 89 exchange-calendar next-session publication gates, 267 decision probes, frozen predecessor source proofs and the 36/53 gap accounting were independently replayed. This is a second real-checkout verification, **not** a new source, fresh holdout or broker proof.

The public 53-event unresolved-rights queue exactly matches this run's local derived public summary (same bytewise SHA256 `3abbdcbf7f5c5fead3269176091f16096f4e34d06a3de7eb48ad83f416ff62ef`). The complete offline 89-event audit bytes SHA256 are `7eb7192a63a4d69fb417209a395f6beee41c57b3aa0951f28d8388913c23003e`, stored only in gitignored `runs/` with original inputs also left untouched. `bash -n`, Python compilation and diff integrity checks are independently run before publication. Completion remains **36/89**, unresolved **53/89**, with **0 newly source-established rights**.
