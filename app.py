import streamlit as st
import pandas as pd
from datetime import date, timedelta
from apify_client import ApifyClient

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
SHEET_URL = "https://docs.google.com/spreadsheets/d/1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA/export?format=csv&gid=1313360174"

CLUSTER_MAP = {
    1: "Hotel Convent",
    2: "Vile brez balkona"
}

# ─────────────────────────────────────────
# LOAD SHEET
# ─────────────────────────────────────────
@st.cache_data
def load_sheet():
    df = pd.read_csv(SHEET_URL)
    df.columns = df.columns.str.strip().str.lower()

    # CLEAN NUMBER COLUMN (CRITICAL FIX)
    df["number"] = (
        df["number"]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )

    df["number"] = pd.to_numeric(df["number"], errors="coerce")

    # MAP NUMBER → NAME (IMPORTANT FIX)
    df["cluster"] = df["number"].map(CLUSTER_MAP)

    return df


# ─────────────────────────────────────────
# APIFY
# ─────────────────────────────────────────
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


# ─────────────────────────────────────────
# UI
# ─────────────────────────────────────────
st.title("🏨 Multi Cluster Hotel Dashboard")

df = load_sheet()

# REMOVE BAD ROWS
df = df.dropna(subset=["cluster"])

# ─────────────────────────────
# SELECT CLUSTER (NOW BY NAME)
# ─────────────────────────────
cluster_name = st.selectbox(
    "Select hotel cluster",
    df["cluster"].unique().tolist()
)

filtered = df[df["cluster"] == cluster_name]

st.subheader(f"Selected: {cluster_name}")
st.dataframe(filtered)

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

    urls = filtered["url"].dropna().tolist()

    if not urls:
        st.error("No URLs in selected cluster")
        st.stop()

    with st.spinner("Fetching Apify data..."):
        data = scrape_apify(urls, checkin, checkout, adults)

    if not data:
        st.error("No data from Apify")
        st.stop()

    dfp = pd.DataFrame(data)

    dfp["price"] = pd.to_numeric(dfp.get("price", 0), errors="coerce").fillna(0)

    # SORT HIGH → LOW (your requirement)
    dfp = dfp.sort_values("price", ascending=False)

    st.subheader("💰 Prices (High → Low)")
    st.dataframe(dfp[["name", "price"]])

    # SELF DETECTION
    dfp["is_self"] = dfp["name"].str.lower().str.contains("adria")

    if dfp["is_self"].any():
        self_price = dfp[dfp["is_self"]]["price"].mean()
        dfp["price_index_%"] = ((dfp["price"] - self_price) / self_price) * 100

        st.subheader("📊 Price Index vs Self")
        st.dataframe(dfp[["name", "price", "price_index_%"]])
