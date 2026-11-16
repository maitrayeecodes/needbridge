import os
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", None)

# Data folder: next to this project, whatever folder you run from (tests can override it)
DATA_DIR = Path(os.environ.get("NEEDBRIDGE_DATA", Path(__file__).resolve().parent.parent / "data"))

CONDITION_POINTS = {"new": 10, "good": 8, "fair": 4}


def load_data():
    donations = pd.read_csv(DATA_DIR / "donations.csv")
    requests = pd.read_csv(DATA_DIR / "requests.csv")
    requests = requests[requests["verified"] == "yes"]
    return donations, requests


def score_matches(donations, requests, detail=False):
    # Pair every donation with every request
    pairs = donations.merge(requests, how="cross", suffixes=("_d", "_r"))

    same_category = pairs["category_d"] == pairs["category_r"]
    category_pts = np.where(same_category, 40, 0)

    overlap = (
        np.minimum(pairs["age_max_d"], pairs["age_max_r"])
        - np.maximum(pairs["age_min_d"], pairs["age_min_r"])
        + 1
    )
    request_span = pairs["age_max_r"] - pairs["age_min_r"] + 1
    age_pts = 20 * np.clip(overlap, 0, None) / request_span

    area_pts = np.where(pairs["area_d"] == pairs["area_r"], 20, 0)
    condition_pts = pairs["condition"].map(CONDITION_POINTS)
    quantity_pts = 10 * np.minimum(pairs["quantity"] / pairs["quantity_needed"], 1)

    pairs["score"] = category_pts + age_pts + area_pts + condition_pts + quantity_pts
    pairs["age_pts"], pairs["area_pts"] = age_pts, area_pts
    pairs["condition_pts"], pairs["quantity_pts"] = condition_pts, quantity_pts
    pairs = pairs[same_category].copy()
    pairs["score"] = pairs["score"].round(1)

    columns = ["donation_id", "item_d", "quantity", "request_id",
               "organization", "quantity_needed", "area_d", "area_r", "score"]
    if detail:  # extra columns used to explain WHY a match was made
        columns += ["item_r", "category_d", "condition", "age_min_d", "age_max_d", "age_min_r", "age_max_r",
                    "age_pts", "area_pts", "condition_pts", "quantity_pts"]
    return pairs[columns].sort_values("score", ascending=False)



def allocate(matches, donations, requests, min_score=50):
    supply = donations.set_index("donation_id")["quantity"].to_dict()
    need = requests.set_index("request_id")["quantity_needed"].to_dict()
    plan = []

    for m in matches.itertuples():
        if m.score < min_score:
            continue
        give = min(supply[m.donation_id], need[m.request_id])
        if give <= 0:
            continue
        supply[m.donation_id] -= give
        need[m.request_id] -= give
        plan.append({
            "donation": m.donation_id,
            "request": m.request_id,
            "organization": m.organization,
            "items": give,
            "score": m.score,
        })

    return pd.DataFrame(plan), need


if __name__ == "__main__":
    donations, requests = load_data()
    matches = score_matches(donations, requests)
    plan, still_needed = allocate(matches, donations, requests)

    print("HANDOVER PLAN")
    print(plan.to_string(index=False))
    print()
    print("STILL NEEDED")
    info = requests.set_index("request_id")
    for rid, qty in still_needed.items():
        if qty > 0:
            print(rid, info.loc[rid, "organization"], "-", info.loc[rid, "item"], ":", qty, "still needed")