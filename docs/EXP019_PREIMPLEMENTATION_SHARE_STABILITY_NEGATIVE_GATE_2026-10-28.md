# EXP-019 — issuer historical stability is not post-distribution no-stock evidence

**Engineering / evidence date:** 2026-10-28 (Asia/Tokyo). **Financial status:** original-source audit only; real execution and P&L **BLOCK**. No model training, portfolio return recomputation, simulated broker fills, factor vintage claims, authorized price-limit data, or use of an inspected test set as independent performance evidence.

## Why this increment matters

Prior experiments established **43 complete issuer share-right events / 46 unresolved** from 89 archived originals. During further inspection of the 46 unresolved notices, 13 implementation notices refer to a distinct interval: **between the dividend plan's announcement and its implementation/publication date**, issuer share capital had not changed. This does **not** prove that the dividend itself caused no bonus-share issuance or capital-reserve transfer on the ex-date. Mistakenly promoting it to zero new shares would create a falsely certain ex-dividend nominal-share multiplier and market value.

EXP019 adds a **source-hashed, read-only negative-evidence classifier**. No rights fields are changed or upgraded. In each annotated event both zero-stock flags and actual broker rights remain unverified. These findings are constraints against false evidence closure, not proof that new shares were issued or not issued.

## Exact source-audit result

- Full PDF byte SHA256 verified against frozen catalog for **89/89** archived issuer PDFs, with dated CNINFO original source URLs and publication order checked.
- Previously incomplete issuer rights: **46/89**, still **46/89**. Fully original-proven issuer rights: **43/89**, unchanged.
- **13** of the unresolved originals contain the pre-implementation interval-stability wording; **33** others remain unresolved without a matching annotation. “No regex match” must not be misreported as proving no such statements or no stock rights.
- Zero new certified share-rights events. No new derived rights catalog, no modifications to prior rights, cash amounts, issuer source PDFs, schedules, model outputs, or frozen transaction records.
- Public source-only machine audit lists each of the **46** unresolved original issuer source URLs, full PDF SHA256, event identity/date, *negative* evidence category, and at most three limited current-window excerpts. **No copyrighted PDF body or brokerage data is embedded**.

The 13 issuer events flagged for improper temporal extrapolation are:

| Ticker | Ex-rights/ex-dividend day | Original clause means only no capital change before implementation |
| --- | --- | --- |
| SZ000858 | 2022-06-29 | announcement → implementation |
| SZ002202 | 2021-08-17; 2022-08-15 | announcement → implementation |
| SZ002415 | 2021-05-28; 2022-05-26 | announcement → implementation |
| SZ002594 | 2021-08-06 | announcement → implementation |
| SZ002773 | 2021-06-11; 2022-06-08 | announcement → implementation |
| SZ002920 | 2021-05-21; 2022-05-20 | announcement → implementation |
| SZ300408 | 2021-06-17; 2022-06-10 | announcement → implementation |
| SZ300760 | 2021-05-28 | announcement → date of current notice |

Two concrete, complete primary-source identities (all 46 are in public metadata):

- SZ000858 2022 source `https://static.cninfo.com.cn/finalpage/2022-06-22/1213776669.PDF`, original complete SHA256 `938a9a8bc801ebbd1104f89756a6a11792e8aae85e6ad33c624399d51350fd18`.
- SZ300760 2021 source `https://static.cninfo.com.cn/finalpage/2021-05-21/1210027566.PDF`, original complete SHA256 `9d3d99c1e6948e406f0f7a87dde69a435f3b68463d8aa71c22c0e31a2def5547`.

Both examples document a **lookback capital-stability period**, not the actual issuance effect of the pending current cash/stock distribution. By contrast, EXP017/018 accepted a much narrower *current-implementation* no-change claim in combination with other direct issuer evidence, exact quantities and frozen whole-PDF hashes. EXP019 never generalizes either proof grade to other names.

## Frozen data provenance and fail-closed code

The exact input remains EXP018's immutable derived source catalog, SHA256:

`62f50f8294adde17712136108b4e74fd84e18ddbe68ce04d3a5efb9042ba8122`.

