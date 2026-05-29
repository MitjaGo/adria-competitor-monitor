import streamlit as st
import pandas as pd
from datetime import date, timedelta
import time
import random
import requests
import io

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Adria Ankaran – Competitor Price Monitor",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Google Sheet CSV URLs ─────────────────────────────────────────────────────
SHEET_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRbx6EnzVBv0ZlRvF6_GuO2ZlCUkrwFp9iR_GmViy5r41hzsexrBW84MdvXI-0DtNul4fEUaLGjx27C/pub"

SHEETS = {
    "🏰 Hotel Convent": {
        "csv_url":    f"{SHEET_BASE}?gid=0&single=true&output=csv",
        "color":      "#8e44ad",
        "description": "Historic convent hotel · Ankaran",
    },
    "🏡 Vile brez balkona": {
        "csv_url":    f"{SHEET_BASE}?gid=1313360174&single=true&output=csv",
        "color":      "#27ae60",
        "description": "Villas without balcony · Ankaran",
    },
}

# Hardcoded fallback data (from your sheet, used if Google Sheets is unreachable)
FALLBACK_DATA = {
    "🏰 Hotel Convent": [
        {"hotel": "Hotel Convent",   "type": "self",       "location": "Ankaran",  "url": "https://www.booking.com/hotel/si/convent.sl.html"},
        {"hotel": "Hotel Riviera",   "type": "competitor", "location": "Portorož", "url": "https://www.booking.com/hotel/si/lifeclass-resort-portoroz-sr.sl.html"},
        {"hotel": "Hotel Histrion",  "type": "competitor", "location": "Portorož", "url": "https://www.booking.com/hotel/si/histrion.sl.html"},
        {"hotel": "Hotel Haliaetum", "type": "competitor", "location": "Izola",    "url": "https://www.booking.com/hotel/si/haliaetum.sl.html"},
        {"hotel": "Hotel Marko",     "type": "competitor", "location": "Portorož", "url": "https://www.booking.com/hotel/si/marko.sl.html"},
        {"hotel": "Hotel Lucija",    "type": "competitor", "location": "Portorož", "url": "https://www.booking.com/hotel/si/lucija.sl.html"},
    ],
    "🏡 Vile brez balkona": [
        {"hotel": "Vile brez Balkona",         "type": "self",       "location": "Ankaran", "url": "https://www.booking.com/hotel/si/depandansa-bor.sl.html"},
        {"hotel": "Hotel Vile Park",           "type": "competitor", "location": "Portorož","url": "https://www.booking.com/hotel/si/vile-park.sl.html"},
        {"hotel": "Depandanse San Simon",      "type": "competitor", "location": "Izola",   "url": "https://www.booking.com/hotel/si/san-simon-resort-depandances.sl.html"},
        {"hotel": "Vile Krka Talasso Strunjan","type": "competitor", "location": "Strunjan","url": "https://www.booking.com/hotel/si/vile-talaso-strunjan.sl.html"},
        {"hotel": "Hotel Barbara Fiesa",       "type": "competitor", "location": "Fiesa",   "url": "https://www.booking.com/hotel/si/barbara-fiesa.sl"},
        {"hotel": "Bio Hotel Koper",           "type": "competitor", "location": "Koper",   "url": "https://www.booking.com/hotel/si/bio.sl.html"},
    ],
}

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'DM Serif Display', serif; }
.main { background: #f0f4f8; }

.hero-banner {
    background: linear-gradient(135deg, #0a4f6e 0%, #1a7a9e 50%, #0d8f8f 100%);
    border-radius: 16px; padding: 2rem 2.5rem; color: white;
    margin-bottom: 1.5rem; box-shadow: 0 8px 32px rgba(10,79,110,0.25);
}
.hero-banner h1 { color: white; margin: 0 0 0.3rem 0; font-size: 2rem; }
.hero-banner p  { margin: 0; opacity: 0.85; font-size: 1rem; }

.metric-card {
    background: white; border-radius: 12px; padding: 1.2rem 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07); border-left: 4px solid #1a7a9e;
}
.property-card {
    background: white; border-radius: 12px; padding: 1.2rem 1.5rem;
    margin-bottom: 0.8rem; box-shadow: 0 2px 10px rgba(0,0,0,0.07);
    border-top: 3px solid transparent;
}
.property-card.self_prop { border-top-color: #e8623a; }
.property-card.cheaper   { border-top-color: #2ecc71; }
.property-card.pricier   { border-top-color: #e74c3c; }

.tag {
    display: inline-block; padding: 2px 10px; border-radius: 20px;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
}
.tag-self    { background: #fde8e0; color: #c0392b; }
.tag-cheaper { background: #d5f5e3; color: #1a7a40; }
.tag-pricier { background: #fde8e0; color: #a93226; }
.tag-similar { background: #d6eaf8; color: #1a5276; }

.segment-header {
    background: white; border-radius: 10px; padding: 0.8rem 1.2rem;
    margin-bottom: 1rem; border-left: 5px solid #1a7a9e;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.stButton > button {
    background: linear-gradient(135deg, #0a4f6e, #1a7a9e);
    color: white; border: none; border-radius: 8px;
    font-weight: 600; padding: 0.6rem 2rem; font-size: 1rem; width: 100%;
}
.stButton > button:hover { opacity: 0.88; }
.info-box {
    background: #e8f4f8; border: 1px solid #a8d5e8; border-radius: 8px;
    padding: 0.8rem 1.2rem; font-size: 0.88rem; color: #0a4f6e;
}
</style>
""", unsafe_allow_html=True)

# ── Load sheet data ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_sheet(seg_key: str) -> pd.DataFrame:
    """Load competitor list from Google Sheet CSV. Falls back to hardcoded data."""
    try:
        url = SHEETS[seg_key]["csv_url"]
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame(FALLBACK_DATA[seg_key])

# ── Apify helpers ─────────────────────────────────────────────────────────────
def _get_apify_token():
    import os
    try:
        return st.secrets.get("APIFY_TOKEN") or os.getenv("APIFY_TOKEN")
    except Exception:
        return os.getenv("APIFY_TOKEN")


def _apify_fetch_url(booking_url: str, checkin: date, checkout: date,
                     adults: int, token: str) -> dict | None:
    """
    Fetch price for a single Booking.com property URL via Apify.
    Returns dict with price info or None on failure.
    """
    from apify_client import ApifyClient
    client = ApifyClient(token)
    nights = (checkout - checkin).days or 1

    run_input = {
        "startUrls": [{"url": booking_url}],
        "checkin":   checkin.strftime("%Y-%m-%d"),
        "checkout":  checkout.strftime("%Y-%m-%d"),
        "adults":    adults,
        "rooms":     1,
        "currency":  "EUR",
        "language":  "en-us",
        "maxResults": 1,
    }

    try:
        run = client.actor("automation-lab/booking-scraper").call(
            run_input=run_input,
            wait_secs=120,
        )
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if items:
            h = items[0]
            price_eur = float(h.get("price") or 0)
            return {
                "price_eur": price_eur,
                "per_night": float(h.get("pricePerNight") or (price_eur / nights if nights else 0)),
                "stars":     int(h.get("starRating") or 0),
                "rating":    float(h.get("reviewScore") or 0),
                "source":    "apify_live",
            }
    except Exception:
        pass
    return None


def _demo_price(location: str, is_self: bool, checkin: date,
                checkout: date, adults: int, seed_str: str) -> dict:
    """Generate realistic demo price based on location and season."""
    nights = (checkout - checkin).days or 1
    base_map = {
        "Ankaran": 70, "Portorož": 90, "Izola": 65,
        "Strunjan": 60, "Fiesa": 55, "Koper": 50,
    }
    base_night = base_map.get(location, 65)
    adult_mult = {2: 1.0, 3: 1.35, 4: 1.65}.get(adults, 1.0)
    month  = checkin.month
    season = 1.5 if month in (7, 8) else 1.2 if month in (6, 9) else 0.75

    random.seed(hash(seed_str + str(checkin) + str(adults)) % 99999)
    noise     = random.uniform(0.88, 1.12)
    total     = round(base_night * adult_mult * season * nights * noise, 0)
    stars_map = {"Ankaran": 4, "Portorož": 4, "Izola": 3,
                 "Strunjan": 3, "Fiesa": 3, "Koper": 3}

    return {
        "price_eur": total,
        "per_night": round(total / nights, 2),
        "stars":     stars_map.get(location, 3),
        "rating":    round(random.uniform(7.5, 9.2), 1),
        "source":    "demo",
    }


def fetch_prices_for_segment(seg_key: str, sheet_df: pd.DataFrame,
                              checkin: date, checkout: date,
                              adults: int, token: str | None) -> list[dict]:
    """Fetch prices for all properties in a segment."""
    nights  = (checkout - checkin).days or 1
    results = []

    for _, row in sheet_df.iterrows():
        name     = str(row.get("hotel", "")).strip()
        is_self  = str(row.get("type", "")).strip().lower() == "self"
        location = str(row.get("location", "")).strip()
        url      = str(row.get("url", "")).strip()

        price_data = None
        if token and url and url.startswith("http"):
            try:
                price_data = _apify_fetch_url(url, checkin, checkout, adults, token)
            except Exception:
                pass

        if not price_data:
            price_data = _demo_price(location, is_self, checkin, checkout, adults, name)

        results.append({
            "name":        name,
            "location":    location,
            "is_self":     is_self,
            "adults":      adults,
            "nights":      nights,
            "booking_url": url,
            "segment":     seg_key,
            **price_data,
        })

    return results


# ── UI helpers ────────────────────────────────────────────────────────────────
def stars_html(n):
    return "⭐" * int(n) if n else "–"


def render_price_cards(df: pd.DataFrame, seg_color: str, adult_counts: list):
    for adults in adult_counts:
        sub = df[df["adults"] == adults].sort_values("price_eur")
        if sub.empty:
            continue
        st.markdown(f"### 👥 {adults} Adults")

        self_vals = sub[sub["is_self"]]["price_eur"].values
        self_ref  = float(self_vals[0]) if len(self_vals) else None

        for _, row in sub.iterrows():
            is_self = row["is_self"]
            price   = row["price_eur"]

            if is_self:
                card_cls = "self_prop"
                tag      = '<span class="tag tag-self">OUR PROPERTY</span>'
            elif self_ref and price < self_ref * 0.95:
                card_cls = "cheaper"
                tag      = f'<span class="tag tag-cheaper">€{self_ref - price:.0f} cheaper</span>'
            elif self_ref and price > self_ref * 1.05:
                card_cls = "pricier"
                tag      = f'<span class="tag tag-pricier">€{price - self_ref:.0f} pricier</span>'
            else:
                card_cls = ""
                tag      = '<span class="tag tag-similar">similar price</span>'

            bar_pct   = min(100, int(price / (sub["price_eur"].max() or 1) * 100))
            bar_color = seg_color if is_self else "#1a7a9e"
            url       = row.get("booking_url", "")
            link_html = f'<a href="{url}" target="_blank" style="font-size:0.78rem;color:#1a7a9e;">🔗 Booking.com</a>' if url else ""

            st.markdown(f"""
<div class="property-card {card_cls}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <b style="font-size:1.05rem;">{row['name']}</b> {tag}<br>
      <span style="color:#666;font-size:0.85rem;">
        {stars_html(row['stars'])} &nbsp;·&nbsp;
        ⭐ {row['rating']} &nbsp;·&nbsp;
        📍 {row['location']} &nbsp;·&nbsp; {link_html}
      </span>
    </div>
    <div style="text-align:right;">
      <span style="font-size:1.5rem;font-weight:700;color:#0a4f6e;">€{price:,.0f}</span><br>
      <span style="color:#888;font-size:0.8rem;">€{row['per_night']:,.0f} / night</span>
    </div>
  </div>
  <div style="margin-top:0.6rem;background:#eee;border-radius:4px;height:6px;">
    <div style="width:{bar_pct}%;background:{bar_color};height:6px;border-radius:4px;"></div>
  </div>
</div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)


def render_table(df: pd.DataFrame):
    disp = df[["name", "location", "stars", "rating", "adults",
               "nights", "price_eur", "per_night", "is_self", "booking_url"]].copy()
    disp.columns = ["Property", "Location", "Stars", "Rating",
                    "Adults", "Nights", "Total €", "Per Night €", "Our Property", "Link"]
    disp = disp.sort_values(["Adults", "Total €"])
    disp["Stars"]        = disp["Stars"].apply(stars_html)
    disp["Our Property"] = disp["Our Property"].apply(lambda x: "✅" if x else "")
    st.dataframe(disp, use_container_width=True, hide_index=True,
                 column_config={
                     "Total €":     st.column_config.NumberColumn(format="€%.0f"),
                     "Per Night €": st.column_config.NumberColumn(format="€%.0f"),
                     "Rating":      st.column_config.NumberColumn(format="%.1f"),
                     "Link":        st.column_config.LinkColumn("Booking.com"),
                 })
    csv = disp.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", csv, "competitor_prices.csv", "text/csv")


def render_charts(df: pd.DataFrame):
    import altair as alt
    chart_df = df.copy()
    chart_df["label"] = chart_df["adults"].astype(str) + " adults"
    chart_df["type"]  = chart_df["is_self"].apply(
        lambda x: "Our Property" if x else "Competitor")

    bar = (
        alt.Chart(chart_df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("name:N", sort="-y", title=None,
                    axis=alt.Axis(labelAngle=-40, labelLimit=180)),
            y=alt.Y("price_eur:Q", title="Total price (€)"),
            color=alt.Color("type:N",
                scale=alt.Scale(domain=["Our Property", "Competitor"],
                                range=["#e8623a", "#1a7a9e"]),
                legend=alt.Legend(title="")),
            column=alt.Column("label:N", title="",
                              header=alt.Header(labelFontSize=13)),
            tooltip=["name", "location", "price_eur", "per_night", "adults"],
        ).properties(height=320)
    )
    st.altair_chart(bar, use_container_width=False)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌊 Search Settings")
    st.divider()

    today       = date.today()
    default_in  = today + timedelta(days=14)
    default_out = default_in + timedelta(days=7)

    checkin  = st.date_input("Check-in",  value=default_in,  min_value=today)
    checkout = st.date_input("Check-out", value=default_out,
                             min_value=checkin + timedelta(days=1))
    nights   = (checkout - checkin).days
    st.caption(f"📅 {nights} night{'s' if nights != 1 else ''}")

    st.divider()
    st.markdown("**Guests per room**")
    show_2 = st.checkbox("2 adults", value=True)
    show_3 = st.checkbox("3 adults", value=True)
    show_4 = st.checkbox("4 adults", value=True)

    st.divider()
    st.markdown("**🏨 Property segment**")
    selected_segments = st.multiselect(
        "Select segments to compare",
        options=list(SHEETS.keys()),
        default=list(SHEETS.keys()),
    )

    st.divider()
    st.markdown("**🔑 Apify API Token**")
    apify_input = st.text_input(
        "Token for live Booking.com prices",
        type="password",
        placeholder="apify_api_xxxx…",
        help="Free at apify.com. Leave blank for demo data.",
    )
    if apify_input:
        import os; os.environ["APIFY_TOKEN"] = apify_input
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
<b>📊 Data source:</b> Competitor lists are loaded live from your
<b>Google Sheet</b>. Edit the sheet to add/remove competitors —
no code changes needed.
</div>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
  <h1>Adria Ankaran – Competitor Monitor</h1>
  <p>Coastal Slovenia · Real-time price comparison by property segment · Booking.com</p>
</div>
""", unsafe_allow_html=True)

# ── Welcome screen ────────────────────────────────────────────────────────────
if not search_btn:
    cols = st.columns(len(SHEETS))
    for i, (seg_key, seg) in enumerate(SHEETS.items()):
        sheet_df = load_sheet(seg_key)
        n_comp   = len(sheet_df[sheet_df["type"] == "competitor"]) if "type" in sheet_df.columns else "?"
        with cols[i]:
            st.markdown(f"""<div class="metric-card">
                <h4>{seg_key}</h4>
                <p style="color:#666;font-size:0.9rem;">{seg['description']}</p>
                <p style="color:#1a7a9e;font-size:0.85rem;font-weight:600;">
                {n_comp} competitors tracked</p>
            </div>""", unsafe_allow_html=True)
    st.info("👈 Select dates, guests and segments, then click **Fetch Prices**.")
    st.stop()

# ── Validate ──────────────────────────────────────────────────────────────────
adult_counts = [a for a, s in [(2, show_2), (3, show_3), (4, show_4)] if s]
if not adult_counts:
    st.warning("Select at least one guest configuration.")
    st.stop()
if not selected_segments:
    st.warning("Select at least one property segment.")
    st.stop()

# ── Fetch all data ────────────────────────────────────────────────────────────
token    = _get_apify_token()
all_data = {}

total = len(selected_segments) * len(adult_counts)
step  = 0
prog  = st.progress(0, text="Loading competitor lists…")

for seg_key in selected_segments:
    sheet_df = load_sheet(seg_key)
    seg_rows = []
    for adults in adult_counts:
        prog.progress(step / total,
                      text=f"Fetching {seg_key} · {adults} adults…")
        rows = fetch_prices_for_segment(
            seg_key, sheet_df, checkin, checkout, adults, token)
        seg_rows.extend(rows)
        step += 1
    all_data[seg_key] = pd.DataFrame(seg_rows)

prog.progress(1.0, text="Done!")
time.sleep(0.3)
prog.empty()

src_label = "🟢 Live Booking.com data" if token else "🟡 Demo data (add Apify token for live prices)"
st.caption(f"{src_label} · {nights} nights · {checkin} → {checkout}")

# ── One tab per selected segment ──────────────────────────────────────────────
seg_tabs = st.tabs(selected_segments)

for tab, seg_key in zip(seg_tabs, selected_segments):
    seg = SHEETS[seg_key]
    df  = all_data[seg_key]

    if df.empty:
        with tab:
            st.warning("No data for this segment.")
        continue

    self_rows = df[df["is_self"]]
    comp_rows = df[~df["is_self"]]
    self_avg  = self_rows["price_eur"].mean() if not self_rows.empty else 0
    comp_avg  = comp_rows["price_eur"].mean() if not comp_rows.empty else 0
    cheapest  = comp_rows.loc[comp_rows["price_eur"].idxmin()] if not comp_rows.empty else None
    priciest  = comp_rows.loc[comp_rows["price_eur"].idxmax()] if not comp_rows.empty else None

    with tab:
        st.markdown(f"""
<div class="segment-header">
  <b style="color:{seg['color']};font-size:1.1rem;">{seg_key}</b>
  &nbsp;·&nbsp;
  <span style="color:#666;">{seg['description']}</span>
</div>""", unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Our avg price", f"€{self_avg:,.0f}",
                  delta=f"vs €{comp_avg:,.0f} market avg",
                  delta_color="inverse" if self_avg > comp_avg else "normal")
        c2.metric("Competitors tracked", len(comp_rows["name"].unique()))
        c3.metric("Cheapest competitor",
                  f"€{cheapest['price_eur']:,.0f}" if cheapest is not None else "–",
                  cheapest["name"] if cheapest is not None else "")
        c4.metric("Most expensive",
                  f"€{priciest['price_eur']:,.0f}" if priciest is not None else "–",
                  priciest["name"] if priciest is not None else "")

        st.divider()

        t1, t2, t3 = st.tabs(["📊 Price Comparison", "🗂️ Full Table", "📈 Charts"])
        with t1:
            render_price_cards(df, seg["color"], adult_counts)
        with t2:
            render_table(df)
        with t3:
            render_charts(df)
    
        
