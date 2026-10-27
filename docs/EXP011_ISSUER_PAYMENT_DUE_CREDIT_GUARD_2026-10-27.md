# EXP-011 — issuer scheduled dividend pay date is NOT broker cash credit

Date: 2026-10-27. **Mac CPU + SHA-pinned original issuer source replay complete. Engineering correction only; NOT actual holder-account settlement, executable order data, financial alpha or independent backtest.**

## Priority and observed accounting defect

Previous `pit_nominal_book.simulate_nominal_right` correctly identified gross pretax entitlements on the ex-dividend date but, once the original issuer's **scheduled** cash payment date appeared in the quote calendar, it moved the whole gross claim to `cash_schedule_only` and zeroed `pretax_receivable`. Although a disclaimer said "not broker confirmed", this cash-like balance could be misinterpreted or improperly reused as spendable settled cash. The old routine also stopped the quote sequence at the issuer payment day and refused a quote window ending before that day.

**EXP011 fixes these accounting semantics, not old strategy results:** the gross pretax receivable is retained as *unreconciled* on and after the issuer scheduled date, `cash_schedule_only` remains zero, the status explicitly becomes `ISSUER_SCHEDULE_REACHED_CREDIT_UNVERIFIED`, and later quote dates remain available. No broker cash/share receipt is invented. If the stated payment date lies beyond the available market quotes, it is preserved as a **known issuer schedule**, not removed from the event. `broker_payment_verified=True` is still rejected absent a separate actual credit record.

An unverified gross receivable is a **scenario accounting claim, not a broker-confirmed cash or reliably priced balance-sheet asset**, and a source-supported share distribution is not a brokerage-confirmed credit or sellable position.

## Original public evidence (reparsed and full-byte SHA256 verified)

The offline source-integrity flow reprocessed **89** archived company implementation PDFs for original cash/bonus/transfer evidence, rechecked exact issuer company share-capital balances, and reproduced **27 complete / 62 incomplete** rights classifications without inventing missing zero terms. Three previously selected positive share distribution examples also reverified independent original issuer PDF date/pretax-cash/rights clauses, including company-capital *derived* complementary zero where applicable.

| Ticker / ex date | Original issuer source | Original PDF full SHA256 | Archived unadjusted CSV full SHA256 |
| --- | --- | --- | --- |
| SH600276 / 2021-06-10 | [Company source](https://static.cninfo.com.cn/finalpage/2021-06-04/1210161820.PDF) | `b731dec60e78bc92eab572ed099ec9da59fed84d6f06bb35fab605f4cb00a2f4` | `a80ae4f88ba9270894a9b88fc85bc408ecac27eefa9eeb6b9ea78d1a56e387af` |
| SH600760 / 2021-06-24 | [Company source](https://static.cninfo.com.cn/finalpage/2021-06-16/1210238262.PDF) | `6ee4d90b8e4d0fc49420a70df6a3a1ea148ad5e2d0a99f208fbb2d8358ddfec8` | `3309549d85141db76af7673db4ab4dccd663dd40091861f3a17199b490eb9843` |
| SH603392 / 2022-04-21 | [Company source](https://static.cninfo.com.cn/finalpage/2022-04-15/1212921735.PDF) | `0ee03e64cad8b1b2ed6a2164f212f3d0ece474a99efa52f0dbcde2b021ecc7d1` | `c72a6230fc54f5a6935eb14466e0c4734befd0393b3397f331563169ca63560c` |

Source metadata JSON bytes are also SHA256-pinned in `pit_receivable_due_audit.PINS`; the original quote provider response **digest** is retained, but the original provider HTTP response bytes are not archived for independent second rehash. Raw original PDFs, downloaded quote CSV files and third-party datasets remain **gitignored on the authorized Mac**, not redistributed. Re-parsing originals does not prove every 2021–2022 historical version of a dividend adjustment factor or payment revision.

## Conservative no-trade nominal illustration, 1,000 shares hypothetically already owned at record date

| Security | Issuer scheduled pay day | Last archived daily quote | Source-backed nominal share **claim** after ex | Gross pretax claim still **unreconciled** at last quote, CNY | Broker credited cash verified, CNY |
| --- | --- | --- | ---: | ---: | ---: |
| SH600276 | 2021-06-11 | 2021-06-16 | 1,200 | 200 | **0 verified** |
| SH600760 | 2021-06-25 | 2021-06-29 | 1,400 | 240 | **0 verified** |
| SH603392 | 2022-04-22 | 2022-04-26 | 1,450 | 200 | **0 verified** |

The "0 verified" column means **no broker credit record is present**, NOT that the issuer did not pay or that the real account cash balance is definitely zero. Gross cash claims are not marked as tax-net receipts. Gross claim plus nominal share end-of-day quote is only a source-backed hypothetical valuation illustration. Venue limit prices, partial fills, auction queue priority, holder-specific tax/rights credit, original delisting cash proceeds, and the historical as-published factor vintage remain **unknown**. Previous EXP002/EXP007 historical return outputs were not recalculated or rebranded as new independent validation.

## Reproduction and engineering checks

From the current repository checkout on the authorized Mac, with locally retained original issuer PDFs, prior issuer cash-event evidence and public unadjusted quote CSVs:

```bash
bash scripts/mac_exp011.sh runs/exp011_<new_unique_name>
```

The offline script refuses to overwrite an existing research directory, runs the full CPU regression suite, regenerates original issuer share-rights and capital-balance analyses, rehashes/reparses the three original PDFs plus unadjusted quote CSV and source metadata files, then checks that scheduled pay days do **not** discharge the gross receivable or create spendable cash. It neither downloads nor alters historical original data. Derived demonstration data is saved to a gitignored `runs/` directory.

Mac validation after correction: **188 tests passed**, original 89 issuer cases and 27/62 completeness classifications independently regenerated, and all 3 original PDF/unadjusted-source due-date tests passed. `bash -n` and `git diff --check` passed. An initial intermediate run of the newly enlarged test suite was **186 passed / 1 failed** because a new regression tested rejection of incomplete original-rights metadata using fake PDF bytes, while the source implementation correctly rejected the fake PDF SHA first. The validation order was adjusted to enforce a fail-closed source-grade preflight *before* reading original bytes; both the publication-date and SHA gates are independently covered in unit tests. A second full offline replay passed.

Machine-readable derived case report: `docs/experiments/2026-10-27_EXP011_issuer_payment_due_receivable_audit.json`, copied unchanged from the passed Mac offline output; source report bytes SHA256: `37ec287316a06ca0e7faf5acc6848387568565013d14776946de4177c253ead0`. This audit contains proof metadata and claim balances, not original raw PDFs or raw quotes.

## Remaining BLOCK items (unchanged)

1. Actual issuer/broker cash and share-credit receipts, holder-specific tax withholding, dividend historical corrections, full stock rights for **62/89** currently incomplete audited events, rights on additional held securities, as-published adjustment factors.
2. Original first-halt reason-specific 2021-06-16–22 SZ002024 interval end still unproven (134/139 primary full sessions; 5 retrospective-only fund corroborations).
3. Original security/day authoritative price-limit levels, changing ST status/exemptions, opening order book + execution priority, official delisting settlement and reliable mark of stuck/nominal positions.
4. A **previously untouched** and preregistered evaluation set is still required after any model/strategy change. EXP002 2021–2022 is already seen.

**Research status:** accounting evidence fidelity improved; broker-level financial validity remains BLOCK.
