import streamlit as st
import pandas as pd
from datetime import date, timedelta
import time
import os
from apify_client import ApifyClient

# ─────────────────────────────
# PAGE CONFIG
# ─────────────────────────────
st.set_page_config(
    page_title="Hotel Cluster Monitor",
    page_icon="🏨",
    layout="wide",
)

# ─────────────────────────────
# GOOGLE SHEET CONFIG
# ─────────────────────────────
SHEETS = {
    "Hotel Convent": "https://docs.google.com/spreadsheets/d/1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA/export?format=csv&gid=0",
    "Vile brez balkona": "https://docs.google.com/spreadsheets/d/1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA/export?format=csv&gid=1313360174",
}

# ─────────────────────────────
# HELPERS
# ─────────────────────────────
def get_token():
    return st.secrets.get("APIFY_TOKEN") or os.getenv("APIFY_TOKEN")


def load_sheet(cluster_name: str):
    url = SHEETS[cluster_name]
    df = pd.read_csv(url)

    # expected columns:
    # name | type | url | number

    df.columns = [c.strip().lower() for c in df.columns]

    return df


def apify_fetch(url: str, checkin, checkout, adults):
    client = ApifyClient(get_token())

    run_input = {
        "startUrls": [{"url": url}],
        "checkin": checkin.strftime("%Y-%m-%d"),
        "checkout": checkout.strftime("%Y-%m-%d"),
        "adults": adults,
        "rooms": 1,
        "currency": "EUR",
        "language": "en-us",
        "maxResults": 20,
    }

    run = client.actor("pAk2GX3uArJTHBc9g").call(run_input=run_input)

    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        return []

    items = list(client.dataset(dataset_id).iterate_items())

    results = []

    for h in items:
        price = h.get("price") or 0
        try:
            price = float(price)
        except:
            price = 0

        results.append({
            "name": h.get("name"),
            "price": price,
            "rating": h.get("reviewScore", 0),
            "url": h.get("url"),
        })

    return results


# ─────────────────────────────
# UI
# ─────────────────────────────
st.title("🏨 Hotel Cluster Pricing Monitor")

cluster = st.selectbox("Select cluster", list(SHEETS.keys()))

today = date.today()

checkin = st.date_input("Check-in", today + timedelta(days=14))
checkout = st.date_input("Check-out", today + timedelta(days=21))
adults = st.selectbox("Adults", [2, 3, 4, 5, 6], index=0)

fetch = st.button("Fetch prices")

# ─────────────────────────────
# MAIN
# ─────────────────────────────
if fetch:

    sheet = load_sheet(cluster)

    if sheet.empty:
        st.error("Google Sheet is empty")
        st.stop()

    self_hotels = sheet[sheet["type"].str.lower() == "self"]

    all_data = []

    progress = st.progress(0)

    for i, row in sheet.iterrows():

        url = row.get("url")
        name = row.get("name")

        if pd.isna(url):
            continue

        try:
            data = apify_fetch(url, checkin, checkout, adults)
        except Exception as e:
            st.warning(f"Apify error for {name}: {e}")
            continue

        for d in data:
            d["hotel"] = name
            d["type"] = row.get("type", "")
            all_data.append(d)

        progress.progress((i + 1) / len(sheet))

    progress.empty()

    df = pd.DataFrame(all_data)

    if df.empty:
        st.error("No data from Apify")
        st.stop()

    # CLEAN
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)

    df = df.sort_values("price", ascending=False)

    # SELF HOTEL REFERENCE
    self_names = self_hotels["name"].tolist()
    self_price = df[df["hotel"].isin(self_names)]["price"].mean()

    st.subheader(f"Cluster: {cluster}")

    st.metric("Self avg price", f"€{self_price:,.0f}")

    st.divider()

    # ─────────────────────────────
    # DISPLAY
    # ─────────────────────────────
    for _, r in df.iterrows():

        is_self = r.get("type", "").lower() == "self"

        color = "#1a73e8" if is_self else "#111"

        diff = ""
        if self_price and self_price > 0:
            diff_pct = ((r["price"] - self_price) / self_price) * 100
            diff = f" ({diff_pct:+.0f}%)"

        st.markdown(f"""
<div style="padding:10px;border-bottom:1px solid #eee;">

    <div style="font-size:18px;font-weight:600;color:{color}">
        {r['hotel']}
    </div>

    <div style="color:#666;font-size:13px;">
        ⭐ {r.get('rating',0)} {diff}
    </div>

    <div style="font-size:22px;font-weight:700;">
        €{r['price']:,.0f}
    </div>

    <a href="{r.get('url','')}" target="_blank">Open</a>

</div>
""", unsafe_allow_html=True)
