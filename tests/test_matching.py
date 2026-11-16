import pandas as pd
from backend.matching import load_data, score_matches, allocate


def donation(**changes):
    row = dict(donation_id="D1", donor="Test", category="notebooks",
               item="Notebooks", quantity=15, condition="new",
               age_min=6, age_max=12, area="Cidco")
    row.update(changes)
    return pd.DataFrame([row])


def request(**changes):
    row = dict(request_id="R1", organization="Test School", category="notebooks",
               item="Notebooks", quantity_needed=20, age_min=6, age_max=12,
               area="Cidco", verified="yes")
    row.update(changes)
    return pd.DataFrame([row])


def test_partial_fulfilment_leaves_remaining_need():
    d, r = donation(), request()
    plan, need = allocate(score_matches(d, r), d, r)
    assert plan["items"].sum() == 15
    assert need["R1"] == 5


def test_different_category_never_matches():
    d, r = donation(), request(category="school_bag")
    assert len(score_matches(d, r)) == 0


def test_weak_match_is_skipped():
    d = donation(condition="fair", quantity=1, area="Garkheda", age_min=6, age_max=8)
    r = request(age_min=10, age_max=12)
    plan, need = allocate(score_matches(d, r), d, r)
    assert len(plan) == 0


def test_unverified_requests_are_excluded():
    _, requests = load_data()
    assert "R07" not in requests["request_id"].values


def test_scores_stay_between_0_and_100():
    donations, requests = load_data()
    matches = score_matches(donations, requests)
    assert matches["score"].between(0, 100).all()


def test_no_donation_or_request_is_over_allocated():
    donations, requests = load_data()
    plan, _ = allocate(score_matches(donations, requests), donations, requests)
    given = plan.groupby("donation")["items"].sum()
    received = plan.groupby("request")["items"].sum()
    for did, qty in given.items():
        assert qty <= donations.set_index("donation_id").loc[did, "quantity"]
    for rid, qty in received.items():
        assert qty <= requests.set_index("request_id").loc[rid, "quantity_needed"]