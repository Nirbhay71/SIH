"""Family provision of the India-Nepal document rules. Every condition of the
provision must be met, and an unmet one must be named in the reason."""
from app.acceptance_policy import evaluate_family_provision


def _ok(**overrides):
    args = dict(
        member_doc_type="aadhaar", relationship="child", relationship_proof_presented=True,
        anchor_name="Ramesh Kumar", anchor_doc_type="indian_passport",
    )
    args.update(overrides)
    return evaluate_family_provision(**args)


def test_lesser_proof_plus_relationship_proof_under_an_approved_adult_is_accepted():
    r = _ok()
    assert r["accepted"] is True
    assert "Ramesh Kumar" in r["reason"] and "child" in r["reason"]


def test_missing_relationship_proof_is_not_accepted_and_says_why():
    r = _ok(relationship_proof_presented=False)
    assert r["accepted"] is False
    assert "proof of the family relationship" in r["reason"]


def test_anchor_without_an_approved_document_does_not_cover_anyone():
    """An adult carrying only an Aadhaar has no approved document to lend."""
    r = _ok(anchor_doc_type="aadhaar")
    assert r["accepted"] is False
    assert "approved document" in r["reason"]


def test_undeclared_relationship_is_not_accepted():
    assert _ok(relationship=None)["accepted"] is False
    assert _ok(relationship="friend")["accepted"] is False


def test_unrecognised_member_document_is_not_accepted():
    r = _ok(member_doc_type="library_card")
    assert r["accepted"] is False
    assert "library_card" in r["reason"]


def test_all_unmet_conditions_are_listed_together():
    r = _ok(anchor_doc_type=None, relationship=None, relationship_proof_presented=False, member_doc_type="x")
    assert r["accepted"] is False
    for phrase in ("approved document", "recognised identity document", "relationship was declared", "proof of the family"):
        assert phrase in r["reason"]
