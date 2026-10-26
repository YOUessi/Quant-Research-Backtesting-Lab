"""EXP-005 CLI: construct audit-only PIT cash event ledger from PDF evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pit_action_book import load_reports


def main():
    parser=argparse.ArgumentParser()
    for name in ("batch19","batch30","recovered","pdf19","pdf30",
                 "exchange-calendar","primary","primary-pdf-dir","out"):
        parser.add_argument("--"+name,type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Ledger already exists; do not overwrite")
    result=load_reports(
        args.batch19,args.batch30,args.recovered,
        args.pdf19,args.pdf30,args.exchange_calendar,
        primary=args.primary,primary_pdf_dir=args.primary_pdf_dir,
    )
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",
                        encoding="utf-8")
    print(json.dumps({
        "source_events":result["candidate_source_events"],
        "unique_accepted":result["unique_cash_events"],
        "conflicting_identities_held":result["contradictory_identities_held"],
        "duplicate_groups_booked_once":result["duplicate_groups_booked_once"],
        "full_rights_or_trading_certified":False,
    },indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
