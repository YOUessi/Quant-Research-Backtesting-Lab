# EXP-013 — Five original-issuer current-implementation CASH-ONLY clauses complete two stock-rights zeros

Date: 2026-10-27. **Original PDF byte/SHA recheck and Mac CPU offline regression**, NOT issuer/broker account inventory, executable orders, historical as-published adjustment factors, alpha, a newly untouched test set, or capital-market performance.

## 1. New directly supported rights evidence

The frozen EXP012 catalog contained **89** source-backed gross-cash distribution events with **27 fully known stock+transfer rights and 62 incomplete**. A targeted second read of the **same already archived** original CNINFO issuer implementation PDFs found five documents explicitly stating the **current implementation ONLY distributes cash, with NO stock bonus and NO capital transfer**, immediately corroborated by the issuer's own statement that circulating-share change ratio is **zero**. This is not a zero inferred from an absent phrase, an aggregator, a later Qlib adjustment factor, or a brokerage receipt.

The guarded **separate EXP013 derivative catalog** thus has **32/89 fully source-evidenced rights and 57/89 incomplete**. The baseline original 27/62 catalog and prior EXP011/012 outputs remain unchanged/replayable. No earlier held-out strategy, historical quoted price, previous event cash amount, issuer announcement availability date, portfolio return, order/fill, or original raw document was changed.

The five genuinely new *proof classifications*, not newly downloaded PDFs or independently unseen dates, are:

