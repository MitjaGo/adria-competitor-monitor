import streamlit as st
import pandas as pd
from datetime import date, timedelta
import os
from apify_client import ApifyClient

# ─────────────────────────────
# CONFIG
# ─────────────────────────────
st.set_page_config(page_title="Hotel Cluster Monitor", layout="wide")

SHEETS = {
    "Hotel Convent": "https://docs.google.com/spreadsheets/d/1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA/export?format=csv&gid=0",
    "Vile brez balkona": "https://docs.google.com/spreadsheets/d/1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA/export?format=csv&gid=1313360174",
}

# ─────────────────────────────
# TOKEN
# ─────────────────────────────
def get_token():
    return st.secrets.get("APIFY_TOKEN") or os.getenv("APIFY_TOKEN")


# ─────────────────────────────
# LOAD GOOGLE SHEET
# ─────────────────────────────
def load_sheet(cluster):
    df = pd.read_csv(SHEETS[cluster])
    df.columns = [c.lower().strip() for c in df.columns]
    return df


# ─────────────────────────────
# APIFY (STABLE)
# ─────────────────────────────
def scrape(client, urls, checkin, checkout, adults):

    run = client.actor("pAk2GX3uArJTHBc9g").call({
        "startUrls": [{"url": u} for u in urls],
        "checkin": str(checkin),
        "checkout": str(checkout),
        "adults": adults,
        "rooms": 1,
        "currency": "EUR",
        "language": "en-us",
        "maxResults": 20
    })

    # ─────────────────────────────
    # SAFE dataset extraction
    # ─────────────────────────────
    dataset_id = None

    # new apify-client style (BEST)
    if hasattr(run, "default_dataset_id"):
        dataset_id = run.default_dataset_id

    # fallback (most common)
    if not dataset_id and hasattr(run, "defaultDatasetId"):
        dataset_id = run.defaultDatasetId

    # dict fallback
    if not dataset_id:
        try:
            dataset_id = run.get("defaultDatasetId")
        except:
            pass

    if not dataset_id:
        st.error(f"Apify run failed or no dataset created: {run}")
        return []

    dataset = client.dataset(dataset_id)

    items = list(dataset.iterate_items())

    return items


# ─────────────────────────────
# UI
# ─────────────────────────────
st.title("🏨 Cluster Hotel Monitor")

cluster = st.selectbox("Cluster", list(SHEETS.keys()))

today = date.today()

checkin = st.date_input("Check-in", today + timedelta(days=14))
checkout = st.date_input("Check-out", today + timedelta(days=21))
adults = st.selectbox("Adults", [2, 3, 4, 5, 6])

fetch = st.button("Fetch prices")


# ─────────────────────────────
# MAIN
# ─────────────────────────────
if fetch:

    token = get_token()
    if not token:
        st.error("Missing APIFY_TOKEN")
        st.stop()

    client = ApifyClient(token)

    sheet = load_sheet(cluster)

    if sheet.empty:
        st.error("Empty Google Sheet")
        st.stop()

    if "url" not in sheet.columns:
        st.error("Sheet must contain column: url")
        st.stop()

    all_results = []

    progress = st.progress(0)

    for i, row in sheet.iterrows():

        url = row.get("url")
        name = row.get("name")

        if pd.isna(url):
            continue

        try:
            data = scrape_apify(
                client,
                [url],
                checkin,
                checkout,
                adults
            )
        except Exception as e:
            st.warning(f"Failed {name}: {e}")
            continue

        for d in data:
            d["hotel"] = name
            d["type"] = row.get("type", "")
            all_results.append(d)

        progress.progress((i + 1) / len(sheet))

    progress.empty()

    df = pd.DataFrame(all_results)

    # ─────────────────────────────
    # DEBUG (NE IZBRIŠI)
    # ─────────────────────────────
    st.write("DEBUG RAW:", df.head())

    if df.empty:
        st.error("No data from Apify")
        st.stop()

    # CLEAN PRICE
    df["price"] = pd.to_numeric(df.get("price", 0), errors="coerce").fillna(0)

    # SORT HIGH → LOW
    df = df.sort_values("price", ascending=False)

    st.subheader(f"Cluster: {cluster}")

    # ─────────────────────────────
    # DISPLAY
    # ─────────────────────────────
    for _, r in df.iterrows():

        is_self = str(r.get("type", "")).lower() == "self"

        color = "#1a73e8" if is_self else "#111"

        st.markdown(f"""
<div style="padding:10px;border-bottom:1px solid #eee;">

    <div style="font-size:18px;font-weight:600;color:{color}">
        {r.get('hotel','Unknown')}
    </div>

    <div style="color:#666;font-size:13px;">
        ⭐ {r.get('rating',0)}
    </div>

    <div style="font-size:22px;font-weight:700;">
        €{r.get('price',0):,.0f}
    </div>

</div>
""", unsafe_allow_html=True)

else:
    st.info("Select cluster and click Fetch")
        
