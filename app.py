import os
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import time
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
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="st-"] { font-family: 'DM Sans', sans-serif; }
.main { background: #f0f4f8; }

.hero-banner {
    background: linear-gradient(135deg, #0a4f6e 0%, #1a7a9e 50%, #0d8f8f 100%);
    border-radius: 16px; padding: 2rem 2.5rem; color: white;
    margin-bottom: 1.5rem; box-shadow: 0 8px 32px rgba(10,79,110,0.25);
}
.hero-banner h1 { margin: 0 0 0.3rem 0; font-size: 2rem; color: white; font-weight: 600; }
.hero-banner p  { margin: 0; opacity: 0.85; font-size: 1rem; }

.metric-card {
    background: white; border-radius: 12px; padding: 1.2rem 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07); border-left: 4px solid #1a7a9e;
}
.property-card {
    background: white; border-radius: 12px; padding: 1.2rem 1.5rem;
    margin-bottom: 0.8rem; box-shadow: 0 2px 10px rgba(0,0,0,0.07);
    border-top: 3px solid #ccc;
}
.property-card.adria   { border-top-color: #e8623a; }
.property-card.cheaper { border-top-color: #2ecc71; }
.property-card.pricier { border-top-color: #e74c3c; }

.tag {
    display: inline-block; padding: 2px 10px; border-radius: 20px;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
}
.tag-adria   { background: #fde8e0; color: #c0392b; }
.tag-cheaper { background: #d5f5e3; color: #1a7a40; }
.tag-pricier { background: #fde8e0; color: #a93226; }
.tag-similar { background: #d6eaf8; color: #1a5276; }

.info-box {
    background: #e8f4f8; border: 1px solid #a8d5e8; border-radius: 8px;
    padding: 0.8rem 1.2rem; font-size: 0.88rem; color: #0a4f6e;
}
</style>
""", unsafe_allow_html=True)

# ── Helpers & State Initializer ───────────────────────────────────────────────
if "df_data" not in st.session_state:
    st.session_state.df_data = None
if "search_clicked" not in st.session_state:
    st.session_state.search_clicked = False

def _get_apify_token():
    try:
        if "APIFY_TOKEN" in st.secrets:
            return st.secrets["APIFY_TOKEN"]
    except Exception:
        pass
    return os.getenv("APIFY_TOKEN")

# FIXED: Added leading underscore to _progress_element to exclude it from hash calculations
@st.cache_data(ttl=3600, show_spinner=False)
def scrape_booking_prices(checkin: date, checkout: date, adults: int, dest: str, _progress_element=None) -> list[dict]:
    token = _get_apify_token()
    
    if token:
        try:
            if _progress_element:
                _progress_element.markdown(f"📡 **System Status:** Connecting to Apify API hub (Querying {adults} Adults dynamic tier)...")
            
            from apify_client import ApifyClient
            client = ApifyClient(token)
            nights = (checkout - checkin).days or 1

            run_input = {
                "locationQuery": dest,
                "checkin": checkin.strftime("%Y-%m-%d"),
                "checkout": checkout.strftime("%Y-%m-%d"),
                "adults": adults,
                "rooms": 1,
                "currency": "EUR",
                "language": "en-us",
                "maxResults": 30,
                "sortBy": "popularity",
            }
            
            if _progress_element:
                _progress_element.markdown(f"🤖 **System Status:** Launching `automation-lab/booking-scraper` payload container for {adults} adults...")
                
            run = client.actor("automation-lab/booking-scraper").call(
                run_input=run_input, 
                wait=timedelta(seconds=180)
            )
            
            if _progress_element:
                _progress_element.markdown(f"📥 **System Status:** Extracting data table dictionary from Apify Dataset key `{run['defaultDatasetId'][:8]}...`")
                
            raw = list(client.dataset(run["defaultDatasetId"]).iterate_items())

            if not raw:
                if _progress_element:
                    _progress_element.markdown("⚠️ **System Status:** Apify worker returned 0 targets due to access filtering. Activating simulation layer...")
                return _demo_data(checkin, checkout, adults)

            if _progress_element:
                _progress_element.markdown(f"⚙️ **System Status:** Normalizing pricing arrays and identifying internal property variables...")

            results = []
            for h in raw:
                price_eur = float(h.get("price") or 0)
                per_night = float(h.get("pricePerNight") or (price_eur / nights if nights else 0))
                name = h.get("name") or "Unknown"
                
                results.append({
                    "name": name,
                    "region": h.get("location") or dest,
                    "stars": int(h.get("starRating") or 0),
                    "rating": float(h.get("reviewScore") or 0),
                    "adults": adults,
                    "nights": nights,
                    "price_eur": price_eur,
                    "per_night": round(per_night, 2),
                    "is_self": "adria ankaran" in name.lower(),
                    "source": "apify_live",
                    "booking_url": h.get("url") or "",
                })
            if results: return results
        except Exception as e:
            st.sidebar.error(f"Apify Connection Refused: {str(e)}")
            
    if _progress_element:
        _progress_element.markdown(f"⚠️ **System Status:** No API connectivity. Falling back to local algorithmic math engine for {adults} adults...")
        time.sleep(0.8)
        
    return _demo_data(checkin, checkout, adults)

def _demo_data(checkin: date, checkout: date, adults: int) -> list[dict]:
    nights = (checkout - checkin).days or 1
    base = {2: 1.0, 3: 1.35, 4: 1.65}.get(adults, 1.0)
    month = checkin.month
    season = 1.5 if month in (7, 8) else 1.2 if month in (6, 9) else 0.75

    def price(base_night, spread=0.15):
        raw = base_night * adults * base * season * nights
        random.seed((checkin.toordinal() + adults + int(base_night)) % 1000)
        noise = random.uniform(1 - spread, 1 + spread)
        return round(raw * noise, 0)

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
            "name": p["name"], "region": p["region"], "stars": p["stars"], "rating": p["rating"],
            "adults": adults, "nights": nights, "price_eur": total, "per_night": round(total / nights, 2),
            "is_self": p["is_self"], "source": "demo", "booking_url": "https://www.booking.com"
        })
    return out

def stars_display(n):
    return "⭐" * n if n else "–"

# ── Sidebar Settings ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌊 Search Settings")
    st.divider()

    today = date.today()
    default_in = today + timedelta(days=14)
    default_out = default_in + timedelta(days=7)

    checkin = st.date_input("Check-in", value=default_in, min_value=today)
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
        options=["SI – Ankaran", "SI – Portorož", "SI – Piran", "HR – Rovinj", "HR – Poreč", "HR – Zadar", "HR – Split"],
        default=["SI – Ankaran", "SI – Portorož", "SI – Piran", "HR – Rovinj", "HR – Poreč"],
    )
    stars_filter = st.slider("Minimum stars", 1, 5, 3)

    st.divider()
    token_loaded = _get_apify_token()
    if token_loaded:
        st.success("✅ Secure Token loaded from secrets")
    else:
        st.warning("⚠️ No Token detected in secrets config")

    st.divider()
    if st.button("🔍 Fetch Prices", use_container_width=True):
        st.session_state.search_clicked = True
        st.session_state.df_data = None  

# ── Hero Layout ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
  <h1>Adria Ankaran – Competitor Monitor</h1>
  <p>Coastal Slovenia & Istria Croatia · Room price comparison · Booking.com</p>
</div>
""", unsafe_allow_html=True)

# ── Welcome Grid Validation ───────────────────────────────────────────────────
if not st.session_state.search_clicked:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="metric-card"><h4>📍 Coverage</h4><p>14 properties across Key Adriatic Sectors</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="metric-card"><h4>👥 Configuration</h4><p>Compare room allocations from 2 to 4 adults</p></div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="metric-card"><h4>🔄 Source Routing</h4><p>Live scrapers running via automated API endpoints</p></div>', unsafe_allow_html=True)
    st.info("👈 Select parameters and launch **Fetch Prices** to begin monitoring analytics.")
    st.stop()

# ── Session State Scraping Engine ─────────────────────────────────────────────
if st.session_state.df_data is None:
    adult_counts = [a for a, show in [(2, show_2), (3, show_3), (4, show_4)] if show]
    if not adult_counts:
        st.warning("Please select at least one guest configuration.")
        st.stop()

    all_data = []
    
    message_container = st.empty()
    progress_bar = st.progress(0)
    
    message_container.markdown("⚙️ **System Status:** Initializing structural workers and cache managers...")
    time.sleep(0.4)
    
    for i, adults in enumerate(adult_counts):
        current_pct = i / len(adult_counts)
        progress_bar.progress(current_pct)
        
        # FIXED: Named explicitly with an underscore inside the call to prevent Streamlit hashing
        rows = scrape_booking_prices(
            checkin, 
            checkout, 
            adults, 
            "Ankaran, Slovenian Istria, Slovenia", 
            _progress_element=message_container
        )
        all_data.extend(rows)
        
        if len(adult_counts) > 1 and i < len(adult_counts) - 1:
            message_container.markdown("⏳ **System Status:** Cool-down padding active. Cooling proxies before next tier call...")
            time.sleep(5)
        
    progress_bar.progress(1.0)
    message_container.markdown("✅ **System Status:** Data compilation complete! Assembling user interface layouts...")
    time.sleep(0.5)
    
    progress_bar.empty()
    message_container.empty()
    
    st.session_state.df_data = pd.DataFrame(all_data)

df = st.session_state.df_data.copy()

if region_filter:
    df = df[df["region"].isin(region_filter) | df["is_self"]]
df = df[df["stars"] >= stars_filter]

if df.empty:
    st.warning("No data returned within active filter boundaries.")
    if st.button("Reset Search"):
        st.session_state.df_data = None
        st.rerun()
    st.stop()

# ── KPI Block Rendering ───────────────────────────────────────────────────────
adria_rows = df[df["is_self"]]
comp_rows = df[~df["is_self"]]

adria_avg = adria_rows["price_eur"].mean() if not adria_rows.empty else 0
comp_avg = comp_rows["price_eur"].mean() if not comp_rows.empty else 0
cheapest = comp_rows.loc[comp_rows["price_eur"].idxmin()] if not comp_rows.empty else None
priciest = comp_rows.loc[comp_rows["price_eur"].idxmax()] if not comp_rows.empty else None

c1, c2, c3, c4 = st.columns(4)
c1.metric("Adria Ankaran Avg", f"€{adria_avg:,.0f}", delta=f"vs €{comp_avg:,.0f} Comps", delta_color="inverse" if adria_avg > comp_avg else "normal")
c2.metric("Tracked Grouping", len(df["name"].unique()) - 1)
c3.metric("Floor Competitor", f"€{cheapest['price_eur']:,.0f}" if cheapest is not None else "–", cheapest["name"] if cheapest is not None else "")
c4.metric("Ceiling Competitor", f"€{priciest['price_eur']:,.0f}" if priciest is not None else "–", priciest["name"] if priciest is not None else "")

st.caption(f"Status Matrix: {'🟢 API Production Data' if df['source'].iloc[0] == 'apify_live' else '🟡 Simulation Mode'} · {nights} Nights Stay Window")
st.divider()

# ── Dashboard Workspace Tabs ──────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Price Comparison", "🗂️ Full Table", "📈 Charts"])

with tab1:
    for adults in sorted(df["adults"].unique()):
        sub = df[df["adults"] == adults].sort_values("price_eur")
        st.markdown(f"### 👥 Room Tier Allocation: {adults} Adults")

        adria_price = sub[sub["is_self"]]["price_eur"].values
        adria_ref = float(adria_price[0]) if len(adria_price) else None

        for _, row in sub.iterrows():
            is_self = row["is_self"]
            price = row["price_eur"]

            if is_self:
                card_class, tag_html = "adria", '<span class="tag tag-adria">OUR PROPERTY</span>'
            elif adria_ref and price < adria_ref * 0.95:
                card_class, tag_html = "cheaper", f'<span class="tag tag-cheaper">€{adria_ref - price:.0f} under our floor</span>'
            elif adria_ref and price > adria_ref * 1.05:
                card_class, tag_html = "pricier", f'<span class="tag tag-pricier">€{price - adria_ref:.0f} over our premium</span>'
            else:
                card_class, tag_html = "", '<span class="tag tag-similar">Direct Match Zone</span>'

            bar_pct = min(100, int(price / (sub["price_eur"].max() or 1) * 100))
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
                  <span style="color:#888;font-size:0.8rem;">€{row['per_night']:,.0f}/Night value</span>
                </div>
              </div>
              <div style="margin-top:0.6rem;background:#eee;border-radius:4px;height:6px;">
                <div style="width:{bar_pct}%;background:{bar_color};height:6px;border-radius:4px;"></div>
              </div>
            </div>""", unsafe_allow_html=True)

with tab2:
    display_df = df[["name", "region", "stars", "rating", "adults", "nights", "price_eur", "per_night", "is_self"]].copy()
    display_df.columns = ["Property", "Region", "Stars", "Rating", "Adults", "Nights", "Total €", "Per Night €", "Our Target"]
    display_df = display_df.sort_values(["Adults", "Total €"])
    display_df["Stars"] = display_df["Stars"].apply(stars_display)
    display_df["Our Target"] = display_df["Our Target"].apply(lambda x: "🎯" if x else "")

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Total €": st.column_config.NumberColumn(format="€%.0f"),
            "Per Night €": st.column_config.NumberColumn(format="€%.0f"),
            "Rating": st.column_config.NumberColumn(format="%.1f"),
        },
    )
    st.download_button("⬇️ Export Structural CSV Data", display_df.to_csv(index=False).encode("utf-8"), "competitor_matrix.csv", "text/csv")

with tab3:
    import altair as alt

    chart_df = df[["name", "adults", "price_eur", "per_night", "is_self", "region"]].copy()
    chart_df["label"] = chart_df["adults"].astype(str) + " guests"
    chart_df["color"] = chart_df["is_self"].apply(lambda x: "Adria Ankaran" if x else "Competitor Vector")

    st.markdown("#### Aggregate Stay Valuation across Comp Sets")
    bar = (
        alt.Chart(chart_df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("name:N", sort="-y", title=None, axis=alt.Axis(labelAngle=-45, labelLimit=150)),
            y=alt.Y("price_eur:Q", title="Stay Cost (€)"),
            color=alt.Color("color:N", scale=alt.Scale(domain=["Adria Ankaran", "Competitor Vector"], range=["#e8623a", "#1a7a9e"]), legend=alt.Legend(title="Allocation Hub")),
            column=alt.Column("label:N", title=None),
            tooltip=["name", "region", "price_eur"]
        ).properties(height=320, width=280)
    )
    st.altair_chart(bar, use_container_width=False)

    st.markdown("#### Verified Per-Night Price Distribution (Cleaned)")
    box = (
        alt.Chart(chart_df)
        .mark_boxplot(extent="min-max", size=35)
        .encode(
            x=alt.X("label:N", title="Guest Structural Index"),
            y=alt.Y("per_night:Q", title="Per-Night Rate (€)"),
            color=alt.Color("color:N", scale=alt.Scale(domain=["Adria Ankaran", "Competitor Vector"], range=["#e8623a", "#1a7a9e"]))
        ).properties(height=300)
    )
    st.altair_chart(box, use_container_width=True)
    
        
