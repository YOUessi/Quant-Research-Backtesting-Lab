# EXP-010 — issuer/fund publication-time embargo on an unresolved 2021 stock halt

2026-10-27. **SOURCE-TIMING SAFETY CHECK VALIDATED ON THE AUTHORIZED MAC CPU.** This is neither a new stock-halt full-interval proof nor a broker fill, verified cash settlement, historic adjustment-vintage proof, or an investment result.

## Motivation

EXP008/009 show that the final 5 out of 139 missing historical CSI300 constituent-days were SZ002024 on 2021-06-16, 17, 18, 21 and 22. The earlier original exchange/issuer dated evidence confirms the start of the initial halt but never supplies a separately identified actual end for that first reason-specific segment. Two independent ORIGINAL fund semiannual PDF disclosures published months later show the **eventual** 2021-07-06 reopening and interim fund stock mark CNY5.59; those reports are excellent *retrospective* corroboration and **not information available to a June 2021 model**.

The new `pit_source_time_guard.py` rechecks the full raw SHA256 of four archived original sources, re-parses the exchange HTML, broker HTML and two original fund PDF suspended-holdings pages, cross-checks the prior EXP009 source report, and enforces an exchange-calendar **next-session-after-publication** knowledge threshold whenever an intraday public availability time is not established. A source's accounting period-end date is never used as its publication timestamp. The only permissible conclusion from the exchange's initial notice is **halt START known**: it is not a substitute for original complete day-by-day exchange status. The five-day provenance grade remains unchanged.

## Verified original dated sources

| Original | Source publication day | First conservatively usable next exchange session | SHA256 of ORIGINAL bytes |
| --- | --- | --- | --- |
| [SZSE 002024 halt start](https://www.szse.cn/disclosure/notice/t20210616_586435.html) | 2021-06-16 | **2021-06-17** | `52670239516bcf63914d7111ceb722985f17eba196c0e14a390cfd68a00be3d3` |
| [Cinda Securities historical pause table](https://www.cindasc.com/osoa/views/a/20210630/43370.html) | 2021-06-30 | **2021-07-01** | `4c29ccffe3feeeded19247c1b0d6d153364d76f4b22928e47d078effe8c9c2ee` |
| [Rongtong Shenzhen100 2021 interim ORIGINAL PDF](https://pdf.dfcfw.com/pdf/H2_AN202108271512608109_1.pdf) | 2021-08-27 | **2021-08-30** | `3baaf3c769ab8def9f4228019711c8704ea87776e212a3d30defa36a2c1c5322` |
| [Zhongke Wotu Wojia 2021 interim ORIGINAL PDF](https://pdf.dfcfw.com/pdf/H2_AN202108311513451275_1.pdf) | 2021-08-31 | **2021-09-01** | `3477978651fc3ec8e881c389c3c65164acaf50c10cfe3e310955748fff359f0f` |

The pinned local **derived EXP009 JSON** has SHA256 `84bccd0af791395aae29b3813b86de3c648cab56aaee1c43a585e3bd57d6da15`, independently verified from its unchanged local bytes. These five SHA values refer to different files. No raw PDF, raw HTML, OHLCV, Qlib dataset, or fund holding feed is redistributed to GitHub.

## Measured outcome (2026-10-27 Mac CPU)

- Clean Git checked out `main` at `089721d84aad18edb980f6a3c25ed00bccf1c2f9` via successful **standard `git pull --ff-only`** before editing source. No isolated-mirror substitute was used for this run.
- Initial pre-change tests: **165 passed**. After new source, 11 additional test cases, and original-source offline audit: **176 passed in 15.28s**; complete CLI returned exit 0. Full one-command script replay also returned **176 passed in 11.52s**, and original-source integration assertions passed. A focused original-source replay read and SHA-verified all four original source files, checked issuer/broker wording and two PDF share-count/mark rows again, and ran the complete exchange-calendar availability gate.
- Across the five frozen June constituent sessions, **zero of five** could legally use either later fund report under the deliberately conservative next-session rule. The June 16 source's halt-*start* fact becomes eligible on June 17, so four remaining June days may use that start fact, but NOT assume that the entire first halt reason continued through June 22 or ended June 22. June 16 itself is embargoed because the exchange's notice has no verified intraday publication timestamp.
- Primary original effective full-interval coverage **remains 134/139**, with 5 of 139 receiving two independently published ORIGINAL-fund retrospective corroborations, never promoted to primary full-interval proof. The fund's 5.59 mark and reported July 6 open 6.15 cannot be used as a June 2021 model signal, arbitrary account valuation, or executable quote.
- Full strategy/benchmark frozen positions, original EXP002 performance, simulated fills and model weights are untouched. The audit output at `runs/exp010_source_publication_time_embargo_20261027.json` is local and gitignored.

### Reproduction

From a **current GitHub checkout** with the already present original PDF/HTML source bytes, prior EXP009 derived report and pinned Qlib exchange calendar in gitignored local directories:

```bash
bash scripts/mac_exp010.sh runs/exp010_repeat_<unique_suffix>
```

The script refuses to overwrite an existing result directory. It runs the full CPU regression suite, rehashes and reparses the original materials, validates all four next-session dates, asserts no fund publication leakage, writes an immutable derived audit, and does not retrain or alter any previous output.

## Obstacles and next research

**Resolved in engineering:** retrospective 2021 fund reports could be accidentally treated as June-available evidence if a developer used their June 30 financial as-of date instead of Aug 27/31 actual report-publication dates. Tests now catch backdating, publication-day optimistic use, source-hash absence and unsupported upgrading of source evidence.

**Still unresolved:** the first 2021 SZ002024 June 16–22 issuer-reason-specific halt end, 62 incomplete stock/bonus rights out of the audited 89 issuer cash events, contemporaneous published corporate-action factor vintages, per-security/day official limit price files and temporary ST rule histories, opening auction queue and broker fills, broker credits of dividends/bonus shares and official delisting settlement amounts. No real financial validity or independent future holdout has been established. The already-examined 2021–2022 EXP002 backtest remains frozen.

Repro gate debugged: the first `git diff --check` rejected a surplus trailing blank line added to `docs/ENGINEERING_LOG.md`; this was removed without changing original financial data. The subsequent clean-diff gate and full one-command replay both passed.
