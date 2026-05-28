import streamlit as st
import pandas as pd
from datetime import date, timedelta
import time
import random

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
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
        token = st.secrets.get("APIFY_TOKEN")
        if token:
            return token
    except Exception:
        pass

    return os.getenv("APIFY_TOKEN")


def normalize_region(region: str) -> str:
    """
    Convert live Booking/Apify location text
    into stable internal region labels.
    """

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

def scrape_booking_prices(
    checkin: date,
    checkout: date,
    adults: int,
    location: str = "Ankaran, Slovenia",
    max_items: int = 30,
):
    """
    Reads REAL Booking.com data from Apify.
    """

    from apify_client import ApifyClient

    token = get_apify_token()

    if not token:
        st.error("No APIFY_TOKEN found.")
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
        "maxResults": max_items,
        "sortBy": "popularity",
    }

    with st.spinner(f"Fetching live Booking.com prices for {adults} adults..."):

        # START ACTOR
        run = client.actor("automation-lab/booking-scraper").call(
            run_input=run_input
        )

        # GET DATASET ID
        dataset_id = getattr(run, "default_dataset_id", None)

        if not dataset_id:
            try:
                dataset_id = run["defaultDatasetId"]
            except Exception:
                st.error("Could not get dataset ID.")
                return []

        dataset = client.dataset(dataset_id)

        # WAIT FOR DATASET TO FILL
        raw = []

        for _ in range(20):
            raw = list(dataset.iterate_items())

            if raw:
                break

            time.sleep(1)

        if not raw:
            st.warning("Apify returned no results.")
            return []

    # ─────────────────────────────────────────
    # NORMALIZE RESULTS
    # ─────────────────────────────────────────

    results = []

    for h in raw:

        name = h.get("name") or "Unknown"

        price = (
            h.get("price")
            or h.get("priceAmount")
            or h.get("totalPrice")
            or 0
        )

        try:
            price = float(price)
        except Exception:
            price = 0

        stars = (
            h.get("starRating")
            or h.get("stars")
            or 0
        )

        try:
            stars = int(float(stars))
        except Exception:
            stars = 0

        rating = (
            h.get("reviewScore")
            or h.get("rating")
            or 0
        )

        try:
            rating = float(rating)
        except Exception:
            rating = 0

        region_raw = (
            h.get("location")
            or h.get("address")
            or location
        )

        region = normalize_region(region_raw)

        booking_url = (
            h.get("url")
            or h.get("hotelUrl")
            or ""
        )

        is_self = "adria" in name.lower() and "ankaran" in name.lower()

        per_night = round(price / nights, 2) if nights else price

        results.append({
            "name": name,
            "region": region,
            "stars": stars,
            "rating": rating,
            "adults": adults,
            "nights": nights,
            "price_eur": price,
            "per_night": per_night,
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

# SIDEBAR
with st.sidebar:

    st.header("Search")

    checkin = st.date_input(
        "Check-in",
        value=default_in,
        min_value=today,
    )

    checkout = st.date_input(
        "Check-out",
        value=default_out,
        min_value=checkin + timedelta(days=1),
    )

    adults = st.selectbox(
        "Adults",
        [2, 3, 4],
        index=0,
    )

    stars_filter = st.slider(
        "Minimum stars",
        0,
        5,
        0,
    )

    region_filter = st.multiselect(
        "Regions",
        [
            "SI – Ankaran",
            "SI – Portorož",
            "SI – Piran",
            "HR – Rovinj",
            "HR – Poreč",
            "HR – Zadar",
            "HR – Split",
        ],
        default=[
            "SI – Ankaran",
            "SI – Portorož",
            "SI – Piran",
            "HR – Rovinj",
            "HR – Poreč",
        ],
    )

    token_input = st.text_input(
        "Apify Token",
        type="password",
        placeholder="apify_api_xxx",
    )

    if token_input:
        import os
        os.environ["APIFY_TOKEN"] = token_input
        st.success("Token loaded.")

    fetch_btn = st.button("Fetch Prices")


# ─────────────────────────────────────────────────────────────
# FETCH
# ─────────────────────────────────────────────────────────────

if fetch_btn:

    data = scrape_booking_prices(
        checkin=checkin,
        checkout=checkout,
        adults=adults,
    )

    if not data:
        st.error("No data received from Apify.")
        st.stop()

    df = pd.DataFrame(data)

    # CLEAN TYPES
    df["stars"] = pd.to_numeric(
        df["stars"],
        errors="coerce"
    ).fillna(0)

    df["price_eur"] = pd.to_numeric(
        df["price_eur"],
        errors="coerce"
    ).fillna(0)

    # FILTERS
    if region_filter:
        df = df[df["region"].isin(region_filter)]

    df = df[df["stars"] >= stars_filter]

    if df.empty:
        st.warning("No results after filters.")
        st.write("DEBUG DATA:")
        st.dataframe(pd.DataFrame(data))
        st.stop()

    # SORT
    df = df.sort_values("price_eur")

    # KPIs
    st.subheader("Overview")

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Hotels",
        len(df),
    )

    c2.metric(
        "Average Price",
        f"€{df['price_eur'].mean():.0f}",
    )

    c3.metric(
        "Cheapest",
        f"€{df['price_eur'].min():.0f}",
    )

    st.divider()

    # RESULTS
    st.subheader("Properties")

    for _, row in df.iterrows():

        badge = "🏨 COMPETITOR"

        if row["is_self"]:
            badge = "🌊 ADRIA ANKARAN"

        st.markdown(f"""
### {row['name']}

{badge}

⭐ {row['stars']} stars  
⭐ Review: {row['rating']}  
📍 {row['region']}

## €{row['price_eur']:,.0f}
€{row['per_night']:,.0f} / night

[Open Booking.com]({row['booking_url']})
        """)

        st.divider()

    # TABLE
    st.subheader("Table")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    # CSV EXPORT
    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download CSV",
        csv,
        file_name="booking_prices.csv",
        mime="text/csv",
    )

else:

    st.info("Select dates and click Fetch Prices.")

