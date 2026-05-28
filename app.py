import streamlit as st
import pandas as pd
from datetime import date, timedelta
from apify_client import ApifyClient

SHEET_URL = "https://docs.google.com/spreadsheets/d/1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA/export?format=csv"

st.set_page_config(page_title="Hotel Cluster Intelligence", layout="wide")


# ─────────────────────────────
# LOAD SHEET
# ─────────────────────────────
@st.cache_data(ttl=600)
def load_sheet():
    df = pd.read_csv(SHEET_URL)
    df.columns = df.columns.str.strip().str.lower()
    df["number"] = pd.to_numeric(df["number"], errors="coerce")
    df["hotel"] = df["hotel"].astype(str).str.strip()
    return df


# ─────────────────────────────
# APIFY FETCH
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

    dataset_id = run.get("defaultDatasetId")
    items = list(client.dataset(dataset_id).iterate_items())

    nights = (checkout - checkin).days or 1

    out = []

    for h in items:
        price = float(h.get("price") or 0)
        if price <= 0:
            continue

        out.append({
            "hotel": h.get("name"),
            "price": price,
            "per_night": round(price / nights, 2),
        })

    return out


# ─────────────────────────────
# UI
# ─────────────────────────────
st.title("🏨 Cluster Hotel Pricing Intelligence")

df = load_sheet()


# ─────────────────────────────
# SELECT CLUSTER BY NUMBER
# ─────────────────────────────
clusters = df[["number", "hotel"]].dropna().drop_duplicates()

cluster_map = {
    int(n): df[df["number"] == n]["hotel"].tolist()
    for n in clusters["number"].unique()
}

selected_number = st.selectbox(
    "Select cluster (number)",
    sorted(cluster_map.keys())
)

self_hotel = cluster_map[selected_number][0]
competitors = cluster_map[selected_number]


st.markdown(f"""
### Selected cluster: {selected_number}
**Self hotel:** {self_hotel}
**Included objects:** {len(competitors)}
""")


# ─────────────────────────────
# DATE INPUT
# ─────────────────────────────
checkin = st.date_input("Check-in", date.today() + timedelta(days=14))
checkout = st.date_input("Check-out", checkin + timedelta(days=7))

run = st.button("Fetch prices")


# ─────────────────────────────
# RUN
# ─────────────────────────────
if run:

    results = []

    for hotel in competitors:

        data = fetch_prices(checkin, checkout, 2, hotel)

        if not data:
            continue

        df_live = pd.DataFrame(data)

        df_live["cluster"] = selected_number
        df_live["source_hotel"] = self_hotel
        df_live["is_self"] = df_live["hotel"] == self_hotel

        results.append(df_live)

    if not results:
        st.error("No data returned from Apify")
        st.stop()

    final = pd.concat(results)

    # ─────────────────────────────
    # SORT: SELF FIRST, THEN PRICE DESC
    # ─────────────────────────────
    final = final.sort_values(["is_self", "price"], ascending=[False, False])

    # ─────────────────────────────
    # SELF BASELINE INDEX
    # ─────────────────────────────
    self_avg = final[final["is_self"]]["price"].mean()

    final["price_index"] = (final["price"] / self_avg * 100).round(1)
    final["vs_self"] = (final["price"] - self_avg).round(0)


    # ─────────────────────────────
    # OUTPUT
    # ─────────────────────────────
    st.subheader("Cluster comparison")

    st.metric("Self average price", f"€{self_avg:.0f}")

    st.divider()

    for hotel in final["hotel"].unique():

        sub = final[final["hotel"] == hotel]

        st.markdown(f"## 🏨 {hotel}")

        for _, r in sub.iterrows():

            tag = "SELF" if r["is_self"] else "COMPETITOR"

            st.write(f"""
**{tag}**

💰 €{r['price']:,.0f}  
🛏 €{r['per_night']:,.0f} / night  
📊 Index: {r['price_index']}  
📈 vs Self: {r['vs_self']:+.0f} €

---
""")

else:
    st.info("Select cluster and dates")

