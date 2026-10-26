# EXP-008 preregistered original-issuer research: 35 unresolved missing constituent stock-days

Committed before obtaining the newly targeted issuer PDF body content. This is a data validity investigation, not a model/return/strategy change.

## Frozen outstanding Qlib member-day date gaps (EXP002, 2021–2022)

| Symbol | Unresolved stock-session gaps | Evidence family to audit |
|---|---:|---|
| SH601108 | 6: 2022-03-31 through 2022-04-11 | Official rights-offering issuer halt/resume timetable |
| SZ002142 | 6: 2021-11-24 through 2021-12-01 | Issuer original rights-offering subscription/settlement and resume |
| SZ000425 | 12: 2022-08-01 through 2022-08-16 | Cash-option issuer stock halt, effective end of option exercise + original resume |
| SZ002024 | 6: 2021-06-16 through 06-22 (5) and 2022-05-05 (1) | Original stock halt start, interim continuation/new halt and single-day risk-warning halt |
| SZ002812 | 5: 2021-06-16 through 06-22 | Original stock halt and distinct original resume announcement |
| **Total** | **35** | Only accept original issuer PDFs and independent historical Qlib no-price check |

Prior EXP007 issuer-proven 104 / 139 missing member-day bars remain unchanged. This round may increase source coverage but MUST NOT retroactively turn any portfolio model fill into an actually executed order.

## Source gates

- Download bounded (<=8 MB) source PDFs only through https://static.cninfo.com.cn/finalpage/ original issuer announcement links, from historical CNINFO index. Store raw PDFs locally under gitignored data/pit/, hash SHA256 and document publication date.
- First identify exact **company A-stock**, not bond, trading-effect event and its effective full-session halt/resume dates. For rights-offering, corroborate subscription and clearing day range; for cash-option event, require actual **resume** and no assumed maximum date.
- A historical PDF may contain projected durations, technical consequences for bond conversion, future-dated listing events, or an issuer's retrospective mention. These are NOT certified stock suspensions on their own.
- Cross-match each exact ticker/session to the 139 known missing/invalid Qlib constituent-days and the full exchange calendar; never fill stock bars, never mark non-halt days automatically tradable.
- Any interrupted or resumed-midday case must be reported separately and must not be treated as full-day suspension unless the original effective dates support it.
- No source may establish executed next-open fills without licensed auction queue/broker trade receipts; historical limit-up/down price level access remains independently blocked.

Record both new proofs and incomplete/rejected source candidates, even where no new intervals can be certified.
