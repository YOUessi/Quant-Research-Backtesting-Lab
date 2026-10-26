"""Offline, deterministic recheck of already-hashed CNINFO issuer PDFs.

No new requests; uses unchanged original PDF bytes from the first audit.
An upgraded gross-vs-net extractor may resolve ambiguous statements but it
must never rewrite the earlier report or hide prior failures.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from pypdf import PdfReader

from .pit_official_batch import (
    extract_cash_candidates_per_share, extract_explicit_pretax_cash_per_share,
    strict_cash_match, is_issuer_dividend_implementation,
)


def rerate(original: dict, source_directory: Path) -> dict:
    if original.get("kind")!="LIMITED_TARGETED_OFFICIAL_ISSUER_PDF_AUDIT":
        raise ValueError("Not an original strict issuer-batch audit")
    updated=[]
    for old in original["documents"]:
        name=(f"{old['symbol']}_{old['official_notice_day']}_"
              f"{old['announcement_id']}.pdf")
        pdf=source_directory/"issuer_pdfs"/name
        if not pdf.is_file():
            raise FileNotFoundError(f"Audited source PDF missing: {pdf}")
        payload=pdf.read_bytes()
        digest=hashlib.sha256(payload).hexdigest()
        if digest!=old["issuer_pdf_sha256"]:
            raise ValueError(f"Historical issuer PDF bytes changed: {name}")
        page=PdfReader(pdf,strict=False)
        text="\n".join(p.extract_text() or "" for p in page.pages[:4])
        all_cash=extract_cash_candidates_per_share(text)
        gross=extract_explicit_pretax_cash_per_share(text)
        expected=old["thirdparty_per_share_pretax"]
        chosen=gross if gross else all_cash
        value=strict_cash_match(chosen, expected)
        if old["thirdparty_same_day_events"]>1:
            value["status"]="MULTIPLE_THIRDPARTY_EVENTS_SAME_DAY"
            value["cash_per_share_verified"]=None
        if (value["status"]=="PDF_CASH_MATCHED_TO_THIRDPARTY"
                and not old["issuer_pdf_ex_record_date_literals_both_present"]):
            value["status"]="PDF_CASH_MATCHED_DATES_NOT_CONFIRMED"
        rec=dict(old)
        rec.update(value)
        if not is_issuer_dividend_implementation(old["official_announcement_title"]):
            rec["status"]="NON_DIVIDEND_DERIVATIVE_NOTICE_EXCLUDED"
            rec["cash_per_share_verified"]=None
            rec["excluded_from_corporate_action_ledger"]=True
            rec["source_note"]=(
                "Issuer PDF may refer to equity distribution but is a "
                "convertible-bond halt, repurchase adjustment or pricing "
                "consequence, not the standalone dividend implementation."
            )
        else:
            rec["excluded_from_corporate_action_ledger"]=False
        rec["issuer_pdf_all_cash_amount_candidates"]=all_cash
        rec["issuer_pdf_explicit_tax_inclusive_cash_candidates"]=gross
        rec["gross_amount_context_used"]=bool(gross)
        rec["byte_hash_reverified"]=True
        rec["status_before_parser_revision"]=old["status"]
        rec["reviewed_offline_without_fetch"]=True
        rec["first_batch_record_unchanged"]=True
        updated.append(rec)
    result={
        "kind":"OFFLINE_RECHECK_OF_PINNED_ISSUER_PDF_BYTES",
        "original_source":"Original 19-symbol issuer batch PDF audit; no new PDFs",
        "n_document_bytes_reverified":len(updated),
        "n_standalone_dividend_implementation_titles":sum(
            not x["excluded_from_corporate_action_ledger"] for x in updated
        ),
        "n_derivative_effect_notices_excluded_from_dividend_ledger":sum(
            x["excluded_from_corporate_action_ledger"] for x in updated
        ),
        "n_document_date_cash_vendor_crossmatches":sum(
            x["status"]=="PDF_CASH_MATCHED_TO_THIRDPARTY" for x in updated
        ),
        "n_document_issuer_amount_only":sum(
            x["status"]=="OFFICIAL_PDF_NUMBER_ONLY_NOT_RECONCILED"
            and x["cash_per_share_verified"] is not None for x in updated
        ),
        "n_document_multi_amount_unresolved":sum(
            x["status"]=="PDF_MULTI_AMOUNT_NEEDS_MANUAL_REVIEW" for x in updated
        ),
        "n_document_number_unextractable":sum(
            x["status"]=="PDF_NUMBER_UNEXTRACTABLE" for x in updated
        ),
        "n_document_without_vendor_date_crossmatch":sum(
            x["thirdparty_same_day_events"]==0 for x in updated
        ),
        "amounts_are_not_broker_cash_posting":True,
        "does_not_prove_vendor_historical_factor_vintage":True,
        "documents":updated,
        "inherited_index_query_failures":original["failures"],
    }
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-batch",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    obj=json.loads(a.original_batch.read_text(encoding="utf-8"))
    result=rerate(obj,a.original_batch.parent)
    if a.out.exists():
        raise FileExistsError(a.out)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
        k:v for k,v in result.items() if k.startswith("n_document_")
    },indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
