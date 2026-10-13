"""Independent reference cases and security regressions for MELD scoring."""
import math

import pytest

from agents.base import AuditTrail
from meld_na import calculate_meld, calculate_meld_na, calculate_meld_3, full_assessment


@pytest.mark.parametrize(
    "bilirubin,inr,creatinine,sodium,albumin,male,female",
    [
        (1, 1, 1, 137, 3.5, 6, 7),
        (2.5, 1.8, 1.5, 135, 3.2, 22, 23),
        (2, 1.5, 1.2, 135, 3.5, 16, 18),
        (10, 3, 2.5, 128, 2, 39, 40),
        (2.5, 1, 1.2, 131, 3.8, 16, 17),
    ],
)
def test_adult_meld3_reference_examples(
    bilirubin, inr, creatinine, sodium, albumin, male, female
):
    # Independent values calculated from Kim et al. (2021) full 8-term formula.
    assert calculate_meld_3(bilirubin, inr, creatinine, sodium, albumin) == male
    assert calculate_meld_3(
        bilirubin, inr, creatinine, sodium, albumin, female=True
    ) == female


def test_legacy_reference_example():
    assert calculate_meld(2.5, 1.8, 1.5) == 20
    assert calculate_meld_na(2.5, 1.8, 1.5, 135) == 21


def test_meld3_albumin_and_creatinine_caps():
    base = calculate_meld_3(2.5, 1.8, 3, 135, 3.5)
    assert calculate_meld_3(2.5, 1.8, 9, 135, 9) == base
    assert calculate_meld_3(2.5, 1.8, 1, 135, 3.5, dialysis=True) == base
    assert calculate_meld_3(2.5, 1.8, 1, 135, 1.0) == calculate_meld_3(
        2.5, 1.8, 1, 135, 1.5
    )


def test_dialysis_caps_differ_between_versions():
    result = full_assessment(2.5, 1.8, 1, 135, albumin=3.2, dialysis=True)
    assert result["inputs"]["creatinine_mgdl"] == 4
    assert result["inputs"]["creatinine_mgdl_meld3"] == 3


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, 0, ""])
def test_reject_invalid_bilirubin(bad):
    with pytest.raises(ValueError):
        calculate_meld(bad, 1.5, 1.2)


def test_sodium_is_validated_even_below_meld_threshold():
    with pytest.raises(ValueError):
        calculate_meld_na(1, 1, 1, float("nan"))


def test_historical_mortality_not_applied_to_meld3():
    result = full_assessment(2.5, 1.8, 1.5, 135, 3.2)
    assert "Historical" in result["mortality_note"]
    assert result["meld_3"] == 22


def test_hmac_verifies_signature_and_does_not_export_mutable_state():
    audit = AuditTrail(secret_key="test-only-key")
    audit.log("runner", "test", "completed", {"status": "ok"})
    assert audit.verify_integrity()
    public_copy = audit.get_trail()
    public_copy[0]["current_hash"] = "0" * 64
    assert audit.verify_integrity()
    audit.logs[0]["current_hash"] = "0" * 64
    assert not audit.verify_integrity()


def test_hmac_rejects_tampered_event_without_changing_chain_links():
    audit = AuditTrail(secret_key="test-only-key")
    audit.log("runner", "test", "completed", {"status": "ok"})
    audit.logs[0]["event_type"] = "tampered"
    assert not audit.verify_integrity()
