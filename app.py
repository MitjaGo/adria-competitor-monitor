import streamlit as st
import pandas as pd
from datetime import date, timedelta
from apify_client import ApifyClient

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
st.set_page_config(page_title="Hotel Cluster Monitor", layout="wide")

SHEET_ID = "1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA"
SHEET_GID = "1313360174"

GOOGLE_SHEET_CSV = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"


# ─────────────────────────────────────────
# LOAD SHEET
# ─────────────────────────────────────────
@st.cache_data
def load_sheet():
    df = pd.read_csv(GOOGLE_SHEET_CSV)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


# ─────────────────────────────────────────
# APIFY
# ─────────────────────────────────────────
def scrape_urls(urls, checkin, checkout, adults):
    token = st.secrets.get("APIFY_TOKEN")
    client = ApifyClient(token)

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
st.title("🏨 Cluster Hotel Price Dashboard")

df = load_sheet()

# normalize columns (IMPORTANT)
df["number"] = pd.to_numeric(df["number"], errors="coerce")

cluster_name = st.selectbox(
    "Select self hotel cluster",
    ["Hotel Convent", "Vile brez balkona"]
)

cluster_id = 1 if cluster_name == "Hotel Convent" else 2

filtered = df[df["number"] == cluster_id]

st.write("### Selected hotels in cluster")
st.dataframe(filtered)

# date picker
today = date.today()
checkin = st.date_input("Check-in", today + timedelta(days=14))
checkout = st.date_input("Check-out", today + timedelta(days=21))
adults = st.selectbox("Adults", [2, 3, 4, 5, 6], index=0)

fetch = st.button("Fetch prices")

# ─────────────────────────────────────────
# RUN
# ─────────────────────────────────────────
if fetch:

    urls = filtered["url"].dropna().tolist()

    if len(urls) == 0:
        st.error("No URLs in this cluster")
        st.stop()

    with st.spinner("Fetching Apify data..."):
        data = scrape_urls(urls, checkin, checkout, adults)

    if not data:
        st.error("No data from Apify")
        st.stop()

    dfp = pd.DataFrame(data)

    # PRICE CLEAN
    dfp["price"] = pd.to_numeric(dfp.get("price", 0), errors="coerce").fillna(0)

    dfp = dfp.sort_values("price", ascending=False)

    st.subheader("💰 Prices (High → Low)")

    st.dataframe(dfp[["name", "price"]])

    # SELF vs COMP INDEX
    st.subheader("📊 Price Index")

    if "adria" in dfp["name"].str.lower().to_string():
        self_price = dfp[dfp["name"].str.lower().str.contains("adria")]["price"].mean()
        dfp["index_vs_self_%"] = ((dfp["price"] - self_price) / self_price) * 100

        st.dataframe(dfp[["name", "price", "index_vs_self_%"]])