New module `src/quant_lab/pit_exp019_unresolved_rights_negative.py` refuses a different catalog digest, source PDF digest, invalid dated original URL, contradictory announcement-to-record/ex chronological order, duplicate source events, missing archive, invented nominal multiplier on an unresolved event, and an output path that already exists. It only emits a new audit in gitignored `runs/` and records **all 46 items as unresolved**. Regression suite `tests/test_exp019_unresolved_rights_negative.py` includes deliberately misleading lookback examples, positive sounding current phrases requiring separate review, source mutation, URL/day mismatch, premature information-use clock, full catalog version mismatch, and no-overwrite tests.

Actual original PDF bytes are locally archived read-only; independent raw HTTP transfer bodies are **not** archived and cannot be asserted to have been byte-rechecked here. No original intraday exchange disclosure timing or actual broker credit has been certified. Source audit PASS is not real-world fill/valuation validity.

## Reproduction and Git synchronization boundaries

The specified Mac `YOUTangdeMacBook-Air.local` was online. The primary Mac `main` was clean at `10abed9c2d3610d4f3b5172a456567d74396861a`. Actual bounded `git pull --ff-only` was attempted but GitHub HTTPS fetch remained unresponsive for more than two minutes and was stopped safely; **Mac primary main is NOT synchronized**.

Fallback source was reconstructed inside Git-ignored `runs/exp019_source_checkout_20261028/` from the **previously Mac-tested, GitHub-published EXP018 exact Git tree** `af4ecee721f82bb1c922c469a70444221c2a3675`. The sole subsequent GitHub change was the EXP018 engineering log; its **exact GitHub blob** `4fd79f13aa5f5cbb7ebc6c7561ed18ca0101cde2` was retrieved through the connector, materialized in this isolated worktree, and the index **pre-EXP019 Git tree** was verified as `7ccae81f470cdca4eab9c99979f9fea83ee26fa3`, exactly equal to GitHub current `cbe2c14f00b1e50fd08da517ccbe068787f6d33a` tree. No local original main reset/rebase/overwrite and no claim of ancestry synchronization.

Mac CPU offline replay, executed at the root with isolated source:

```bash
QUANT_LAB_ROOT="$PWD" \
EXP019_SOURCE_DIR="$PWD/runs/exp019_source_checkout_20261028" \
bash runs/exp019_source_checkout_20261028/scripts/mac_exp019.sh \
     runs/exp019_fresh_original_replay
```

After an **actual** safe original-main synchronization, the ordinary runner is `bash scripts/mac_exp019.sh runs/exp019_fresh_replay`. All replay destinations must be new and ignored.

**Mac CPU final verification:** the new targeted suite **19 passed**. Final combined test gate **366 passed in 9.47s** (257 root + 21 EXP016 + 31 EXP017 + 38 EXP018 + 19 EXP019). Complete immutable source replay returned **exit 0 in 152.37s** with inherited **347/309/278/257×4** test gates passing and 89 whole original issuer PDF SHA256 checks. Both first and final source-audit replays reproduce **13 pre-implementation only + 33 other unresolved = 46**, and the exact same sanitized audit full SHA256 `7cce3ce2ad58ae83a6cc4dcb3aadfcf599774ea2e26c1043c9e377fd587bb650`. Public audit: `docs/experiments/2026-10-28_EXP019_unresolved_rights_negative_source_audit.json`. The initial runner only counted root + new tests, **276 passed**; corrected to include the three inherited isolated test suites and verified all **366** without relaxing any production source gate. Claims of financial execution, published historical adjustment vintages, official per-stock/day ST limit prices or brokerage payment/stock settlement remain **BLOCK**.

## Next unresolved priorities

46 current issuer share-right events still need *current-implementation* original explicit stock/capitalization terms, later issuer revisions and contemporaneous published factor vintages. Five 2021 SZ002024 stock sessions need source-complete original halt end evidence. Official daily security-specific limits and actual auction fills, nominal untradable share marks, delisting proceeds, and holder-specific cash and share postings remain separate BLOCKs. Continue original source work before any model changes or independent performance evaluation.
