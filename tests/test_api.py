import pandas as pd
from backend import api, matching
from backend.geo import canonical_area, distance_km


def test_area_names_ignore_case():
    assert canonical_area("CIDCO") == "Cidco" and canonical_area("nowhere") is None


def test_distance_is_sensible():
    assert 1 < distance_km("Cidco", "Garkheda") < 5 and distance_km("Cidco", "Cidco") == 0


def test_explanation_mentions_real_reasons():
    d = pd.DataFrame([dict(donation_id="D1", donor="T", category="notebooks", item="N", quantity=15, condition="new",
                           age_min=6, age_max=12, area="Cidco")])
    r = pd.DataFrame([dict(request_id="R1", organization="S", category="notebooks", item="N", quantity_needed=20,
                           age_min=6, age_max=12, area="Garkheda", verified="yes")])
    row = matching.score_matches(d, r, detail=True).iloc[0].to_dict()
    text = api.explain(row)
    assert "same category" in text and "Cidco to Garkheda" in text and "covers 15 of 20" in text


def test_bad_donation_is_rejected_with_clear_messages():
    _, errors = api.clean_donation({"donor": "A", "category": "toys", "item": "x", "quantity": 0,
                                    "condition": "ok", "age_min": 12, "age_max": 5, "area": "Mars"})
    assert len(errors) >= 6


def test_new_requests_are_never_verified():
    row, errors = api.clean_request({"organization": "New NGO", "category": "notebooks", "item": "Notebooks",
                                     "quantity_needed": 10, "age_min": 6, "age_max": 10, "area": "cidco"})
    assert not errors and row["verified"] == "no" and row["area"] == "Cidco"


def test_append_row_gives_next_id_even_without_final_newline(tmp_path):
    f = tmp_path / "donations.csv"
    f.write_text("donation_id,donor,category,item,quantity,condition,age_min,age_max,area\r\nD01,A,notebooks,N,1,new,6,9,Cidco")
    row, _ = api.clean_donation({"donor": "Bo", "category": "notebooks", "item": "Pens", "quantity": 2,
                                 "condition": "good", "age_min": 6, "age_max": 9, "area": "Cidco"})
    assert api.append_row(f, "donation_id", "D", row) == "D02"
    assert len(pd.read_csv(f)) == 2