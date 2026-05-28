import streamlit as st
import pandas as pd
from datetime import date, timedelta
from apify_client import ApifyClient

SHEET_URL = "https://docs.google.com/spreadsheets/d/1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA/export?format=csv"

st.set_page_config(page_title="Hotel Monitor", layout="wide")


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
def fetch_prices(checkin, checkout, adults, location):
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
        price = float(h.get("price") or 0)

        if price <= 0:
            continue

        out.append({
            "hotel": h.get("name"),
            "adults": adults,
            "price": price,
            "per_night": round(price / nights, 2)
        })

    return out


# ─────────────────────────────
# UI
# ─────────────────────────────
st.title("🏨 Competitor Intelligence")

df_sheet = load_sheet()

# CLEAN
df_sheet["hotel"] = df_sheet["hotel"].astype(str).str.strip()
df_sheet["type"] = df_sheet["type"].astype(str).str.strip().str.lower()

self_list = df_sheet[df_sheet["type"] == "self"]["hotel"].unique().tolist()
comp_list = df_sheet[df_sheet["type"] != "self"]["hotel"].unique().tolist()

# SELF SELECT
self_hotel = st.selectbox("Select SELF hotel", self_list)

# filter competitors based on sheet relationships
competitors = df_sheet[df_sheet["hotel"] == self_hotel]["competitors"] if "competitors" in df_sheet.columns else df_sheet

# fallback: all non-self
competitors = df_sheet[df_sheet["type"] != "self"]["hotel"].tolist()


# DATE
checkin = st.date_input("Check-in", date.today() + timedelta(days=14))
checkout = st.date_input("Check-out", checkin + timedelta(days=7))

run = st.button("Fetch")


# ─────────────────────────────
# RUN
# ─────────────────────────────
if run:

    results = []

    # SELF + COMPETITORS ONLY
    targets = [self_hotel] + competitors

    for hotel in targets:

        data = fetch_prices(checkin, checkout, 2, hotel)

        if not data:
            continue

        df = pd.DataFrame(data)

        df["is_self"] = df["hotel"] == self_hotel

        # SORT: SELF FIRST, then price desc
        df = df.sort_values(["is_self", "price"], ascending=[False, False])

        results.append(df)

    if not results:
        st.error("No data")
        st.stop()

    final = pd.concat(results)

    # ORDER: SELF FIRST
    final["priority"] = final["hotel"].apply(lambda x: 0 if x == self_hotel else 1)
    final = final.sort_values(["priority", "price"], ascending=[True, False])


    # ─────────────────────────────
    # DISPLAY ONLY AVAILABLE PERSON COUNTS
    # ─────────────────────────────
    st.subheader("Results")

    for hotel in final["hotel"].unique():

        sub = final[final["hotel"] == hotel]

        st.markdown(f"## {hotel}")

        for _, r in sub.iterrows():

            # show ONLY if price exists
            if pd.isna(r["price"]) or r["price"] <= 0:
                continue

            label = "SELF" if hotel == self_hotel else "COMPETITOR"

            st.write(f"""
**{label}**  
💰 €{r['price']:,.0f}  
🛏 €{r['per_night']:,.0f} / night  
---""")

else:
    st.info("Select dates and SELF hotel")

