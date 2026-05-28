import streamlit as st
import pandas as pd
from datetime import date, timedelta
import time
from apify_client import ApifyClient

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Adria Ankaran – Competitor Monitor",
    page_icon="🌊",
    layout="wide",
)

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def get_apify_token():
    import os
    try:
        return st.secrets.get("APIFY_TOKEN") or os.getenv("APIFY_TOKEN")
    except:
        return os.getenv("APIFY_TOKEN")


def detect_room_type(text: str) -> str:
    t = (text or "").lower()

    if any(x in t for x in ["half board", "hb"]):
        return "Half Board"

    if any(x in t for x in ["bed and breakfast", "b&b", "breakfast included", "breakfast"]):
        return "Bed & Breakfast"

    if any(x in t for x in ["apartment", "studio", "kitchen", "kitchenette"]):
        return "Rental / Apartment"

    return "Room only"


def normalize_region(region: str) -> str:
    if not region:
        return "Other"

    r = region.lower()

    if "ankaran" in r:
        return "SI – Ankaran"
    if "portoro" in r:
        return "SI – Portorož"
    if "piran" in r:
        return "SI – Piran"
    if "rovinj" in r:
        return "HR – Rovinj"
    if "pore" in r:
        return "HR – Poreč"
    if "zadar" in r:
        return "HR – Zadar"
    if "split" in r:
        return "HR – Split"

    return "Other"


# ─────────────────────────────────────────────────────────────
# APIFY SCRAPER
# ─────────────────────────────────────────────────────────────

def scrape_booking(checkin, checkout, adults, location="Ankaran, Slovenia"):

    token = get_apify_token()

    if not token:
        st.error("Missing APIFY token")
        return []

    client = ApifyClient(token)

    nights = max((checkout - checkin).days, 1)

    run_input = {
        "locationQuery": location,
        "checkin": checkin.strftime("%Y-%m-%d"),
        "checkout": checkout.strftime("%Y-%m-%d"),
        "adults": adults,
        "rooms": 1,
        "currency": "EUR",
        "language": "en-us",
        "maxResults": 30,
        "sortBy": "popularity",
    }

    with st.spinner(f"Fetching Apify data ({adults} adults) ..."):

        run = client.actor("automation-lab/booking-scraper").call(run_input=run_input)

        dataset_id = (
            getattr(run, "defaultDatasetId", None)
            or run.get("defaultDatasetId")
        )

        if not dataset_id:
            st.error("No dataset returned from Apify")
            return []

        dataset = client.dataset(dataset_id)

        raw = []
        for _ in range(30):
            raw = list(dataset.iterate_items())
            if raw:
                break
            time.sleep(1.2)

    if not raw:
        st.warning("No results from Apify")
        return []

    results = []

    for h in raw:

        name = (
            h.get("name")
            or h.get("hotelName")
            or h.get("title")
            or "Unknown"
        )

        price = (
            h.get("price")
            or h.get("priceAmount")
            or h.get("totalPrice")
            or 0
        )

        try:
            price = float(price)
        except:
            price = 0

        stars = h.get("starRating") or h.get("stars") or 0
        try:
            stars = int(float(stars))
        except:
            stars = 0

        rating = h.get("reviewScore") or h.get("rating") or 0
        try:
            rating = float(rating)
        except:
            rating = 0

        region_raw = h.get("location") or h.get("address") or location
        region = normalize_region(region_raw)

        booking_url = h.get("url") or h.get("hotelUrl") or ""

        room_text = h.get("roomType") or h.get("mealPlan") or h.get("description") or name
        room_type = detect_room_type(room_text)

        per_night = round(price / nights, 2)

        is_self = "adria" in name.lower()

        results.append({
            "name": name,
            "region": region,
            "stars": stars,
            "rating": rating,
            "price_eur": price,
            "per_night": per_night,
            "room_type": room_type,
            "is_self": is_self,
            "booking_url": booking_url,
        })

    return results


# ─────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────

st.title("🌊 Adria Ankaran – Competitor Monitor")

today = date.today()

default_in = today + timedelta(days=14)
default_out = default_in + timedelta(days=7)

with st.sidebar:

    st.header("Search")

    checkin = st.date_input("Check-in", default_in, min_value=today)
    checkout = st.date_input("Check-out", default_out, min_value=checkin + timedelta(days=1))

    adults = st.selectbox("Adults", [2, 3, 4], index=0)

    stars_filter = st.slider("Min stars", 0, 5, 0)

    token = st.text_input("Apify token", type="password")

    if token:
        import os
        os.environ["APIFY_TOKEN"] = token

    fetch = st.button("Fetch Prices")


# ─────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────

if fetch:

    data = scrape_booking(checkin, checkout, adults)

    if not data:
        st.stop()

    df = pd.DataFrame(data)

    df["price_eur"] = pd.to_numeric(df["price_eur"], errors="coerce").fillna(0)
    df["stars"] = pd.to_numeric(df["stars"], errors="coerce").fillna(0)

    df = df[df["stars"] >= stars_filter]

    # SORT: HIGH → LOW
    df = df.sort_values("price_eur", ascending=False)

    st.subheader("Overview")

    c1, c2, c3 = st.columns(3)

    c1.metric("Hotels", len(df))
    c2.metric("Avg price", f"€{df['price_eur'].mean():.0f}")
    c3.metric("Cheapest", f"€{df['price_eur'].min():.0f}")

    st.divider()

    st.subheader("Hotels")

    for _, r in df.iterrows():

        badge = "🌊 ADRIA" if r["is_self"] else "🏨 COMPETITOR"

        st.markdown(f"""
### {r['name']}

{badge}  
📍 {r['region']}  
⭐ {r['stars']} | ⭐ {r['rating']}  
🏷️ {r['room_type']}

## €{r['price_eur']:,.0f}
€{r['per_night']:,.0f} / night

[Open]({r['booking_url']})
        """)

        st.divider()

    st.subheader("Table")

    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download CSV",
        csv,
        "booking_prices.csv",
        "text/csv"
    )

else:
    st.info("Select dates and click Fetch Prices.")

