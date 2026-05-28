import streamlit as st
import pandas as pd
from datetime import date, timedelta
from apify_client import ApifyClient

SHEET = "https://docs.google.com/spreadsheets/d/1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA/export?format=csv"


@st.cache_data(ttl=600)
def load():
    return pd.read_csv(SHEET).dropna()


def token():
    return st.secrets.get("APIFY_TOKEN") or st.text_input("APIFY token", type="password")


def scrape(client, name, location, checkin, checkout, adults):

    run = client.actor("automation-lab/booking-scraper").call({
        "locationQuery": location,
        "checkin": checkin,
        "checkout": checkout,
        "adults": adults,
        "rooms": 1,
        "currency": "EUR",
        "maxResults": 25
    })

    dataset = client.dataset(getattr(run, "defaultDatasetId"))
    items = list(dataset.iterate_items())

    out = []

    for i in items:
        price = i.get("price") or 0
        try:
            price = float(price)
        except:
            continue

        if price <= 0:
            continue

        out.append({
            "hotel": name,
            "price": price,
        })

    return out


st.title("🏨 Hotel Pricing")

df = load()

checkin = st.date_input("Check-in", date.today() + timedelta(days=14))
checkout = st.date_input("Check-out", checkin + timedelta(days=7))
adults = st.selectbox("Adults", [2, 3, 4], 0)

if st.button("Fetch"):

    client = ApifyClient(token())

    results = []

    for _, r in df.iterrows():

        data = scrape(
            client,
            r["name"],
            r["location"],
            checkin.strftime("%Y-%m-%d"),
            checkout.strftime("%Y-%m-%d"),
            adults
        )

        for d in data:
            d["type"] = r["type"]
            d["url"] = r.get("url", "")

        results.extend(data)

    df = pd.DataFrame(results)

    if df.empty:
        st.warning("No data")
        st.stop()

    # SORT HIGH → LOW
    df = df.sort_values("price", ascending=False)

    st.subheader("Prices (High → Low)")

    for _, r in df.iterrows():
        st.markdown(f"""
### {r['hotel']}

🏷️ {r['type']}  
## €{r['price']:,.0f}
""")

    st.dataframe(df)

