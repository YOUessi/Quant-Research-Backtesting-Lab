"""EXP019: immutable, source-hashed queue for unproved historical share rights.

A statement that share capital did not change *between plan announcement
and implementation* says nothing about whether the current dividend will
issue shares on its ex-date. Such statements must never prove zero rights.
This module is an audit/triage artifact, NOT a rights-upgrade operation.
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

from .pit_share_distribution import clean
from .pit_exp020_issuer_identity_gate import validate_original_header

PARENT_SHA256 = "62f50f8294adde17712136108b4e74fd84e18ddbe68ce04d3a5efb9042ba8122"
PARENT_KIND = "EXP018_SUPPLEMENTAL_TREASURY_EXCLUDED_CASH_ONLY_CATALOG"
AUDIT_KIND = "EXP019_UNRESOLVED_ISSUER_RIGHTS_NEGATIVE_SOURCE_QUEUE"
HISTORICAL_STABILITY = re.compile(
    r"(?:自)?(?:本次|20\d{2}年度)?(?:权益分派|利润分配|分配)方案披露至"
    r"(?:实施期间|本公告日).{0,30}?"
    r"(?:总股本|股本总额).{0,16}?"
    r"(?:未发生变化|未发生变动|保持不变)"
)
CURRENT_CHANGE = (
    "本次权益分派不会导致公司总股本发生变动",
    "本次权益分派实施后，公司总股本保持不变",
    "实施权益分派前后公司总股本保持不变",
)


def classify_unresolved_text(text: str) -> dict:
    """Return a NON-PROOF annotation: neither branch authorizes zero rights."""
    normalized = clean(text)
    matches = list(HISTORICAL_STABILITY.finditer(normalized))
    snippets = sorted(set(m.group(0) for m in matches))
    current_mentions = [s for s in CURRENT_CHANGE if clean(s) in normalized]
    return {
        "negative_evidence_class": (
            "PRE_IMPLEMENTATION_STABILITY_IS_NOT_POST_DISTRIBUTION_PROOF"
            if snippets else "UNRESOLVED_NO_SOURCE_GRADE_UPGRADE"
        ),
        "pre_implementation_stability_snippets": snippets[:3],
        "current_change_phrase_requires_separate_plan_review": bool(current_mentions),
        "current_rights_issuance_certified": False,
        "zero_bonus_certified_by_this_audit": False,
        "zero_transfer_certified_by_this_audit": False,
    }


def source_inventory(rows: list[dict], directories: list[Path]) -> tuple[dict[str, Path], int]:
    source_map: dict[str, Path] = {}
    for folder in directories:
        if not folder.is_dir():
            raise FileNotFoundError("Missing read-only original issuer archive: " + str(folder))
        for pdf in folder.glob("*.pdf"):
            data = pdf.read_bytes()
            if not data.startswith(b"%PDF"):
                raise ValueError("Invalid original PDF content")
            sha = hashlib.sha256(data).hexdigest()
            source_map.setdefault(sha, pdf)
    for row in rows:
        sha = row.get("issuer_original_pdf_sha256")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("Invalid frozen full original PDF SHA256")
        original = source_map.get(sha)
        if original is None or hashlib.sha256(original.read_bytes()).hexdigest() != sha:
            raise ValueError("Missing or modified full original PDF: " + row["event_id"])
        notice, url = row["announcement_day"], row["issuer_original_pdf_url"]
        if not re.fullmatch(
            r"https://static\.cninfo\.com\.cn/finalpage/" + re.escape(notice) + r"/\d+\.PDF",
            url,
        ):
            raise ValueError("Original issuer URL/publication-day identity mismatch")
        if not notice < row["earliest_usable_exchange_day"] <= row["record_date"] < row["ex_date"]:
            raise ValueError("Original publication-clock chronology mismatch")
        # EXP020: first-page A-stock / implementation identity, not bond or H-share label.
        validate_original_header(row, original.read_bytes())
    return source_map, len(rows)


def run(parent: Path, pdf_dirs: list[Path], out: Path) -> dict:
    if out.exists():
        raise FileExistsError("Never overwrite a previous EXP019 audit")
    raw = parent.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA256:
        raise ValueError("Incorrect frozen EXP018 full catalog SHA256")
    original = json.loads(raw)
    rows = original["events"]
    if (original.get("kind") != PARENT_KIND or
        original.get("issuer_events") != 89 or
        original.get("fully_verified_nominal_share_rights") != 43 or
        original.get("unknown_share_rights") != 46 or
        len(rows) != 89 or
        len({(r["symbol"], r["ex_date"]) for r in rows}) != 89):
        raise ValueError("Frozen event identities or completeness changed")
    files, hashes_checked = source_inventory(rows, pdf_dirs)
    unresolved = []
    for row in rows:
        if row["complete_rights_supported_by_issuer_original"]:
            continue
        if row.get("full_new_nominal_share_multiplier") is not None:
            raise ValueError("Unresolved current-share multiplier was silently invented")
        sha = row["issuer_original_pdf_sha256"]
        reader = PdfReader(BytesIO(files[sha].read_bytes()), strict=False)
        if not reader.pages:
            raise ValueError("Empty original issuer PDF")
        body = "\n".join(p.extract_text() or "" for p in reader.pages[:5])
        annotation = classify_unresolved_text(body)
        unresolved.append({
            "event_id": row["event_id"], "symbol": row["symbol"],
            "ex_date": row["ex_date"], "original_announcement_day": row["announcement_day"],
            "original_pdf_full_sha256": sha, "original_issuer_pdf_url": row["issuer_original_pdf_url"],
            "prior_bonus_per_nominal_share": row["bonus_shares_per_old_share"],
            "prior_transfer_per_nominal_share": row["capital_transfer_shares_per_old_share"],
            **annotation,
        })
    if len(unresolved) != 46:
        raise AssertionError("Unresolved issuer event count changed")
    classes = Counter(r["negative_evidence_class"] for r in unresolved)
    audit = {
        "kind": AUDIT_KIND,
        "input_frozen_exp018_catalog_sha256": PARENT_SHA256,
        "original_issuer_pdf_full_sha256_checked": hashes_checked,
        "total_issuer_events": 89,
        "previous_complete_share_rights": 43,
        "unresolved_share_rights": 46,
        "newly_certified_complete_rights": 0,
        "historical_stability_not_post_distribution_proof": classes.get(
            "PRE_IMPLEMENTATION_STABILITY_IS_NOT_POST_DISTRIBUTION_PROOF", 0),
        "other_unresolved_records": classes.get("UNRESOLVED_NO_SOURCE_GRADE_UPGRADE", 0),
        "new_derived_rights_catalog_written": False,
        "broker_receipts_or_actual_fills_certified": False,
        "vintage_factors_or_daily_limit_prices_certified": False,
        "original_inputs_or_old_outputs_modified": False,
        "unresolved_original_issuer_sources": unresolved,
    }
    out.mkdir(parents=True)
    (out / "source_negative_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--parent-catalog", type=Path, required=True)
    p.add_argument("--issuer-pdfs", type=Path, nargs="+", required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args()
    a = run(args.parent_catalog, args.issuer_pdfs, args.out_dir)
    print(json.dumps({k: v for k, v in a.items() if k != "unresolved_original_issuer_sources"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
