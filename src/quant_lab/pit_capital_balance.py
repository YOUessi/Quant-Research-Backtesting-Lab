"""EXP-007 issuer-original pre/post capital arithmetic for unresolved share rights.

Historical issuer implementation PDFs sometimes specify before + after total
nominal shares, a positive bonus/transfer ratio and the issued-share count.
A *same-document* exact capital reconciliation can derive zero for an otherwise
unknown complementary rights class. We only accept reconciliations satisfying:
  1) exactly one strongly formatted pre/post implementation capital pair;
  2) a known positive issuer bonus or capital transfer ratio;
  3) source-described issued share quantity (unless explicit issuer directly
     says zero, in which case this module is not needed);
  4) no "differential distribution" flag and no material unexplained balance.
The inference is stronger than a missing third-party field, but it remains a
source-accounting balance, not an independently credited brokerage share.

Do NOT infer zero-share rights from the absence of wording or from a later
total capital statement in a press article. Do NOT use Qlib factor as proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader

from .pit_share_distribution import clean


NUMBER = r"([0-9][0-9,]*)"
SSE_BEFORE_AFTER = re.compile(
    r"本次利润分配(?:及转增股本)?以方案实施前的公司总股本"
    + NUMBER
    + r"股为基数.{0,800}?本次分配后总股本为"
    + NUMBER
    + r"股"
)
SSE_GENERAL = re.compile(
    r"本次分配以方案实施前的公司总股本"
    + NUMBER
    + r"股为基数.{0,800}?本次分配后总股本为"
    + NUMBER
    + r"股"
)
SZ_BEFORE_AFTER = re.compile(
    r"分红前本公司总股本为"
    + NUMBER
    + r"股.{0,150}?分红后总股本增至"
    + NUMBER
    + r"股"
)
ISSUER_BONUS_ISSUED = re.compile(r"派送红股" + NUMBER + r"股")
ISSUER_TRANSFER_ISSUED = re.compile(r"(?:共计转增|合计转增|，转增)" + NUMBER + r"股")


def _int(candidate: str) -> int:
    out=int(candidate.replace(",",""))
    if not (100_000 <= out < 10**14):
        raise ValueError("Implausible listed-issuer total share count")
    return out


def audit_balanced_issuer_rights(
    text: str,
    rights: dict,
    *,
    issuer_sha256: str,
    is_differential_distribution: bool | None = None,
) -> dict:
    """Return unambiguous source capital balance and optional inferred zero.

    Inferred zero is one complementary category only, never an unreported
    bonus+transfer pair and never a complete broker rights settlement.
    """
    t=clean(text)
    pairs=set()
    for rex in (SSE_BEFORE_AFTER,SSE_GENERAL,SZ_BEFORE_AFTER):
        for m in rex.finditer(t):
            pairs.add((_int(m.group(1)),_int(m.group(2))))
    if len(issuer_sha256)!=64:
        raise ValueError("Original issuer PDF SHA is required")
    result={
        "original_pdf_sha256":issuer_sha256,
        "issuer_current_implementation_pre_post_share_pairs":[
            {"pre_issued_nominal_share_count":a,"post_issued_nominal_share_count":b}
            for a,b in sorted(pairs)
        ],
        "source_distribution_differential":is_differential_distribution,
        "balanced_accounting_inferred_zero_category":None,
        "status":"NO_SINGLE_ELIGIBLE_ISSUER_CAPITAL_BALANCE",
        "source_issued_shares_are_global_not_broker_credit":True,
        "historical_broker_share_credit_verified":False,
        "issuer_rights_historical_factor_vintage_verified":False,
    }
    if len(pairs)!=1 or is_differential_distribution is not False:
        # Differential distributions, floating market share counts, and
        # unknown eligibility dates block inferred zero.
        if is_differential_distribution is not False and pairs:
            result["status"]="DIFFERENTIAL_OR_UNDECLARED_ELIGIBILITY_HOLD"
        return result
    before,after=next(iter(pairs))
    issued=after-before
    if issued < 0:
        result["status"]="DECREASED_CAPITAL_NOT_SIMPLE_DISTRIBUTION"
        return result
    result.update({
        "pre_nominal_company_shares":before,
        "post_nominal_company_shares":after,
        "issuer_total_issued_delta":issued,
    })
    b=rights["bonus_ratio_per_nominal_share"]
    c=rights["transfer_ratio_per_nominal_share"]
    if (b is None and c is None) or (b is not None and c is not None):
        result["status"]="COMPLEMENT_NOT_UNIQUE_OR_RIGHTS_ALREADY_COMPLETE"
        return result
    positive=b if b is not None else c
    if positive <= 0:
        result["status"]="NO_POSITIVE_SOURCE_RIGHT_TO_BALANCE"
        return result
    expected=before*positive
    if abs(issued-expected)>1.01:
        result["status"]="CAPITAL_BALANCE_DIFFERENCE_EXCEEDS_ONE_SHARE"
        result["expected_share_delta_from_known_right"]=round(expected,6)
        return result

    # Confirm that the issuer's described new share quantity agrees as well,
    # not merely that the parsed pre/post company totals happen to match.
    quantity_candidates=(
        ISSUER_BONUS_ISSUED.findall(t) if b is not None
        else ISSUER_TRANSFER_ISSUED.findall(t)
    )
    quantities=sorted(set(_int(x) for x in quantity_candidates))
    if len(quantities)!=1 or abs(quantities[0]-issued)>1:
        result["status"]="TOTAL_BALANCE_MATCHES_BUT_ISSUED_SHARES_UNCONFIRMED"
        result["source_issued_share_quantity_candidates"]=quantities
        return result
    result.update({
        "issuer_explicit_new_share_quantity":quantities[0],
        "calculated_known_right_issued_shares":round(expected,6),
        "capital_balance_gap_shares":issued-expected,
        "balanced_accounting_inferred_zero_category":(
            "transfer" if b is not None else "bonus"
        ),
        "status":"ISSUER_IN_SAME_PDF_PRE_POST_AND_ISSUED_SHARE_BALANCE_SUPPORT_ZERO_COMPLEMENT",
        "source_evidence_grade":"DERIVED_ZERO_BY_ISSUER_CAPITAL_CONSERVATION_NOT_EXPLICIT_NO_CLAUSE",
    })
    return result


def audit_originals(ledger: dict, shares: dict, pdf_dirs: list[Path]) -> dict:
    bysha={}
    for root in pdf_dirs:
        for file in root.glob("*.pdf"):
            bysha[hashlib.sha256(file.read_bytes()).hexdigest()]=file
    if len(ledger.get("events",[]))!=len(shares.get("audit",[])):
        raise ValueError("Cash/stock-right event scopes differ")
    rightsby={x["event_id"]:x for x in shares["audit"]}
    review=[]
    for event in ledger["events"]:
        right=rightsby[event["event_id"]]
        if right["issuer_pdf_sha256"]!=event["issuer_pdf_sha256"]:
            raise ValueError("Cash/stock original PDF identity mismatch")
        f=bysha.get(event["issuer_pdf_sha256"])
        if f is None:raise ValueError("Missing original issuer PDF")
        content="\n".join(p.extract_text() or "" for p in PdfReader(f).pages[:5])
        n=clean(content)
        # The SSE standardized disclosure header explicitly indicates
        # whether differential distribution is present.
        flag=re.findall(r"差异化分红送转[：:]([是否])",n)
        differential={"是":True,"否":False}.get(flag[-1]) if len(set(flag))==1 else None
        item=audit_balanced_issuer_rights(
            content,right,issuer_sha256=event["issuer_pdf_sha256"],
            is_differential_distribution=differential,
        )
        item.update({
            "symbol":event["symbol"],"event_id":event["event_id"],
            "ex_date":event["ex_date"],"issuer_pdf_url":event["issuer_pdf_url"],
            "previous_rights_full":right["known_complete"],
            "previous_positive_rights":right["known_positive_stock_rights"],
        })
        review.append(item)
    proven=[x for x in review if x["balanced_accounting_inferred_zero_category"]]
    return {
        "kind":"EXP007_CORPORATE_CAPITAL_BALANCE_ADDITIONAL_NO_RIGHT_PROOF",
        "n_source_original_issuer_events":len(review),
        "previously_fully_known_rights":sum(x["previous_rights_full"] for x in review),
        "new_complete_share_rights_by_original_issuer_balance":len(proven),
        "full_rights_after_balanced_addition":sum(x["previous_rights_full"] for x in review)+len(proven),
        "new_positive_events_rights_completed":[
            {"symbol":x["symbol"],"ex_date":x["ex_date"],
             "new_zero_right_category":x["balanced_accounting_inferred_zero_category"],
             "issuer_pdf_sha256":x["original_pdf_sha256"],
             "pre":x["pre_nominal_company_shares"],"post":x["post_nominal_company_shares"],
             "stated_issued_shares":x["issuer_explicit_new_share_quantity"]}
            for x in proven
        ],
        "source_capital_balance_is_company_total_not_broker_share_credit":True,
        "corporate_action_revisions_and_asof_factor_history_still_missing":True,
        "audits":review,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cash-ledger",type=Path,required=True)
    p.add_argument("--share-audit",type=Path,required=True)
    p.add_argument("--issuer-dirs",type=Path,nargs="+",required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():raise FileExistsError(args.out)
    cash=json.loads(args.cash_ledger.read_text("utf8"))
    share=json.loads(args.share_audit.read_text("utf8"))
    result=audit_originals(cash,share,args.issuer_dirs)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
        k:v for k,v in result.items() if k in (
            "n_source_original_issuer_events",
            "previously_fully_known_rights",
            "new_complete_share_rights_by_original_issuer_balance",
            "full_rights_after_balanced_addition",
            "new_positive_events_rights_completed",
        )
    },ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
