"""Only unpaired issuer-effective halts trigger bounded original PDF recovery."""

import pytest

from quant_lab.pit_resume_recovery import recovery_targets, collect


def original_pairing():
    return {
        "kind": "EXP007_PAIRED_INDEPENDENT_ORIGINAL_ISSUER_HALT_RESUME_PROOFS",
        "unresolved_not_booked_as_halts": [
            {"symbol": "SH600009", "start": "2022-04-08",
             "reason": "NO_SEPARATELY_EXPLICIT_RESUME_DATE"},
            {"symbol": "SZ000425", "start": "2021-04-07",
             "reason": "NO_SEPARATELY_EXPLICIT_RESUME_DATE"},
            {"symbol": "SZ000425", "start": "2022-05-27",
             "reason": "NO_SEPARATELY_EXPLICIT_RESUME_DATE"},
            {"symbol": "SZ000425", "start": "2021-04-07",
             "reason": "NO_SEPARATELY_EXPLICIT_RESUME_DATE"},
            {"symbol": "SH600009", "start": "2021-05-01",
             "reason": "POSITIVE_QUOTE_ON_EXPECTED_HALT"},
        ],
    }


def test_resume_search_scope_is_only_unpaired_starts_and_unique():
    assert recovery_targets(original_pairing()) == {
        "SH600009": ["2022-04-08"],
        "SZ000425": ["2021-04-07", "2022-05-27"],
    }


def test_wrong_halt_source_kind_rejected():
    with pytest.raises(ValueError, match="pairing audit"):
        recovery_targets({"kind": "UNTRUSTED", "unresolved_not_booked_as_halts": []})


def test_empty_new_target_cannot_overwrite_existing_audit(tmp_path):
    out=tmp_path/"immutable"
    out.mkdir()
    with pytest.raises(FileExistsError, match="existing PDF audit output"):
        collect(original_pairing(), {"kind": "EXP005_PRIMARY_ISSUER_HALT_ANNOUNCEMENT_EXPLORATION", "results":[]}, tmp_path, output=out)
