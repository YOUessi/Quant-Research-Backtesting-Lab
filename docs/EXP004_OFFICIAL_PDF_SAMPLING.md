# EXP-004 — Additional original issuer-document audit sampling plan

**Locked BEFORE new original issuer PDF requests or reviewing any results.**
This is a provenance audit, NOT a trading-model experiment. Trading model,
evaluation range and holdout metrics stay frozen.

## Source and sampling frame

- Study period: 2021–2022, historical CSI300 source pinned in EXP-002.
- Eastmoney implementation-event dates are historical metadata in a 2026
  source snapshot; they are NOT fully archived point-in-time vintages.
- First 19 symbols were purposely targeted; now draw **30 additional**
  names without replacing failed PDF/document cases.
- Stratified random sampling from unreviewed, successful source tickers
  having at least one 2021–2022 implementation event, NumPy RNG seed
  **20261026**, **15 SH + 15 SZ**, without replacement. Eligible pools:
  **SH=212, SZ=139**.
- Historical stock selection is for *data source audit only*. It is NOT
  an investment recommendation, market universe modification or alpha test.

### Exact frozen 30 symbols

    SH600010 SH600015 SH600085 SH600703 SH600741 SH600760 SH600845
    SH601009 SH601225 SH601336 SH601601 SH601881 SH601939 SH603392
    SH688111 SZ000100 SZ000786 SZ002032 SZ002142 SZ002202 SZ002311
    SZ002673 SZ002773 SZ002812 SZ002920 SZ300142 SZ300408 SZ300676
    SZ300751 SZ300760

## Evidence gates

1. CNINFO original issuer PDF found, publication calendar day available,
   PDF stock code and hash validated locally. This alone is NOT verified cash.
2. Cash must be a unique **gross/tax-inclusive** value from original PDF,
   not an after-tax value also present in the same document.
3. Cross-check same implementation announcement calendar day, per-share
   gross cash, record date and ex-date with the independent third-party
   record; keep ambiguous and unavailable cases.
4. Do not treat stock daily volume or Qlib price as observed order fill,
   historical adjustment-factor release version or cash settlement.
5. Do not discard a symbol with no official search result: mark it as
   source-coverage failure, not zero dividends.

Raw PDFs stay locally gitignored on Mac. Publish only minimal source
metadata, hashes, dates, statuses and count evidence.

## Reproducibility

GitHub source modules: src/quant_lab/pit_official_batch.py and
src/quant_lab/pit_official_recheck.py. The exact fixed selection above
precedes the issuer PDF audit; later model returns remain untouched.
