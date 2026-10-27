"""EXP020: source-first issuer A-stock identity for historical equity notices.

An issuer notice may mention preferred share, convertible bond and H-share codes.
Never promote a receipt or rights claim unless the *primary, labeled A-stock*
code on page one matches the event symbol. This verifies issuer identity ONLY.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

from pypdf import PdfReader

PARENT_SHA256 = "62f50f8294adde17712136108b4e74fd84e18ddbe68ce04d3a5efb9042ba8122"
PARENT_KIND = "EXP018_SUPPLEMENTAL_TREASURY_EXCLUDED_CASH_ONLY_CATALOG"
AUDIT_KIND = "EXP020_PRIMARY_A_STOCK_ISSUER_NOTICE_IDENTITY_AUDIT"
_STOCK_LINE = re.compile(
    r"(?m)^[ \t]*(?P<a>A[ \t]*股[ \t]*)?(?P<label>股票|证券)"
    r"[ \t]*代码[ \t]*[:：][ \t]*(?P<code>\d{6})(?!\d)"
)


def check_first_page_text(text: str, symbol: str) -> dict:
    """Validate the page-one *primary* stock label, not body/code mentions."""
    if not re.fullmatch(r"(?:SH|SZ)\d{6}", symbol):
        raise ValueError("Invalid exchange-qualified A-stock symbol")
    matches = list(_STOCK_LINE.finditer(text))
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous labeled A-stock header")
    match = matches[0]
    title_position = text.find("实施公告")
    if title_position >= 0 and match.start() > title_position:
        raise ValueError("Missing or ambiguous primary A-stock header before notice title")
    if match.group("code") != symbol[2:]:
        raise ValueError("Original A-stock code disagrees with event symbol")
    compact = re.sub(r"\s+", "", text)[:480]
    if "实施公告" not in compact:
        raise ValueError("Missing current implementation-notice title")
    if "权益分派" in compact:
        title = "EQUITY_DISTRIBUTION_IMPLEMENTATION"
    elif "分红派息" in compact:
        title = "CASH_DIVIDEND_IMPLEMENTATION"
    else:
        raise ValueError("Original notice not identified as equity/cash implementation")
    return {
        "primary_a_stock_code": match.group("code"),
        "header_type": (
            "EXPLICIT_A_SHARE_STOCK_CODE" if match.group("a")
            else ("STOCK_CODE" if match.group("label") == "股票" else "SECURITY_CODE")
        ),
        "first_page_notice_type": title,
    }


def validate_original_header(row: dict, original_pdf_bytes: bytes) -> dict:
    """Full hashed primary PDF + page one, no false H/preferred/bond matching."""
    pinned = row.get("issuer_original_pdf_sha256")
    if not isinstance(pinned, str) or hashlib.sha256(original_pdf_bytes).hexdigest() != pinned:
        raise ValueError("Original PDF full SHA256 mismatch")
    if not original_pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Not an original PDF byte stream")
    reader = PdfReader(BytesIO(original_pdf_bytes), strict=False)
    if not reader.pages:
        raise ValueError("Empty original issuer PDF")
    return check_first_page_text(reader.pages[0].extract_text() or "", row["symbol"])


def run(parent: Path, pdf_dirs: list[Path], output_dir: Path) -> dict:
    if output_dir.exists():
        raise FileExistsError("Never overwrite an earlier EXP020 source identity audit")
    raw = parent.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA256:
        raise ValueError("Frozen EXP018 original-rights catalog SHA256 mismatch")
    catalog = json.loads(raw)
    rows = catalog["events"]
    if (catalog.get("kind") != PARENT_KIND or
        (catalog.get("issuer_events"),catalog.get("fully_verified_nominal_share_rights"),
         catalog.get("unknown_share_rights")) != (89,43,46) or
        len(rows) != 89 or len({(r["symbol"],r["ex_date"]) for r in rows}) != 89):
        raise ValueError("Wrong baseline issuer rights and event identities")
    # EXP019 source_inventory supplies full PDF bytes and publication-clock gates.
    from .pit_exp019_unresolved_rights_negative import source_inventory
    files, validated = source_inventory(rows, pdf_dirs)
    audit_rows = []
    for row in rows:
        header = validate_original_header(
            row, files[row["issuer_original_pdf_sha256"]].read_bytes()
        )
        audit_rows.append({
            "event_id":row["event_id"], "symbol":row["symbol"],
            "ex_date":row["ex_date"],
            "announcement_day":row["announcement_day"],
            "original_pdf_full_sha256":row["issuer_original_pdf_sha256"],
            "original_pdf_url":row["issuer_original_pdf_url"],
            **header,
            "issuer_notice_proves_broker_credit":False,
            "issuer_notice_proves_executable_order":False,
            "additional_share_rights_certified":False,
        })
    styles = Counter(r["header_type"] for r in audit_rows)
    categories = Counter(r["first_page_notice_type"] for r in audit_rows)
    audit = {
        "kind": AUDIT_KIND,
        "input_frozen_exp018_catalog_sha256":PARENT_SHA256,
        "full_original_pdf_sha256_checked":validated,
        "primary_stock_first_pages_verified":len(audit_rows),
        "header_type_counts":dict(sorted(styles.items())),
        "first_page_notice_type_counts":dict(sorted(categories.items())),
        "complete_share_rights_unchanged":43,
        "unresolved_share_rights_unchanged":46,
        "newly_proven_share_rights":0,
        "broker_credit_or_executable_fills_proven":False,
        "historical_factor_vintages_proven":False,
        "raw_source_or_prior_results_modified":False,
        "issuer_original_event_identity_audit":audit_rows,
    }
    output_dir.mkdir(parents=True)
    (output_dir/"issuer_notice_identity_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2)+"\n", encoding="utf-8"
    )
    return audit


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--parent-catalog",type=Path,required=True)
    p.add_argument("--issuer-pdfs",type=Path,nargs="+",required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    opts=p.parse_args()
    a=run(opts.parent_catalog,opts.issuer_pdfs,opts.out_dir)
    print(json.dumps({k:v for k,v in a.items() if k!="issuer_original_event_identity_audit"},
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
