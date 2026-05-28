import streamlit as st
import pandas as pd
from datetime import date, timedelta
from apify_client import ApifyClient

SHEET_URL = "https://docs.google.com/spreadsheets/d/1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA/export?format=csv"


# ─────────────────────────────
# DATA
# ─────────────────────────────

@st.cache_data(ttl=600)
def load():
    return pd.read_csv(SHEET_URL)


def token():
    return st.secrets.get("APIFY_TOKEN") or st.text_input("APIFY token", type="password")


# ─────────────────────────────
# ROOM FILTER (BB / HB / RENTAL)
# ─────────────────────────────

def room_type(text: str):
    t = (text or "").lower()

    if "half board" in t:
        return "Half Board"
    if "bed" in t:
        return "Bed & Breakfast"
    if "apartment" in t or "kitchen" in t:
        return "Rental"

    return None


# ─────────────────────────────
# APIFY
# ─────────────────────────────

def fetch(client, name, location, checkin, checkout, adults):

    run = client.actor("automation-lab/booking-scraper").call({
        "locationQuery": location,
        "checkin": checkin,
        "checkout": checkout,
        "adults": adults,
        "rooms": 1,
        "currency": "EUR",
        "maxResults": 30
    })

    dataset = client.dataset(getattr(run, "defaultDatasetId"))
    items = list(dataset.iterate_items())

    out = []

    for i in items:

        rt = room_type((i.get("name","") + i.get("description","")))

        if not rt:
            continue

        price = i.get("price") or 0
        try:
            price = float(price)
        except:
            continue

        if price <= 0:
            continue

        out.append({
            "hotel": name,
            "location": location,
            "room_type": rt,
            "price": price
        })

    return out


# ─────────────────────────────
# UI
# ─────────────────────────────

st.title("🏨 Self Hotel Competitor Tracker")

df = load()

checkin = st.date_input("Check-in", date.today() + timedelta(days=14))
checkout = st.date_input("Check-out", checkin + timedelta(days=7))

adults = st.selectbox("Adults", [2,3,4,5,6], 0)

# ─────────────────────────────
# SELF HOTEL SELECT
# ─────────────────────────────

self_hotels = df[df["type"] == "self"]["hotel"].unique().tolist()

selected_self = st.selectbox("Select Self Hotel", self_hotels)

if st.button("Fetch"):

    client = ApifyClient(token())

    # ─────────────────────────────
    # GET SELECTED GROUP
    # ─────────────────────────────

    self_row = df[df["hotel"] == selected_self].iloc[0]

    location = self_row["location"]

    # self + competitors in SAME location group
    group = df[df["location"] == location]

    group = group[group["hotel"].notna()]

    results = []

    # ─────────────────────────────
    # FETCH ONLY GROUP
    # ─────────────────────────────

    for _, r in group.iterrows():

        data = fetch(
            client,
            r["hotel"],
            r["location"],
            checkin.strftime("%Y-%m-%d"),
            checkout.strftime("%Y-%m-%d"),
            adults
        )

        results.extend(data)

    df_out = pd.DataFrame(results)

    if df_out.empty:
        st.warning("No data")
        st.stop()

    # SORT HIGH → LOW
    df_out = df_out.sort_values("price", ascending=False)

    # ─────────────────────────────
    # OUTPUT
    # ─────────────────────────────

    st.subheader(f"Comparison for {selected_self}")

    for _, r in df_out.iterrows():

        st.markdown(f"""
### {r['hotel']}

🏷️ {r['room_type']}  
📍 {r['location']}  

## €{r['price']:,.0f}
""")

        st.divider()

    st.dataframe(df_out)

