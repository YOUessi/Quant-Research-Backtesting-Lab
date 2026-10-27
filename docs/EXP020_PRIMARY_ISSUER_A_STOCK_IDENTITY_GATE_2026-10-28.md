# EXP-020 — primary issuer A-share identity gate for frozen original rights notices

**Evidence/engineering date:** 2026-10-28. **State:** archived original-source identity audit + Mac CPU regression; real tradability/P&L remains **BLOCK**. No portfolio strategy change, new backtest, fill simulation, broker order or financial performance claim.

## Problem: content-addressed PDF does not itself prove issuer A-share identity

All 89 issuer originals were previously pinned by complete SHA256 and dated original CNINFO PDF URLs, but the EXP019 source inventory did not enforce a **first-page primary A-stock code** against the exact event ticker. An issuer filing may simultaneously mention preferred shares, H shares or convertible-bond codes, and a matching six-digit number somewhere in its body is not an adequate primary-issuer identity proof. Reusing a genuine PDF for the wrong A-stock event could otherwise silently contaminate a source-level classification if the surrounding catalog provenance were weakened.

The new `pit_exp020_issuer_identity_gate.py` validates **all 89** full archived original issuer PDF bytes against frozen event SHA256, first-page *labeled* primary A-stock code and operative cash/equity implementation-notice title. It rejects H-only, convertible-bond and preferred-share labels, conflicting/missing primary headers, wrong exchange-qualified ticker, an incidental body code, and nonimplementation notices. The existing EXP019 `source_inventory` now calls the stricter first-page gate as part of its original-source audit. This is a verified **identity boundary**, not an inference that a cash-only description necessarily implies no stock distribution.

## Original archived source checks (no new PDF downloaded)

- Exact immutable EXP018 parent catalog SHA256: `62f50f8294adde17712136108b4e74fd84e18ddbe68ce04d3a5efb9042ba8122`.
- **89/89** complete original PDF SHA256 rechecked, original URL publication-day / notice chronology verified.
- **89/89** first-page primary A-share ticker codes agree with frozen event symbols. Code-label forms: **83** `证券代码`, **4** `股票代码`, **2** explicitly `A 股股票代码` with separate H-share lines (SH601336, 2021 and 2022). Matching a secondary/H/convertible instrument alone is explicitly rejected.
- First-page operative notice types: **81** `权益分派实施公告` and **8** `分红派息实施公告`.
- **43** complete, **46** unresolved issuer share rights unchanged; **13** historical lookback-only statements remain nonproof, with **33** other unresolved. **0** bonus/transfer rights newly promoted.
- Git-tracked metadata-only source audit: `docs/experiments/2026-10-28_EXP020_issuer_primary_A_stock_identity_audit.json`. Initial fully verified audit complete SHA256: `8a53f96169b7a226566f798d72d7c43c4dad7b3e9829419263f97ca8414ea1ef`. It contains only original event identities, dates, source URLs, complete source SHA256 and identity-classification flags, not full copyrighted PDF text, HTTP payloads, raw brokerage accounts or keys.

These are **previously archived** original PDFs rehashed from the Mac local source archive, not new issuer filings or an independently recaptured HTTP response stream. An A-stock identity/title match does not independently prove that later filing amendments or adjusted-factor publication vintages are exhaustive.

## Mac provenance and reproducibility

The authorized Mac `YOUTangdeMacBook-Air.local` was online. Original main was clean at `10abed9c2d3610d4f3b5172a456567d74396861a`. The required real `git pull --ff-only` **fetched** GitHub `main=d49b7e7494bdef1c71abb7eb2fa13a5c17810284`, then exited **128** due to divergent history; no force-reset, rebase, overwritten raw data, or original-main synchronization was claimed. Built a separate detached worktree from the **exact fetched GitHub commit** under gitignored `runs/exp020_source_checkout_20261028/`, parent Git tree `2dc33d6e7323afaadbead971f5b7846921f7e7ff`. Source data remain under ignored `data/pit/`.

The first targeted regression had **28 passes / 1 failure**: a malformed fixture placed the labeled stock header *after* the implementation title, and the validator initially accepted it. Corrected the **production source gate** to require the primary labeled header before the operative title, then reran EXP019+EXP020 targeted regression **48 passed**. No source requirement was relaxed.

Full original-source Mac CPU replay command (from parent Mac repository):

```bash
QUANT_LAB_ROOT="$PWD" \
  EXP020_SOURCE_DIR="$PWD/runs/exp020_source_checkout_20261028" \
  bash runs/exp020_source_checkout_20261028/scripts/mac_exp020.sh \
       runs/exp020_verified_original_source_replay_20261028_001
```

Expanded combined CPU tests **395 passed** (root 257 + EXP016 21 + EXP017 31 + EXP018 38 + EXP019 19 + EXP020 29); the nested immutable EXP019/018/017/016 and earlier evidence replays were reexecuted with no previous result overwritten. The runner also checks the final 89-identity audit and verifies the original 43/46 rights state. Run log in ignored `runs/exp020_verified_original_source_replay_stdout_20261028_001.log`. The full CPU replay **exited 0 in 182.51 seconds**. The derived full audit SHA256 is `8a53f96169b7a226566f798d72d7c43c4dad7b3e9829419263f97ca8414ea1ef`, identical to the independent first complete source trial.

**Strict separation:** engineering/source-origin controls can pass while real broker-holder cash/share receipts, true historical tradability, shareholder-specific settlement and executable P&L remain **BLOCK**.

## Remaining priority

Continue primary issuer proof on **46** unresolved current bonus/transfer-right events and their later amendments, then as-published adjustment factor vintages. Separately preserve the SZ002024 five original 2021 halt-end sessions as unknown until a complete independent issuer/exchange effective interval is obtained. Official per-security/day limit-up/down price levels, ST/exemptions, auction queue/broker fills, delisting settlement and shareholder-specific cash/bonus postings remain blocking. Do not tune the model or reuse previously examined performance tests as independent confirmation.
