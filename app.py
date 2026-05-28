import streamlit as st
import pandas as pd
from datetime import date, timedelta
from apify_client import ApifyClient

SHEET_URL = "https://docs.google.com/spreadsheets/d/1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA/export?format=csv"

st.set_page_config(page_title="Hotel Pricing Intelligence", layout="wide")


# ─────────────────────────────
# LOAD SHEET
# ─────────────────────────────
@st.cache_data(ttl=600)
def load_sheet():
    df = pd.read_csv(SHEET_URL)
    df.columns = df.columns.str.strip().str.lower()
    return df


# ─────────────────────────────
# APIFY
# ─────────────────────────────
def fetch(checkin, checkout, adults, location):
    token = st.secrets.get("APIFY_TOKEN")
    if not token:
        return []

    client = ApifyClient(token)

    run = client.actor("automation-lab/booking-scraper").call({
        "locationQuery": location,
        "checkin": checkin.strftime("%Y-%m-%d"),
        "checkout": checkout.strftime("%Y-%m-%d"),
        "adults": adults,
        "rooms": 1,
        "currency": "EUR",
        "language": "en-us",
        "maxResults": 30
    })

    dataset_id = run.get("defaultDatasetId") or getattr(run, "default_dataset_id", None)

    items = list(client.dataset(dataset_id).iterate_items())

    nights = (checkout - checkin).days or 1

    out = []

    for h in items:
        name = (h.get("name") or "").lower()
        price = float(h.get("price") or 0)

        if price <= 0:
            continue

        # ── BOARD TYPE DETECTION ──
        board = "rental"

        if "half" in name or "hb" in name:
            board = "halfboard"
        elif "breakfast" in name or "bb" in name:
            board = "bb"

        out.append({
            "hotel": h.get("name"),
            "adults": adults,
            "price": price,
            "per_night": round(price / nights, 2),
            "board": board
        })

    return out


# ─────────────────────────────
# UI
# ─────────────────────────────
st.title("🏨 Pricing Intelligence Engine")

df_sheet = load_sheet()

df_sheet["hotel"] = df_sheet["hotel"].astype(str).str.strip()
df_sheet["type"] = df_sheet["type"].astype(str).str.strip().str.lower()

self_list = df_sheet[df_sheet["type"] == "self"]["hotel"].unique().tolist()
competitors = df_sheet[df_sheet["type"] != "self"]["hotel"].unique().tolist()


# ── SELF HOTELS (MULTI)
self_hotels = st.multiselect(
    "Self hotels",
    self_list,
    default=self_list
)


# ── DATE
checkin = st.date_input("Check-in", date.today() + timedelta(days=14))
checkout = st.date_input("Check-out", checkin + timedelta(days=7))


run = st.button("Fetch Prices")


# ─────────────────────────────
# RUN
# ─────────────────────────────
if run:

    results = []

    targets = self_hotels + competitors

    for hotel in targets:

        data = fetch(checkin, checkout, 2, hotel)

        if not data:
            continue

        df = pd.DataFrame(data)

        df["is_self"] = df["hotel"].isin(self_hotels)

        results.append(df)

    if not results:
        st.error("No data")
        st.stop()

    df = pd.concat(results)

    # ─────────────────────────────
    # SELF BASELINE (INDEX)
    # ─────────────────────────────
    self_avg = df[df["is_self"]]["price"].mean()

    df["price_index"] = (df["price"] / self_avg * 100).round(1)

    df["vs_self"] = (df["price"] - self_avg).round(0)

    # ─────────────────────────────
    # SORT
    # ─────────────────────────────
    df = df.sort_values(["is_self", "price"], ascending=[False, False])

    # ─────────────────────────────
    # OUTPUT
    # ─────────────────────────────
    st.subheader("Pricing Index (SELF = 100%)")

    st.metric("Self avg price", f"€{self_avg:.0f}")

    st.divider()

    for hotel in df["hotel"].unique():

        sub = df[df["hotel"] == hotel]

        st.markdown(f"## 🏨 {hotel}")

        for _, r in sub.iterrows():

            tag = "SELF" if r["is_self"] else "COMPETITOR"

            st.write(f"""
**{tag}**

💰 €{r['price']:,.0f}  
🛏 €{r['per_night']:,.0f} / night  
🍽 {r['board'].upper()}  
📊 Index: {r['price_index']} (100 = self)  
📈 vs Self: {r['vs_self']:+.0f} €
---
""")

else:
    st.info("Select dates + self hotels")

