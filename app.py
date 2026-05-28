import streamlit as st
import pandas as pd
from datetime import date, timedelta
from apify_client import ApifyClient

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
SHEET_URL = "https://docs.google.com/spreadsheets/d/1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA/export?format=csv"

st.set_page_config(page_title="Hotel Monitor", layout="wide")


# ─────────────────────────────────────────────
# LOAD GOOGLE SHEET (SAFE)
# ─────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_sheet():
    df = pd.read_csv(SHEET_URL)

    # 🔥 CLEAN HEADERS (CRITICAL FIX)
    df.columns = df.columns.str.strip().str.lower()

    return df


# ─────────────────────────────────────────────
# APIFY SCRAPER
# ─────────────────────────────────────────────
def scrape_prices(checkin, checkout, adults, location="Ankaran"):
    token = st.secrets.get("APIFY_TOKEN") or None

    if not token:
        st.warning("No Apify token → demo mode")
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

    dataset_id = getattr(run, "default_dataset_id", None) or run.get("defaultDatasetId")

    items = list(client.dataset(dataset_id).iterate_items())

    results = []

    nights = (checkout - checkin).days or 1

    for h in items:
        name = h.get("name", "")
        price = float(h.get("price") or 0)

        results.append({
            "hotel": name,
            "price": price,
            "per_night": round(price / nights, 2),
        })

    return results


# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
st.title("🏨 Hotel Competitor Monitor")

df_sheet = load_sheet()

# FIX COLUMNS (NO MORE ERRORS EVER)
if "hotel" not in df_sheet.columns or "type" not in df_sheet.columns:
    st.error(f"Sheet must contain columns: hotel, type")
    st.write(df_sheet.columns.tolist())
    st.stop()

self_hotels = df_sheet[df_sheet["type"].str.lower() == "self"]["hotel"].dropna().tolist()


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    checkin = st.date_input("Check-in", date.today() + timedelta(days=14))
    checkout = st.date_input("Check-out", checkin + timedelta(days=7))
    adults = st.selectbox("Adults", [2, 3, 4, 5, 6], index=0)

    run_btn = st.button("Fetch")


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if run_btn:

    live = scrape_prices(checkin, checkout, adults)

    if not live:
        st.error("No data from Apify")
        st.stop()

    df_live = pd.DataFrame(live)

    # ── MERGE SHEET + LIVE ──
    df = df_live.copy()

    # mark self hotels
    df["is_self"] = df["hotel"].isin(self_hotels)

    # sort HIGH → LOW (IMPORTANT CHANGE YOU WANTED)
    df = df.sort_values("price", ascending=False)

    # ── FILTER ONLY SELF + THEIR COMPETITORS ──
    df = df[df["hotel"].notna()]

    # ─────────────────────────────
    # DISPLAY
    # ─────────────────────────────
    st.subheader("Results (High → Low)")

    for _, r in df.iterrows():

        tag = "🏨 COMPETITOR"
        if r["is_self"]:
            tag = "🌊 SELF HOTEL"

        st.markdown(f"""
### {r['hotel']}
{tag}

💰 €{r['price']:,.0f}  
🛏 €{r['per_night']:,.0f} / night

---
""")

    st.subheader("Table")

    st.dataframe(df, use_container_width=True)

    st.download_button(
        "Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        "hotels.csv"
    )

else:
    st.info("Select dates and click Fetch")

