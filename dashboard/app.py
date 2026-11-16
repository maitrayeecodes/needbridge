import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import streamlit as st

from backend.matching import allocate, load_data, score_matches

CHERRY, LILAC = "#E2375C", "#D9CCFF"

st.set_page_config(page_title="NeedBridge Dashboard", page_icon="🎒", layout="wide")


@st.cache_data
def run_engine(min_score):
    donations, requests = load_data()
    matches = score_matches(donations, requests)
    plan, still = allocate(matches, donations, requests, min_score)
    return donations, requests, plan, still


st.title("NeedBridge · NGO control room")
st.caption("Sample data only. Verified requests are matched with donations, best score first.")

min_score = st.sidebar.slider("Minimum match score", 0, 100, 50)
donations, requests, plan, still = run_engine(min_score)

if plan.empty:
    st.warning("No matches at this score. Try lowering the minimum.")
    st.stop()

total_needed = int(requests["quantity_needed"].sum())
matched = int(plan["items"].sum())
remaining = int(sum(still.values()))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Verified requests", len(requests))
c2.metric("Items matched", matched)
c3.metric("Items still needed", remaining)
c4.metric("Needs fulfilled", f"{matched / total_needed:.0%}")

tab1, tab2, tab3 = st.tabs(["Handover plan", "Needs vs delivered", "Unmatched donations"])

with tab1:
    st.dataframe(plan, hide_index=True)

with tab2:
    chart = requests.set_index("request_id")[["organization", "quantity_needed"]].copy()
    chart["delivered"] = plan.groupby("request")["items"].sum().reindex(chart.index).fillna(0)

    fig, ax = plt.subplots(figsize=(8, 4))
    x = range(len(chart))
    ax.bar(x, chart["quantity_needed"], color=LILAC, label="Needed")
    ax.bar(x, chart["delivered"], color=CHERRY, label="Delivered")
    ax.set_xticks(list(x))
    ax.set_xticklabels(chart.index)
    ax.set_ylabel("Items")
    ax.legend()
    ax.spines[["top", "right"]].set_visible(False)
    st.pyplot(fig)

with tab3:
    left = donations.set_index("donation_id")[["item", "quantity", "area"]].copy()
    given = plan.groupby("donation")["items"].sum().reindex(left.index).fillna(0)
    left["left_over"] = (left["quantity"] - given).astype(int)
    st.dataframe(left[left["left_over"] > 0])