| A-stock / ex date | Original issuer published day / earliest permitted exchange day | Original source / full PDF SHA256 | Gross pretax cash right per eligible original share | Direct issuer-rights finding |
|---|---|---|---:|---|
| **SH600703 / 2022-07-14** | 2022-07-08 / 2022-07-11 | [CNINFO PDF](https://static.cninfo.com.cn/finalpage/2022-07-08/1213983746.PDF) · `ea47709e05fe1bddc5693fea5716766f5cfc8f7688dcec7414971b17fcb1c25f` | CNY 0.100 | bonus 0, transfer 0 |
| **SH600705 / 2021-08-05** | 2021-07-28 / 2021-07-29 | [CNINFO PDF](https://static.cninfo.com.cn/finalpage/2021-07-28/1210580550.PDF) · `02e1a0bad42ae4ed00803c9d0df58df0e50a6ce268b0dc9ddced6e6d0daa65f7` | CNY 0.112 | bonus 0, transfer 0 |
| **SH600705 / 2022-07-07** | 2022-06-29 / 2022-06-30 | [CNINFO PDF](https://static.cninfo.com.cn/finalpage/2022-06-29/1213855504.PDF) · `17250533a9f1da13fd3b51a2e1b19b4659300bcea42f60f3f2985fb328bd2295` | CNY 0.152 | bonus 0, transfer 0 |
| **SH601318 / 2022-06-20** | 2022-06-11 / 2022-06-13 | [CNINFO PDF](https://static.cninfo.com.cn/finalpage/2022-06-11/1213675462.PDF) · `c3c7aa1b51962b1441c6d9a2cdafe6c66264323b2f4c39a2e9b30a6c180d0bd3` | CNY 1.500 | bonus 0, transfer 0 |
| **SH601318 / 2022-10-20** | 2022-10-13 / 2022-10-14 | [CNINFO PDF](https://static.cninfo.com.cn/finalpage/2022-10-13/1214757273.PDF) · `63ba8885c1954203bd16dacb4368fd169e611b3b997756c9c702bf7a275782b8` | CNY 0.920 | bonus 0, transfer 0 |

The original source PDFs and metadata were already obtained in earlier experiments; **no new issuer or vendor data was fetched in EXP013**. Full 64-character SHA256 values in the table were checked against local original bytes again. A supplemental parser verified the source was an original issuer PDF on CNINFO, the exact primary A-stock identifier and issuer implementation title (including the distinct `分红派息实施公告` wording), all original record/ex/scheduled-pay dates, exactly one matching explicit gross pre-tax cash amount, the frozen conservative announcement-day embargo, and absence of contradictory positive numerical stock-right clauses.

Two of these issuers disclose **differential cash dividends**. Proof of zero stock distribution does not transform issuer cash declarations into a universal market-price adjustment or broker settlement; record-date share eligibility, excluded treasury shares, taxes, net payable cash, real credited holdings and historic version history remain separate questions.

## 2. Source-derived result, with old evidence reproducibility preserved

The new module `src/quant_lab/pit_cash_only_original_completion.py` refuses unpinned original PDFs, incomplete SHA values, issuer/date/cash mismatches, positive stock-rights contradictions, earlier already-complete events, or unexpected additional literal matches. The rule requires an explicit **same-current-document** cash-only statement plus an adjacent statement that circulation shares do not change and the circulation-share ratio is zero. Boilerplate instructions (e.g., what would happen *if* stock dividends were issued) are not evidence.

The original parser, catalog, and all EXP011/012 numeric 27/62 source gates **remain unchanged**. The additive catalog is explicitly labeled `EXP013_SUPPLEMENTAL_DIRECT_CASH_ONLY_ISSUER_RIGHTS_CATALOG`, retaining every old unmodified event and preserving the original event-level proof grade for upgraded records.

In the Mac offline run:
- All **89** original issuer event PDFs were read and rehashed against their frozen complete source SHA256 identities; five passed the stricter *additional* direct-current cash-only proof (including the original PDF source publication/ex/payment and cash fields).
- Frozen baseline catalog complete SHA256: `255756a4e4cfe24c36259dcaf5336da8f93544b6da31419566c8d6c1be95329f`.
- New derivative catalog complete SHA256: `54c3a094fa49614145db2434180a6cf4326ba1c8abf807a9e667fa8b19b8cfcf`.
- Sanitized EXP013 audit summary SHA256: `6c79529e331e0f66bf455f16ea6ce5df86ebce5542fda24f65e507f677498bdd` (the local `source_audit.json` was copied byte-for-byte into `docs/experiments/` for code review).
- The source-only overlay leaves **all non-target event dictionaries byte-equivalent as parsed JSON** and retains original cash/announcement metadata for all 89 events; no broker credits were asserted.

## 3. Mac CPU verification and reproducibility

The connected Apple Silicon Mac `YOUTangdeMacBook-Air.local` first showed a clean checkout at `7f51c4dc85b53298c2b5ebd5ed2e39c65f07570d`. The instructed `git -c http.lowSpeedLimit=100 -c http.lowSpeedTime=15 pull --ff-only` succeeded, fast-forwarding to the exact GitHub main SHA `f5683ee0b0b42effcc0dfadc117b208125abae63` **before** any EXP013 changes. No gitignored source mirror or substituted Git version was used for this run.

Tests now include an explicit forbidden-weak-statement suite, positive bonus/transfer contradiction rejection, missing adjacent unchanged-shares statement rejection, 64-character SHA tamper rejection, preservation of existing known positive stock rights and cash evidence, proof identity matching and unchanged frozen rows. `python -m pytest -q` on Mac CPU returned **210 passed**. The replay script additionally runs the original EXP012 full offline proof, preserving its old 27/62 acceptance, then audits EXP013 with all 89 original PDFs; no trading strategy is retrained.

For an up-to-date Mac Git checkout with the previously archived gitignored original documents:

```bash
bash -n scripts/mac_exp013.sh
git diff --check
bash scripts/mac_exp013.sh runs/exp013_<new_unique_name>
```

The script refuses existing output folders; all output catalogs and original-source replays stay gitignored under `runs/`. It requires the original archived PDFs, original provider raw unadjusted CSV for the three older nominal-price examples and the existing Mac Python virtualenv. It makes no network requests, brokerage orders, data substitutions, or returns calculations. Full machine-readable sanitized audit: `docs/experiments/2026-10-27_EXP013_direct_issuer_cash_only_source_audit.json`.

## 4. Observed failures, fixes and remaining BLOCK gates

**Failures caught during development:** An initial too-broad issuer-header requirement rejected other legitimate *non-target* original PDF formats; it was restricted to the five new claims while maintaining complete SHA checks for all 89 documents. The next run rejected two legitimate **SH601318** originals titled `分红派息实施公告`, while matching only two other headline formulations. Added this literal implementation title without removing the required A-stock code, PDF SHA, dates or direct cash-only clause. The corrected original scan produced exactly five narrowly pinned documents, with no extra candidates silently promoted. Tests and the source replay were rerun after correction. No financial-source verification was disabled to make an originally unsupported claim pass.

**Unresolved:** The derivative catalog still contains **57** events without complete issuer stock-rights evidence. Original revisions, point-in-time vendor factor vintages, exchange-authoritative ticker/day limit PRICE levels and ST exceptions, opening auction queue and actual partial fills, delisting/illiquid liquidation price, holder-specific dividend taxes/broker credited cash/new shares and the five remaining early SZ002024 full-period issuer-halt days are unverified. No assertion of realistic investment-grade mark-to-market, tradability, newly independent holdout or positive alpha follows from 210 passing CPU tests.

**Decision: original-source rights completeness improved, engineering/SHA test PASSED; broker/exchange-grade financial validity remains BLOCKED.**
