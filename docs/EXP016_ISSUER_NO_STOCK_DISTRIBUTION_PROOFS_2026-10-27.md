# EXP-016 — two directly stated no-stock-distribution issuer originals

**Date:** 2026-10-27. **Scope:** original issuer PDF evidence, full-byte SHA256 and conservative publication-day availability. **No** market orders, trading profit, broker receipt, authorized real exchange limit-price data, or new independent backtest is claimed.

## New original-source evidence

The already archived, unmodified **SH600887 伊利股份** current implementation PDFs contain the exact original clause:

> 本次权益分派不涉及派送红股或转增股本。

The clause appears in section **四、分配实施办法**, not in a hypothetical broker handling paragraph. This confirms that **the particular implementation** has neither stock bonus nor capital-reserve transfer. It does **not** retroactively prove any other issuer's implementation, an individual's broker statement, or any transaction's execution.

| Original issue fiscal year | Source notice day | Conservative first eligible Qlib exchange day | Record day | Ex-dividend day | Gross cash/share | Original PDF full SHA256 |
| --- | --- | --- | --- | --- | --- | --- |
| 2020 | 2021-06-03 | 2021-06-04 | 2021-06-10 | 2021-06-11 | CNY 0.82 | `757f3b72dc33925080addf7e3ee826047066c52b10c12ed607190ed70597fbef` |
| 2021 | 2022-05-26 | 2022-05-27 | 2022-05-31 | 2022-06-01 | CNY 0.96 | `9e2789f8a0c3e4716eefaa703e838301bb9200893a64aa2724913b15e939f18b` |

Original issuer PDF URLs:
- 2021: https://static.cninfo.com.cn/finalpage/2021-06-03/1210151060.PDF
- 2022: https://static.cninfo.com.cn/finalpage/2022-05-26/1213499389.PDF

On the authorized Mac, the entire archived PDF bytes of each notice were independently rehashed with `shasum -a 256` and matched the frozen EXP014 original row; its first-page issuer name, A-stock code and fiscal implementation title were inspected. The extracted original text contains one direct current-plan no-bonus/no-transfer statement. The existing issuer original record, ex-date and scheduled payment date parser matched all six day fields; the source pre-tax cash reader independently matched each original CNY/share figure. The source-audit script also rejects unrelated positive share distributions, altered source bytes, mismatched event identity, vintage/intraday or broker proof promotions.

The source dates are **date-only archival notices**, not verified intraday release timestamps. A conservative next-Qlib-session embargo is retained. The archived exchange calendar is not an independent exchange intraday dissemination log.

## Immutable source-accounting outcome

The 89-event original issuer catalog is **not** edited. A new derived `rights_catalog_exp016.json` is created only inside gitignored `runs/` and checked against frozen EXP014 source-catalog SHA256:

- Frozen source catalog: `f47b34380951ea998f9c494687d2d8f0f2355cea4bfd0ef000bf5eece6ea19d2` (**36 complete / 53 unresolved**).
- New derived catalog: `60a3187bff82f4d4a0eae82b3cbb83afc0749593a1ebcd817e17145cb7eb2d9d` (**38 complete / 51 unresolved**).
- New source audit: `c5d001d222a901563990664028ea0bd2c48809d38eb91a9b7912691d40d44e00`.

Exactly **two original current-plan issuer notices** resolve **four** previously UNKNOWN fields (2 × bonus-zero and capital-transfer-zero). The two upgraded rows get a nominal share multiplier of **1.0**; all remaining **87 rows are JSON-identical** to the frozen source catalog. All original issuer cash amounts, notice/record/ex/payment days, original URL and full source SHA remain unchanged. No issuer scheduled payment is converted into a broker cash receipt. This is a claim-level source-completeness upgrade, **not** a tradeable portfolio mark or market outcome.

The executable artifact is `src/quant_lab/pit_exp016_issuer_no_stock_proof.py`; it fail-closes on wrong/modified full PDF SHA, non-current issuer fiscal/year/title/code, missing literal, contradictory positive rights, stock-date/cash conflicts, source-era ambiguity and attempts to overwrite already evidenced terms. `tests/test_exp016_issuer_no_stock_proof.py` includes positive/negative and mutation guards. `scripts/mac_exp016.sh` enforces a new gitignored destination and recursively replays EXP012–015 primary sources before constructing this supplemental catalog. The public metadata-only audit is in `docs/experiments/2026-10-27_EXP016_two_direct_issuer_no_stock_proofs.json`; **no PDF bytes, brokerage files, raw quotes or Qlib prices were uploaded**.

## Real Mac CPU and original-evidence validation

- Mac `YOUTangdeMacBook-Air.local`, Python 3.12 virtualenv, CPU only.
- Full expanded test suite: **278 passed in 6.41 s** initially and **278 passed in 5.72 s** inside complete offline runner, up from EXP015 257; 21 new parametrized test cases.
- Full immutable source replay `QUANT_LAB_ROOT="$PWD" EXP016_SOURCE_DIR="$PWD/runs/exp016_source_checkout_20261027" bash runs/exp016_source_checkout_20261027/scripts/mac_exp016.sh runs/exp016_full_all_original_sources_20261027_2203` **exit 0** (64.20 s). Four nested inherited source/test gates each returned **257 passed**. Complete 89 original PDFs were rehashed; upstream EXP012–015 evidence/claims were revalidated with a separate final current-plan 2-PDF proof.
- Final audit checked all 89 event source digests, 2 new direct issuer zero-rights proofs, unchanged 87 non-target records, 38/51 source-rights tally, uncredited brokerage rights and no order-fills.

After obtaining an actually current Mac main checkout containing EXP016, reproduce with:

```bash
bash scripts/mac_exp016.sh runs/exp016_new_unique_replay
```

### Git divergence and safe source isolation

At run start GitHub `main=b5b9bcf2fb6e1b86df4619e7125387945fcca583`. Authorized Mac original `main=10abed9c2d3610d4f3b5172a456567d74396861a`, ahead 1/behind 1. The requested actual `git pull --ff-only` fetched `b5b9bcf` successfully, but **refused** to fast-forward because the histories had diverged; it returned exit **128**. Both commit trees were independently checked equal to `858098f8832535c19fff41fdf0057efd528a7104`, but commit histories are not equal. Neither original main HEAD nor its tracked working files were rewritten, rebased, reset or represented as synced.

To test exact canonical source without mutating that main checkout, a **detached Git worktree at the fully fetched exact `b5b9bcf` commit** was created under `runs/exp016_source_checkout_20261027`, which is explicitly gitignored. The new files and CPU verification were developed there, with the prior local original PDFs/Qlib calendar referenced read-only. The Mac primary checkout remains divergent until safely reconciled; tree equality alone does not resolve Git ancestry.

## Remaining hard BLOCK

**51/89** issuer events still lack full source-backed stock bonus/capital transfer; the separate 5 reason-specific early 2021 SZ002024 halt sessions still need original end-date proof. Original issuer correction histories and historical as-published factor vintages, per-security real daily limit prices, exact ST transitions, opening auction queue and fills, delisting proceeds, unsellable nominal equity marks, and holder-specific cash/share broker postings and taxes are all **unverified**.

**Engineering/source verification PASSED; real-market executable financial validity remains BLOCK.** No model fitting/threshold selection, frozen backtest return changes, fresh holdout claims, trade orders, or unauthorized paid feeds were introduced.
