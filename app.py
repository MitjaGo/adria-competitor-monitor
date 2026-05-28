import streamlit as st
import pandas as pd
from datetime import date, timedelta
from apify_client import ApifyClient


# ─────────────────────────────
# CONFIG
# ─────────────────────────────
SPREADSHEET_ID = "1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA"

TABS = {
    "Convent": "0",
    "Vile brez balkona": "1313360174"
}


# ─────────────────────────────
# LOAD GOOGLE SHEET TAB
# ─────────────────────────────
@st.cache_data
def load_tab(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={gid}"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip().str.lower()
    return df


# ─────────────────────────────
# APIFY
# ─────────────────────────────
def scrape_apify(urls, checkin, checkout, adults):
    client = ApifyClient(st.secrets["APIFY_TOKEN"])

    run = client.actor("pAk2GX3uArJTHBc9g").call({
        "startUrls": [{"url": u} for u in urls],
        "checkin": checkin.strftime("%Y-%m-%d"),
        "checkout": checkout.strftime("%Y-%m-%d"),
        "adults": adults,
        "currency": "EUR",
        "language": "en-us",
    })

    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        return []

    return list(client.dataset(dataset_id).iterate_items())


# ─────────────────────────────
# UI
# ─────────────────────────────
st.title("🏨 Multi-Tab Cluster Dashboard")

cluster_name = st.selectbox("Select cluster", list(TABS.keys()))

df = load_tab(TABS[cluster_name])

st.subheader(f"Cluster: {cluster_name}")
st.dataframe(df)

# ─────────────────────────────
# DATES
# ─────────────────────────────
today = date.today()
checkin = st.date_input("Check-in", today + timedelta(days=14))
checkout = st.date_input("Check-out", today + timedelta(days=21))
adults = st.selectbox("Adults", [2, 3, 4, 5, 6])


# ─────────────────────────────
# FETCH
# ─────────────────────────────
if st.button("Fetch prices"):

    urls = df["url"].dropna().tolist()

    if not urls:
        st.error("No URLs in this tab")
        st.stop()

    with st.spinner("Fetching Apify data..."):
        data = scrape_apify(urls, checkin, checkout, adults)

    if not data:
        st.error("No data from Apify")
        st.stop()

    dfp = pd.DataFrame(data)

    dfp["price"] = pd.to_numeric(dfp.get("price", 0), errors="coerce").fillna(0)

    # SORT HIGH → LOW
    dfp = dfp.sort_values("price", ascending=False)

    st.subheader("💰 Prices (High → Low)")
    st.dataframe(dfp[["name", "price"]])

    # SELF HOTEL DETECTION
    dfp["is_self"] = dfp["name"].str.lower().str.contains("adria")

    if dfp["is_self"].any():
        self_price = dfp[dfp["is_self"]]["price"].mean()
        dfp["price_index_%"] = ((dfp["price"] - self_price) / self_price) * 100

        st.subheader("📊 Price Index vs Self Hotel")
        st.dataframe(dfp[["name", "price", "price_index_%"]])
