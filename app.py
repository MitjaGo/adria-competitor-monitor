import streamlit as st
import requests
import pandas as pd
from datetime import date, timedelta
import time
import json
import re
from urllib.parse import urlencode
import random

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Adria Ankaran – Competitor Price Monitor",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}
h1, h2, h3 { font-family: 'DM Serif Display', serif; }

.main { background: #f0f4f8; }

.hero-banner {
    background: linear-gradient(135deg, #0a4f6e 0%, #1a7a9e 50%, #0d8f8f 100%);
    border-radius: 16px;
    padding: 2rem 2.5rem;
    color: white;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 32px rgba(10,79,110,0.25);
}
.hero-banner h1 { color: white; margin: 0 0 0.3rem 0; font-size: 2rem; }
.hero-banner p  { margin: 0; opacity: 0.85; font-size: 1rem; }

.metric-card {
    background: white;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    border-left: 4px solid #1a7a9e;
}

.property-card {
    background: white;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 0.8rem;
    box-shadow: 0 2px 10px rgba(0,0,0,0.07);
    border-top: 3px solid transparent;
    transition: box-shadow 0.2s;
}
.property-card:hover { box-shadow: 0 4px 20px rgba(0,0,0,0.12); }
.property-card.adria { border-top-color: #e8623a; }
.property-card.cheaper { border-top-color: #2ecc71; }
.property-card.pricier { border-top-color: #e74c3c; }

.tag {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.tag-adria    { background: #fde8e0; color: #c0392b; }
.tag-cheaper  { background: #d5f5e3; color: #1a7a40; }
.tag-pricier  { background: #fde8e0; color: #a93226; }
.tag-similar  { background: #d6eaf8; color: #1a5276; }

.stButton > button {
    background: linear-gradient(135deg, #0a4f6e, #1a7a9e);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.6rem 2rem;
    font-size: 1rem;
    width: 100%;
}
.stButton > button:hover { opacity: 0.88; }

.info-box {
    background: #e8f4f8;
    border: 1px solid #a8d5e8;
    border-radius: 8px;
    padding: 0.8rem 1.2rem;
    font-size: 0.88rem;
    color: #0a4f6e;
}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
COMPETITORS = [
    {"name": "Adria Ankaran",           "booking_id": "219994", "region": "Slovenia – Ankaran",  "is_self": True},
    {"name": "Camping Adria Mobilehome","booking_id": None,     "region": "Slovenia – Ankaran",  "is_self": False},
    {"name": "Bernot Hostel",           "booking_id": None,     "region": "Slovenia – Ankaran",  "is_self": False},
    {"name": "Kempinski Palace Portorož","booking_id": None,    "region": "Slovenia – Portorož", "is_self": False},
    {"name": "Hotel Riviera Portorož",  "booking_id": None,     "region": "Slovenia – Portorož", "is_self": False},
    {"name": "Hotel Piran",             "booking_id": None,     "region": "Slovenia – Piran",    "is_self": False},
    {"name": "Valamar Riviera",         "booking_id": None,     "region": "Croatia – Poreč",     "is_self": False},
    {"name": "Sol Garden Istra",        "booking_id": None,     "region": "Croatia – Poreč",     "is_self": False},
    {"name": "Maistra Resort Rovinj",   "booking_id": None,     "region": "Croatia – Rovinj",    "is_self": False},
    {"name": "Hotel Lone Rovinj",       "booking_id": None,     "region": "Croatia – Rovinj",    "is_self": False},
    {"name": "Hotel Monte Mulini",      "booking_id": None,     "region": "Croatia – Rovinj",    "is_self": False},
    {"name": "Falkensteiner Punta Skala","booking_id": None,    "region": "Croatia – Zadar",     "is_self": False},
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_apify_token():
    import os
    try:
        return st.secrets.get("APIFY_TOKEN") or os.getenv("APIFY_TOKEN")
    except Exception:
        return os.getenv("APIFY_TOKEN")


def _apify_scrape(checkin: date, checkout: date, adults: int,
                  location: str, token: str, max_items: int = 30) -> list[dict]:
    """
    Call the Apify Booking.com scraper actor and return normalised results.
    Actor: automation-lab/booking-scraper
    Docs:  https://apify.com/automation-lab/booking-scraper
    """
    ACTOR_ID = "automation-lab~booking-scraper"   # ✅ correct actor ID
    BASE_URL = "https://api.apify.com/v2"

    run_input = {
        "locationQuery": location,                 # ✅ correct field name
        "checkin":       checkin.strftime("%Y-%m-%d"),
        "checkout":      checkout.strftime("%Y-%m-%d"),
        "adults":        adults,
        "rooms":         1,
        "currency":      "EUR",
        "language":      "en-gb",
        "maxResults":    max_items,
    }

    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {token}",
    }

    run_resp = requests.post(
        f"{BASE_URL}/acts/{ACTOR_ID}/runs",
        json=run_input,
        headers=headers,
        params={"waitForFinish": 120},
        timeout=130,
    )
    run_resp.raise_for_status()
    run_data   = run_resp.json()
    run_id     = run_data["data"]["id"]
    dataset_id = run_data["data"]["defaultDatasetId"]

    # Poll until done
    for _ in range(30):
        status_resp = requests.get(
            f"{BASE_URL}/actor-runs/{run_id}",
            headers=headers, timeout=15,
        )
        status = status_resp.json()["data"]["status"]
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break
        time.sleep(5)

    if status != "SUCCEEDED":
        return []

    items_resp = requests.get(
        f"{BASE_URL}/datasets/{dataset_id}/items",
        headers=headers,
        params={"format": "json", "clean": True, "limit": max_items},
        timeout=20,
    )
    items_resp.raise_for_status()
    raw = items_resp.json()

    nights = (checkout - checkin).days or 1
    results = []
    for h in raw:
        price_raw = h.get("price") or h.get("priceForDisplay") or 0
        try:
            price_eur = float(str(price_raw).replace(",", "").replace("€", "").strip())
        except ValueError:
            price_eur = 0.0

        name   = h.get("name") or h.get("hotel_name") or "Unknown"
        stars  = int(h.get("stars") or h.get("starRating") or 0)
        rating = float(h.get("rating") or h.get("reviewScore") or 0)
        region = h.get("address", {}).get("country", "") if isinstance(h.get("address"), dict) \
                 else h.get("city", location)
        is_self = "adria ankaran" in name.lower()

        results.append({
            "name":        name,
            "region":      region or location,
            "stars":       stars,
            "rating":      rating,
            "adults":      adults,
            "nights":      nights,
            "price_eur":   price_eur,
            "per_night":   round(price_eur / nights, 2) if nights else price_eur,
            "is_self":     is_self,
            "source":      "apify_live",
            "booking_url": h.get("url") or h.get("bookingUrl") or "",
        })

    return results


def scrape_booking_prices(checkin: date, checkout: date, adults: int,
                          dest: str, progress_bar=None) -> list[dict]:
    token = _get_apify_token()
    if token:
        try:
            results = _apify_scrape(checkin, checkout, adults, dest, token)
            if results:
                return results
        except Exception as e:
            st.warning(f"Apify error: {e} — falling back to demo data.")
    return _demo_data(checkin, checkout, adults)


def _demo_data(checkin: date, checkout: date, adults: int) -> list[dict]:
    nights = (checkout - checkin).days or 1
    base   = {2: 1.0, 3: 1.35, 4: 1.65}.get(adults, 1.0)
    month  = checkin.month
    season = 1.5 if month in (7, 8) else 1.2 if month in (6, 9) else 0.75

    def price(base_night, spread=0.15):
        raw   = base_night * adults * base * season * nights
        noise = random.uniform(1 - spread, 1 + spread)
        return round(raw * noise, 0)

    random.seed((checkin.toordinal() + adults) % 100)

    properties = [
        {"name": "Adria Ankaran Resort & Spa",  "region": "SI – Ankaran",  "stars": 4, "base_night": 65,  "is_self": True,  "rating": 8.1},
        {"name": "Kempinski Palace Portorož",   "region": "SI – Portorož", "stars": 5, "base_night": 165, "is_self": False, "rating": 9.0},
        {"name": "Hotel Riviera Portorož",      "region": "SI – Portorož", "stars": 4, "base_night": 90,  "is_self": False, "rating": 8.3},
        {"name": "Hotel Piran",                 "region": "SI – Piran",    "stars": 4, "base_night": 75,  "is_self": False, "rating": 8.6},
        {"name": "Hotel Tartini Piran",         "region": "SI – Piran",    "stars": 3, "base_night": 55,  "is_self": False, "rating": 8.0},
        {"name": "Hostel Bernot",               "region": "SI – Ankaran",  "stars": 2, "base_night": 28,  "is_self": False, "rating": 7.4},
        {"name": "Hotel Lone Rovinj",           "region": "HR – Rovinj",   "stars": 5, "base_night": 145, "is_self": False, "rating": 8.9},
        {"name": "Hotel Monte Mulini Rovinj",   "region": "HR – Rovinj",   "stars": 5, "base_night": 155, "is_self": False, "rating": 9.1},
        {"name": "Maistra Resort Rovinj",       "region": "HR – Rovinj",   "stars": 4, "base_night": 95,  "is_self": False, "rating": 8.5},
        {"name": "Valamar Riviera Poreč",       "region": "HR – Poreč",    "stars": 4, "base_night": 85,  "is_self": False, "rating": 8.2},
        {"name": "Sol Garden Istra Poreč",      "region": "HR – Poreč",    "stars": 4, "base_night": 80,  "is_self": False, "rating": 8.0},
        {"name": "Hotel Parentino Poreč",       "region": "HR – Poreč",    "stars": 3, "base_night": 58,  "is_self": False, "rating": 7.8},
        {"name": "Falkensteiner Punta Skala",   "region": "HR – Zadar",    "stars": 5, "base_night": 130, "is_self": False, "rating": 9.0},
        {"name": "Boutique Hotel Orsula Split", "region": "HR – Split",    "stars": 4, "base_night": 105, "is_self": False, "rating": 8.7},
    ]

    out = []
    for p in properties:
        total = price(p["base_night"])
        out.append({
            "name":        p["name"],
            "region":      p["region"],
            "stars":       p["stars"],
            "rating":      p["rating"],
            "adults":      adults,
            "nights":      nights,
            "price_eur":   total,
            "per_night":   round(total / nights, 2),
            "is_self":     p["is_self"],
            "source":      "demo",
            "booking_url": "https://www.booking.com/hotel/si/adria-ankaran.html"
                           if p["is_self"] else
                           f"https://www.booking.com/searchresults.html?ss={p['name'].replace(' ', '+')}",
        })
    return out


def stars_display(n):
    return "⭐" * n if n else "–"


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌊 Search Settings")
    st.divider()

    today       = date.today()
    default_in  = today + timedelta(days=14)
    default_out = default_in + timedelta(days=7)

    checkin  = st.date_input("Check-in",  value=default_in,  min_value=today)
    checkout = st.date_input("Check-out", value=default_out, min_value=checkin + timedelta(days=1))

    nights = (checkout - checkin).days
    st.caption(f"📅 {nights} night{'s' if nights != 1 else ''}")

    st.divider()
    st.markdown("**Guests per room**")
    show_2 = st.checkbox("2 adults", value=True)
    show_3 = st.checkbox("3 adults", value=True)
    show_4 = st.checkbox("4 adults", value=True)

    st.divider()
    region_filter = st.multiselect(
        "Filter regions",
        options=["SI – Ankaran", "SI – Portorož", "SI – Piran",
                 "HR – Rovinj", "HR – Poreč", "HR – Zadar", "HR – Split"],
        default=["SI – Ankaran", "SI – Portorož", "SI – Piran",
                 "HR – Rovinj", "HR – Poreč"],
    )

    stars_filter = st.slider("Minimum stars", 1, 5, 3)

    st.divider()
    st.markdown("**🔑 Apify API Token**")
    apify_token_input = st.text_input(
        "Paste your token for live data",
        type="password",
        placeholder="apify_api_xxxx…",
        help="Free at apify.com — $5/month credit. Leave blank for demo data.",
    )
    if apify_token_input:
        import os; os.environ["APIFY_TOKEN"] = apify_token_input
        st.success("✅ Live data enabled")
    else:
        import os
        if os.getenv("APIFY_TOKEN") or (hasattr(st, "secrets") and st.secrets.get("APIFY_TOKEN")):
            st.success("✅ Token loaded from secrets")
        else:
            st.info("No token → demo data mode")

    st.divider()
    search_btn = st.button("🔍 Fetch Prices", use_container_width=True)

    st.markdown("""
<div class="info-box">
<b>ℹ️ Live data:</b> Add your free <a href="https://apify.com" target="_blank">Apify</a> token above.<br>
<b>Demo mode:</b> Realistic simulated pricing used when no token provided.
</div>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
  <h1>Adria Ankaran – Competitor Monitor</h1>
  <p>Coastal Slovenia & Istria Croatia · Room price comparison · Booking.com</p>
</div>
""", unsafe_allow_html=True)

# ── Main ──────────────────────────────────────────────────────────────────────
if not search_btn:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""<div class="metric-card">
            <h4>📍 Coverage</h4>
            <p>14 properties across Ankaran, Portorož, Piran, Rovinj, Poreč, Zadar</p>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""<div class="metric-card">
            <h4>👥 Guest Configs</h4>
            <p>Compare prices for 2, 3 and 4 adults per room simultaneously</p>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown("""<div class="metric-card">
            <h4>🔄 Data Source</h4>
            <p>Live Booking.com data via Apify, with realistic fallback if needed</p>
        </div>""", unsafe_allow_html=True)
    st.info("👈 Select dates and guests, then click **Fetch Prices** in the sidebar.")
    st.stop()

# ── Fetch data ────────────────────────────────────────────────────────────────
adult_counts = [a for a, show in [(2, show_2), (3, show_3), (4, show_4)] if show]

if not adult_counts:
    st.warning("Select at least one guest configuration.")
    st.stop()

all_data = []
progress = st.progress(0, text="Fetching prices…")

for i, adults in enumerate(adult_counts):
    progress.progress(i / len(adult_counts), text=f"Fetching prices for {adults} adults…")
    rows = scrape_booking_prices(checkin, checkout, adults, "Ankaran, Slovenia")
    all_data.extend(rows)
    time.sleep(0.3)

progress.progress(1.0, text="Done!")
time.sleep(0.4)
progress.empty()

df = pd.DataFrame(all_data)

# ── Filter ────────────────────────────────────────────────────────────────────
if region_filter:
    df = df[df["region"].isin(region_filter) | df["is_self"]]
df = df[df["stars"] >= stars_filter]

if df.empty:
    st.warning("No results match your filters.")
    st.stop()

# ── KPI row ───────────────────────────────────────────────────────────────────
adria_rows = df[df["is_self"]]
comp_rows  = df[~df["is_self"]]

adria_avg = adria_rows["price_eur"].mean() if not adria_rows.empty else 0
comp_avg  = comp_rows["price_eur"].mean()  if not comp_rows.empty else 0
cheapest  = comp_rows.loc[comp_rows["price_eur"].idxmin()] if not comp_rows.empty else None
priciest  = comp_rows.loc[comp_rows["price_eur"].idxmax()] if not comp_rows.empty else None

c1, c2, c3, c4 = st.columns(4)
c1.metric("Adria Ankaran avg", f"€{adria_avg:,.0f}",
          delta=f"vs €{comp_avg:,.0f} comp avg",
          delta_color="inverse" if adria_avg > comp_avg else "normal")
c2.metric("Competitors tracked", len(df["name"].unique()) - 1)
c3.metric("Cheapest competitor",
          f"€{cheapest['price_eur']:,.0f}" if cheapest is not None else "–",
          cheapest["name"] if cheapest is not None else "")
c4.metric("Most expensive",
          f"€{priciest['price_eur']:,.0f}" if priciest is not None else "–",
          priciest["name"] if priciest is not None else "")

source_note = "🟢 Live data" if df["source"].iloc[0] == "apify_live" else "🟡 Demo data (no Apify token)"
st.caption(source_note + f" · {nights} nights · {checkin} → {checkout}")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Price Comparison", "🗂️ Full Table", "📈 Charts"])

# ── TAB 1 ─────────────────────────────────────────────────────────────────────
with tab1:
    for adults in adult_counts:
        sub = df[df["adults"] == adults].sort_values("price_eur")
        st.markdown(f"### 👥 {adults} Adults")

        adria_price = sub[sub["is_self"]]["price_eur"].values
        adria_ref   = float(adria_price[0]) if len(adria_price) else None

        for _, row in sub.iterrows():
            is_self = row["is_self"]
            price   = row["price_eur"]

            if is_self:
                card_class = "adria"
                tag_html   = '<span class="tag tag-adria">OUR PROPERTY</span>'
            elif adria_ref and price < adria_ref * 0.95:
                card_class = "cheaper"
                tag_html   = f'<span class="tag tag-cheaper">€{adria_ref - price:.0f} cheaper</span>'
            elif adria_ref and price > adria_ref * 1.05:
                card_class = "pricier"
                tag_html   = f'<span class="tag tag-pricier">€{price - adria_ref:.0f} pricier</span>'
            else:
                card_class = ""
                tag_html   = '<span class="tag tag-similar">similar</span>'

            bar_pct   = min(100, int(price / (sub["price_eur"].max() or 1) * 100))
            bar_color = "#e8623a" if is_self else "#1a7a9e"

            st.markdown(f"""
<div class="property-card {card_class}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <b style="font-size:1.05rem;">{row['name']}</b> {tag_html}<br>
      <span style="color:#666;font-size:0.85rem;">
        {stars_display(row['stars'])} &nbsp;·&nbsp; ⭐ {row['rating']} &nbsp;·&nbsp; {row['region']}
      </span>
    </div>
    <div style="text-align:right;">
      <span style="font-size:1.5rem;font-weight:700;color:#0a4f6e;">€{price:,.0f}</span><br>
      <span style="color:#888;font-size:0.8rem;">€{row['per_night']:,.0f}/night</span>
    </div>
  </div>
  <div style="margin-top:0.6rem;background:#eee;border-radius:4px;height:6px;">
    <div style="width:{bar_pct}%;background:{bar_color};height:6px;border-radius:4px;"></div>
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

# ── TAB 2 ─────────────────────────────────────────────────────────────────────
with tab2:
    display_df = df[["name", "region", "stars", "rating", "adults",
                      "nights", "price_eur", "per_night", "is_self"]].copy()
    display_df.columns = ["Property", "Region", "Stars", "Rating",
                          "Adults", "Nights", "Total €", "Per Night €", "Our Property"]
    display_df = display_df.sort_values(["Adults", "Total €"])
    display_df["Stars"]        = display_df["Stars"].apply(stars_display)
    display_df["Our Property"] = display_df["Our Property"].apply(lambda x: "✅" if x else "")

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Total €":     st.column_config.NumberColumn(format="€%.0f"),
            "Per Night €": st.column_config.NumberColumn(format="€%.0f"),
            "Rating":      st.column_config.NumberColumn(format="%.1f"),
        },
    )
    csv = display_df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", csv, "competitor_prices.csv", "text/csv")

# ── TAB 3 ─────────────────────────────────────────────────────────────────────
with tab3:
    import altair as alt

    chart_df = df[["name", "adults", "price_eur", "is_self", "region"]].copy()
    chart_df["label"] = chart_df["adults"].astype(str) + " adults"
    chart_df["color"] = chart_df["is_self"].apply(lambda x: "Adria Ankaran" if x else "Competitor")

    st.markdown("#### Total stay price by property and guest count")
    bar = (
        alt.Chart(chart_df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("name:N", sort="-y", title=None,
                    axis=alt.Axis(labelAngle=-40, labelLimit=160)),
            y=alt.Y("price_eur:Q", title="Total price (€)"),
            color=alt.Color("color:N",
                scale=alt.Scale(domain=["Adria Ankaran", "Competitor"],
                                range=["#e8623a", "#1a7a9e"]),
                legend=alt.Legend(title="Type")),
            column=alt.Column("label:N", title="", header=alt.Header(labelFontSize=13)),
            tooltip=["name", "region", "price_eur", "adults"],
        )
        .properties(height=340)
    )
    st.altair_chart(bar, use_container_width=False)

    st.markdown("#### Per-night price distribution (box plot)")
    box = (
        alt.Chart(chart_df)
        .mark_boxplot(extent="min-max", size=30)
        .encode(
            x=alt.X("label:N", title="Guest count"),
            y=alt.Y("price_eur:Q", title="Price per night (€)"),
            color=alt.Color("color:N",
                scale=alt.Scale(domain=["Adria Ankaran", "Competitor"],
                                range=["#e8623a", "#1a7a9e"])),
        )
        .properties(height=300)
    )
    st.altair_chart(box, use_container_width=True)
