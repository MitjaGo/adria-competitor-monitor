import streamlit as st
import pandas as pd
from datetime import date, timedelta
from apify_client import ApifyClient

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
st.set_page_config(page_title="Cluster Hotel Dashboard", layout="wide")

SHEET_ID = "1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA"
SHEET_GID = "1313360174"

SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"


# ─────────────────────────────────────────
# LOAD GOOGLE SHEET
# ─────────────────────────────────────────
@st.cache_data
def load_sheet():
    df = pd.read_csv(SHEET_URL)

    # clean columns
    df.columns = df.columns.str.strip().str.lower()

    # clean number column (IMPORTANT FIX)
    df["number"] = (
        df["number"]
        .astype(str)
        .str.strip()
    )

    df["number"] = pd.to_numeric(df["number"], errors="coerce")

    return df


# ─────────────────────────────────────────
# APIFY SCRAPER
# ─────────────────────────────────────────
def scrape_apify(urls, checkin, checkout, adults):
    token = st.secrets.get("APIFY_TOKEN")
    if not token:
        st.error("Missing APIFY token")
        return []

    client = ApifyClient(token)

    run = client.actor("pAk2GX3uArJTHBc9g").call({
        "startUrls": [{"url": u} for u in urls],
        "checkin": checkin.strftime("%Y-%m-%d"),
        "checkout": checkout.strftime("%Y-%m-%d"),
        "adults": adults,
        "currency": "EUR",
        "language": "en-us",
    })

    dataset_id = run.get("defaultDatasetId") or getattr(run, "default_dataset_id", None)

    if not dataset_id:
        return []

    return list(client.dataset(dataset_id).iterate_items())


# ─────────────────────────────────────────
# UI
# ─────────────────────────────────────────
st.title("🏨 Cluster Hotel Price Dashboard")

df = load_sheet()

# safety check
if "number" not in df.columns:
    st.error("Sheet must contain 'number' column")
    st.stop()

# cluster selector
cluster_map = {
    "Hotel Convent": 1,
    "Vile brez balkona": 2
}

cluster_name = st.selectbox("Select cluster", list(cluster_map.keys()))
cluster_id = cluster_map[cluster_name]

filtered = df[df["number"] == cluster_id]

st.subheader("Cluster hotels")
if filtered.empty:
    st.warning("No hotels in this cluster (check Google Sheet numbers)")
    st.stop()

st.dataframe(filtered)

# dates
today = date.today()
checkin = st.date_input("Check-in", today + timedelta(days=14))
checkout = st.date_input("Check-out", today + timedelta(days=21))
adults = st.selectbox("Adults", [2, 3, 4, 5, 6])

# fetch
if st.button("Fetch prices"):

    urls = filtered["url"].dropna().tolist()

    if len(urls) == 0:
        st.error("No URLs in selected cluster")
        st.stop()

    with st.spinner("Fetching Apify..."):
        data = scrape_apify(urls, checkin, checkout, adults)

    if not data:
        st.error("No data returned from Apify")
        st.stop()

    dfp = pd.DataFrame(data)

    # safe price parsing
    dfp["price"] = pd.to_numeric(dfp.get("price", 0), errors="coerce").fillna(0)

    # sort high → low (IMPORTANT REQUEST)
    dfp = dfp.sort_values("price", ascending=False)

    st.subheader("💰 Prices (High → Low)")
    st.dataframe(dfp[["name", "price"]])

    # self hotel detection
    dfp["is_self"] = dfp["name"].str.lower().str.contains("adria")

    if dfp["is_self"].any():
        self_price = dfp[dfp["is_self"]]["price"].mean()
        dfp["index_vs_self_%"] = ((dfp["price"] - self_price) / self_price) * 100

        st.subheader("📊 Price Index vs Self Hotel")
        st.dataframe(dfp[["name", "price", "index_vs_self_%"]])
