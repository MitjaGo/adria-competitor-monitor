import streamlit as st
import pandas as pd
from datetime import date, timedelta
from apify_client import ApifyClient

SHEET_URL = "https://docs.google.com/spreadsheets/d/1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA/export?format=csv"


# ─────────────────────────────
# DATA
# ─────────────────────────────

@st.cache_data(ttl=600)
def load_hotels():
    df = pd.read_csv(SHEET_URL)
    return df.dropna()


def get_token():
    return st.secrets.get("APIFY_TOKEN") or st.text_input("APIFY token", type="password")


# ─────────────────────────────
# ROOM TYPE DETECTOR
# ─────────────────────────────

def detect_room(text: str):

    t = (text or "").lower()

    if "half board" in t or "hb" in t:
        return "Half Board"

    if "bed & breakfast" in t or "breakfast" in t or "b&b" in t:
        return "Bed & Breakfast"

    if "apartment" in t or "kitchen" in t or "studio" in t:
        return "Rental"

    return None


# ─────────────────────────────
# APIFY SCRAPER
# ─────────────────────────────

def scrape(client, hotel, location, checkin, checkout, adults):

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

    results = []

    for i in items:

        name = i.get("name", "")

        desc = (
            i.get("description")
            or i.get("roomType")
            or ""
        )

        room_type = detect_room(desc + name)

        if not room_type:
            continue  # ❗ skip if no BB/HB/Rental

        price = i.get("price") or i.get("totalPrice") or 0

        try:
            price = float(price)
        except:
            continue

        if price <= 0:
            continue

        results.append({
            "hotel": hotel,
            "room_type": room_type,
            "adults": adults,
            "price": price,
        })

    return results


# ─────────────────────────────
# UI
# ─────────────────────────────

st.title("🏨 Hotel Pricing Engine")

df_hotels = load_hotels()

checkin = st.date_input("Check-in", date.today() + timedelta(days=14))
checkout = st.date_input("Check-out", checkin + timedelta(days=7))

adults_list = st.multiselect(
    "Guests",
    [2, 3, 4, 5, 6],
    default=[2, 3, 4]
)

hotel_filter = st.multiselect(
    "Hotels",
    df_hotels["hotel"].tolist() if "hotel" in df_hotels.columns else df_hotels.iloc[:, 0].tolist()
)

if st.button("Fetch Prices"):

    client = ApifyClient(get_token())

    all_data = []

    for _, h in df_hotels.iterrows():

        hotel_name = h.get("hotel") or h.iloc[0]
        location = h.get("location") or "Slovenia"

        if hotel_filter and hotel_name not in hotel_filter:
            continue

        for adults in adults_list:

            data = scrape(
                client,
                hotel_name,
                location,
                checkin.strftime("%Y-%m-%d"),
                checkout.strftime("%Y-%m-%d"),
                adults
            )

            for d in data:
                all_data.append(d)

    df = pd.DataFrame(all_data)

    if df.empty:
        st.warning("No data found")
        st.stop()

    # SORT HIGH → LOW
    df = df.sort_values("price", ascending=False)

    # ─────────────────────────────
    # OUTPUT (CLEAN PIVOT STYLE)
    # ─────────────────────────────

    st.subheader("Results (High → Low)")

    for _, r in df.iterrows():

        st.markdown(f"""
### {r['hotel']}

🏷️ {r['room_type']}  
👥 {r['adults']} persons  

## €{r['price']:,.0f}
""")

        st.divider()

    st.dataframe(df)

