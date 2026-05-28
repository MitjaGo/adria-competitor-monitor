import streamlit as st
import pandas as pd
from apify_client import ApifyClient

st.set_page_config(page_title="Pro Hotel Pricing Engine", layout="wide")

APIFY_ACTOR = "pAk2GX3uArJTHBc9g"

SHEETS = {
    "Convent": "https://docs.google.com/spreadsheets/d/1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA/export?format=csv&gid=1313360174",
    "Vile": "https://docs.google.com/spreadsheets/d/1at8Qo7Ne28Fb43WfhoXN0IpRBnwmenfgCVRZytTEGDA/export?format=csv&gid=0",
}

# ─────────────────────────────
# GOOGLE SHEET
# ─────────────────────────────
@st.cache_data(ttl=600)
def load_sheet(cluster):
    df = pd.read_csv(SHEETS[cluster])
    df.columns = [c.lower().strip() for c in df.columns]

    if "name" not in df.columns:
        df.rename(columns={df.columns[0]: "name"}, inplace=True)

    if "url" not in df.columns:
        df.rename(columns={df.columns[-1]: "url"}, inplace=True)

    if "type" not in df.columns:
        df["type"] = "comp"

    return df

# ─────────────────────────────
# APIFY
# ─────────────────────────────
def scrape_detail(client, url):
    run = client.actor(APIFY_ACTOR).call({
        "startUrls": [{"url": url}],
        "maxResults": 10,
        "currency": "EUR",
        "language": "en-us"
    })

    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        return []

    return list(client.dataset(dataset_id).iterate_items())

# ─────────────────────────────
# MEAL TYPE DETECTION
# ─────────────────────────────
def detect_meal(text):
    t = (text or "").lower()

    if "half board" in t or "hb" in t:
        return "Half Board"
    if "breakfast" in t or "bb" in t:
        return "B&B"
    if "apartment" in t or "self catering" in t or "rental" in t:
        return "Rental"

    return "Room"

# ─────────────────────────────
# PARSE HOTEL DATA
# ─────────────────────────────
def parse(items, hotel_name):

    out = []

    for h in items:

        room = h.get("roomType") or h.get("name")
        price = h.get("price")

        if price is None:
            continue

        try:
            price = float(price)
        except:
            continue

        meal = detect_meal(room)

        occupancy_prices = {}

        # try extract occupancy variants if exist
        for i in range(2, 7):
            key = f"price_{i}"
            if key in h:
                try:
                    occupancy_prices[i] = float(h[key])
                except:
                    pass

        if not occupancy_prices:
            occupancy_prices[2] = price  # fallback

        for pax, p in occupancy_prices.items():

            out.append({
                "hotel": hotel_name,
                "meal": meal,
                "pax": pax,
                "price": p
            })

    return out

# ─────────────────────────────
# UI
# ─────────────────────────────
st.title("🔥 PRO Hotel Pricing Engine")

cluster = st.selectbox("Cluster", ["Convent", "Vile"])

check = st.button("Fetch Pro Pricing")

if check:

    token = st.secrets.get("APIFY_TOKEN")
    if not token:
        st.error("Missing APIFY_TOKEN")
        st.stop()

    client = ApifyClient(token)

    sheet = load_sheet(cluster)

    all_data = []

    for _, row in sheet.iterrows():

        name = row["name"]
        url = row["url"]

        if not url:
            continue

        raw = scrape_detail(client, url)

        parsed = parse(raw, name)

        all_data.extend(parsed)

    if not all_data:
        st.warning("No pricing data found (actor limitation or blocked pages)")
        st.stop()

    df = pd.DataFrame(all_data)

    # ─────────────────────────────
    # INDEX CALC
    # ─────────────────────────────
    base = df[df["hotel"] == df["hotel"].iloc[0]]["price"].mean()

    df["index_vs_base"] = (df["price"] / base * 100).round(1)

    # ─────────────────────────────
    # UI TABLES
    # ─────────────────────────────
    st.subheader("Raw Pricing Matrix")
    st.dataframe(df)

    st.subheader("Meal Breakdown")

    st.dataframe(
        df.groupby(["hotel", "meal"])["price"].mean().reset_index()
    )

    st.subheader("Occupancy Breakdown (2–6 pax)")

    st.dataframe(
        df.groupby(["hotel", "pax"])["price"].mean().reset_index()
    )
        
