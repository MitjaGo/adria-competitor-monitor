import streamlit as st
import pandas as pd
from datetime import date, timedelta
import time
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
        "csv_url":     f"{SHEET_BASE}?gid=0&single=true&output=csv",
        "color":       "#8e44ad",
        "description": "Historic convent hotel · Ankaran",
    },
    "🏡 Vile brez balkona": {
        "csv_url":     f"{SHEET_BASE}?gid=1313360174&single=true&output=csv",
        "color":       "#27ae60",
        "description": "Villas without balcony · Ankaran",
    },
}

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
        {"hotel": "Vile brez Balkona",          "type": "self",       "location": "Ankaran", "url": "https://www.booking.com/hotel/si/depandansa-bor.sl.html"},
        {"hotel": "Hotel Vile Park",            "type": "competitor", "location": "Portorož","url": "https://www.booking.com/hotel/si/vile-park.sl.html"},
        {"hotel": "Depandanse San Simon",       "type": "competitor", "location": "Izola",   "url": "https://www.booking.com/hotel/si/san-simon-resort-depandances.sl.html"},
        {"hotel": "Vile Krka Talasso Strunjan", "type": "competitor", "location": "Strunjan","url": "https://www.booking.com/hotel/si/vile-talaso-strunjan.sl.html"},
        {"hotel": "Hotel Barbara Fiesa",        "type": "competitor", "location": "Fiesa",   "url": "https://www.booking.com/hotel/si/barbara-fiesa.sl"},
        {"hotel": "Bio Hotel Koper",            "type": "competitor", "location": "Koper",   "url": "https://www.booking.com/hotel/si/bio.sl.html"},
    ],
}

MEAL_PLANS = [
    {"label": "🛏️ Room only",      "key": "room_only", "multiplier": 1.00},
    {"label": "🍳 Bed & Breakfast", "key": "bb",        "multiplier": 1.18},
    {"label": "🍽️ Half Board",     "key": "hb",        "multiplier": 1.38},
    {"label": "🍴 Full Board",      "key": "fb",        "multiplier": 1.55},
]

APIFY_ACTOR = "voyager~booking-scraper"
APIFY_BASE  = "https://api.apify.com/v2"

# ── CSS ───────────────────────────────────────────────────────────────────────
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
.meal-pill {
    display: inline-block; margin: 2px 4px 2px 0; padding: 3px 10px;
    border-radius: 12px; font-size: 0.75rem; background: #f0f4f8; color: #444;
    border: 1px solid #dde3ea;
}
.meal-pill.cheapest { background: #e8f5e9; border-color: #a5d6a7; color: #2e7d32; font-weight: 600; }
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


# ── Helpers ───────────────────────────────────────────────────────────────────
def fix_encoding(s: str) -> str:
    try:
        return s.encode("latin-1").decode("utf-8")
    except Exception:
        return s


def _get_apify_token():
    import os
    try:
        return st.secrets.get("APIFY_TOKEN") or os.getenv("APIFY_TOKEN")
    except Exception:
        return os.getenv("APIFY_TOKEN")


@st.cache_data(ttl=300)
def load_sheet(seg_key: str) -> pd.DataFrame:
    try:
        resp = requests.get(SHEETS[seg_key]["csv_url"], timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        df.columns = [c.strip().lower() for c in df.columns]
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].astype(str).apply(fix_encoding)
        return df
    except Exception:
        return pd.DataFrame(FALLBACK_DATA.get(seg_key, []))


# ── Apify REST API ────────────────────────────────────────────────────────────
def _normalize_meal(meal: str) -> str:
    m = meal.lower()
    if "breakfast" in m or "b&b" in m:
        return "🍳 Bed & Breakfast"
    elif "half" in m:
        return "🍽️ Half Board"
    elif "full" in m or "all inclusive" in m:
        return "🍴 Full Board"
    return "🛏️ Room only"


def _match_url(h_url: str, urls: list) -> str | None:
    for u in urls:
        if "/hotel/" in u:
            slug = u.split("/hotel/")[1].split(".")[0]
            if slug and slug in h_url:
                return u
    return None


def _run_apify(run_input: dict, token: str, max_items: int = 20) -> list:
    hdrs = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    r = requests.post(f"{APIFY_BASE}/acts/{APIFY_ACTOR}/runs",
                      json=run_input, headers=hdrs, timeout=30)
    r.raise_for_status()
    data       = r.json()["data"]
    run_id     = data["id"]
    dataset_id = data["defaultDatasetId"]

    for _ in range(60):
        time.sleep(5)
        status = requests.get(f"{APIFY_BASE}/actor-runs/{run_id}",
                              headers=hdrs, timeout=15).json()["data"]["status"]
        if status == "SUCCEEDED":
            break
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            return []

    raw = requests.get(f"{APIFY_BASE}/datasets/{dataset_id}/items",
                       headers=hdrs,
                       params={"format": "json", "clean": "true", "limit": max_items},
                       timeout=20).json()

    return raw if isinstance(raw, list) else []


def _extract_price(h: dict) -> float:
    price = 0.0
    for f in ["price", "minPrice", "lowestPrice", "totalPrice", "priceFrom"]:
        val = h.get(f)
        if val:
            try:
                price = float(str(val).replace(",","").replace("€","").replace("EUR","").strip())
                if price > 0:
                    break
            except Exception:
                pass
    return price


def _apify_single_run(urls: list, checkin: date, checkout: date,
                      adults: int, nights: int, token: str) -> dict:
    out: dict = {}

    run_input = {
        "startUrls": [{"url": u} for u in urls if u.startswith("http")],
        "checkIn":   checkin.strftime("%Y-%m-%d"),
        "checkOut":  checkout.strftime("%Y-%m-%d"),
        "adults":    adults,
        "children":  0,
        "rooms":     1,
        "currency":  "EUR",
        "language":  "en-gb",
        "maxItems":  len(urls) * 5,
        "extractAdditionalHotelData": False,
    }

    raw = _run_apify(run_input, token, max_items=len(urls) * 10)

    for h in raw:
        if not isinstance(h, dict):
            continue

        h_url  = h.get("url") or ""
        price  = _extract_price(h)
        stars  = int(h.get("stars") or h.get("starRating") or 0)
        rating = float(h.get("reviewScore") or h.get("rating") or 0)

        if price == 0:
            continue

        match_url = _match_url(h_url, urls)
        if not match_url:
            continue

        if match_url not in out:
            out[match_url] = []
        if not out[match_url]:
            out[match_url].append({
                "price_eur": price,
                "per_night": round(price / nights, 2),
                "stars":     stars,
                "rating":    rating,
                "meal_plan": "🛏️ Najnižja cena",
                "source":    "apify_live",
            })

    return out


def apify_fetch_all(all_urls: list, checkin: date, checkout: date,
                    adult_counts: list, token: str,
                    progress_cb=None) -> dict:
    nights  = (checkout - checkin).days or 1
    results = {}

    for i, adults in enumerate(adult_counts):
        if progress_cb:
            progress_cb(i / len(adult_counts),
                        f"🔍 Apify run {i+1}/{len(adult_counts)} · {adults} odrasli · {len(all_urls)} hotelov…")
        try:
            results[adults] = _apify_single_run(all_urls, checkin, checkout,
                                                adults, nights, token)
        except Exception as e:
            st.warning(f"⚠️ Apify napaka za {adults} odrasle: {e}")
            results[adults] = {}

    return results


def assemble_segment(seg_key: str, sheet_df: pd.DataFrame,
                     checkin: date, checkout: date,
                     adults: int,
                     batch: dict) -> list:
    nights  = (checkout - checkin).days or 1
    results = []

    for _, row in sheet_df.iterrows():
        name     = fix_encoding(str(row.get("hotel", "")).strip())
        is_self  = str(row.get("type", "")).strip().lower() == "self"
        location = fix_encoding(str(row.get("location", "")).strip())
        url      = str(row.get("url", "")).strip()

        variants = batch.get(url, [])
        if variants:
            for v in variants:
                results.append({
                    "name":        name,
                    "location":    location,
                    "is_self":     is_self,
                    "adults":      adults,
                    "nights":      nights,
                    "booking_url": url,
                    "segment":     seg_key,
                    **v,
                })
        else:
            results.append({
                "name":        name,
                "location":    location,
                "is_self":     is_self,
                "adults":      adults,
                "nights":      nights,
                "booking_url": url,
                "segment":     seg_key,
                "price_eur":   None,
                "per_night":   None,
                "stars":       0,
                "rating":      0.0,
                "meal_plan":   "❌ Ni podatka",
                "source":      "error",
            })

    return results


# ── UI helpers ────────────────────────────────────────────────────────────────
def stars_html(n):
    return "⭐" * int(n) if n else "–"


def render_cards(df: pd.DataFrame, seg_color: str, adult_counts: list):
    for adults in adult_counts:
        sub = df[df["adults"] == adults]
        if sub.empty:
            continue
        st.markdown(f"### 👥 {adults} odrasli")

        sub_ok  = sub[sub["price_eur"].notna() & (sub["price_eur"] > 0)]
        sub_err = sub[sub["price_eur"].isna()  | (sub["price_eur"] == 0)]

        for _, erow in sub_err.drop_duplicates("name").iterrows():
            url  = erow.get("booking_url", "")
            link = f'<a href="{url}" target="_blank" style="font-size:0.78rem;color:#1a7a9e;">🔗 Booking.com</a>' if url else ""
            st.markdown(f"""
<div class="property-card" style="border-top-color:#e74c3c;opacity:0.7;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div>
      <b>{erow["name"]}</b> &nbsp;
      <span style="font-size:0.75rem;background:#fde8e0;color:#c0392b;padding:2px 8px;border-radius:10px;">❌ Ni cene</span><br>
      <span style="color:#888;font-size:0.82rem;">📍 {erow["location"]} &nbsp;·&nbsp; {link}</span>
    </div>
    <span style="color:#aaa;font-size:0.85rem;">ni razpoložljivo</span>
  </div>
</div>""", unsafe_allow_html=True)

        if sub_ok.empty:
            continue

        best = sub_ok.groupby("name")["price_eur"].min().reset_index()
        best.columns = ["name", "min_price"]
        sub_ok = sub_ok.merge(best, on="name")

        hotels   = sub_ok.sort_values("min_price")["name"].unique()
        self_ref = None
        sr = sub_ok[sub_ok["is_self"]]
        if not sr.empty:
            self_ref = float(sr["min_price"].iloc[0])

        for hotel in hotels:
            hrows    = sub_ok[sub_ok["name"] == hotel]
            base     = hrows.iloc[0]
            is_self  = bool(base["is_self"])
            min_p    = float(base["min_price"])

            if is_self:
                cls = "self_prop"
                tag = '<span class="tag tag-self">NAŠ HOTEL</span>'
            elif self_ref and min_p < self_ref * 0.95:
                cls = "cheaper"
                tag = f'<span class="tag tag-cheaper">€{self_ref - min_p:.0f} cenejši</span>'
            elif self_ref and min_p > self_ref * 1.05:
                cls = "pricier"
                tag = f'<span class="tag tag-pricier">€{min_p - self_ref:.0f} dražji</span>'
            else:
                cls = ""
                tag = '<span class="tag tag-similar">podobna cena</span>'

            bar_pct   = min(100, int(min_p / (sub_ok["min_price"].max() or 1) * 100))
            bar_color = seg_color if is_self else "#1a7a9e"
            url       = base.get("booking_url", "")
            link      = f'<a href="{url}" target="_blank" style="font-size:0.78rem;color:#1a7a9e;">🔗 Booking.com</a>' if url else ""
            src_icon  = "🟢" if base.get("source") == "apify_live" else "🟡"

            st.markdown(f"""
<div class="property-card {cls}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div style="flex:1;">
      <b style="font-size:1.05rem;">{hotel}</b> {tag} {src_icon}<br>
      <span style="color:#666;font-size:0.85rem;">
        {stars_html(base['stars'])} &nbsp;·&nbsp;
        ⭐ {base['rating']} &nbsp;·&nbsp;
        📍 {base['location']} &nbsp;·&nbsp; {link}
      </span>
    </div>
    <div style="text-align:right;min-width:110px;">
      <span style="font-size:0.75rem;color:#888;">najnižja cena</span><br>
      <span style="font-size:1.5rem;font-weight:700;color:#0a4f6e;">€{min_p:,.0f}</span><br>
      <span style="color:#888;font-size:0.8rem;">€{hrows['per_night'].min():,.0f} / noč</span>
    </div>
  </div>
  <div style="margin-top:0.7rem;background:#eee;border-radius:4px;height:6px;">
    <div style="width:{bar_pct}%;background:{bar_color};height:6px;border-radius:4px;"></div>
  </div>
</div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)


def render_table(df: pd.DataFrame, key: str = "default"):
    """Prikaže tabelo in CSV gumb — key mora biti unikaten za vsak segment."""
    disp = df[["name", "location", "stars", "rating", "meal_plan",
               "adults", "nights", "price_eur", "per_night",
               "is_self", "booking_url"]].copy()
    disp.columns = ["Hotel", "Kraj", "Zvezde", "Ocena", "Vrsta ponudbe",
                    "Odrasli", "Noči", "Skupaj €", "Na noč €",
                    "Naš hotel", "Link"]
    disp = disp.sort_values(["Odrasli", "Hotel", "Skupaj €"])
    disp["Zvezde"]    = disp["Zvezde"].apply(stars_html)
    disp["Naš hotel"] = disp["Naš hotel"].apply(lambda x: "✅" if x else "")
    st.dataframe(disp, use_container_width=True, hide_index=True,
                 column_config={
                     "Skupaj €":   st.column_config.NumberColumn(format="€%.0f"),
                     "Na noč €":   st.column_config.NumberColumn(format="€%.0f"),
                     "Ocena":      st.column_config.NumberColumn(format="%.1f"),
                     "Link":       st.column_config.LinkColumn("Booking.com"),
                 })
    csv = disp.to_csv(index=False).encode("utf-8")
    # ↓ key mora biti unikaten — drugače Streamlit vrže DuplicateElementId
    st.download_button(
        "⬇️ Prenesi CSV",
        csv,
        f"konkurenti_{key}.csv",
        "text/csv",
        key=f"download_csv_{key}",
    )


def render_charts(df: pd.DataFrame):
    import altair as alt
    chart_df = (df.groupby(["name", "adults", "is_self", "location"])["price_eur"]
                  .min().reset_index())
    chart_df["label"] = chart_df["adults"].astype(str) + " odrasli"
    chart_df["tip"]   = chart_df["is_self"].apply(
        lambda x: "Naš hotel" if x else "Konkurent")

    st.markdown("#### Najcenejša cena po hotelu")
    bar = (
        alt.Chart(chart_df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("name:N", sort="-y", title=None,
                    axis=alt.Axis(labelAngle=-40, labelLimit=180)),
            y=alt.Y("price_eur:Q", title="Skupna cena (€)"),
            color=alt.Color("tip:N",
                scale=alt.Scale(domain=["Naš hotel", "Konkurent"],
                                range=["#e8623a", "#1a7a9e"]),
                legend=alt.Legend(title="")),
            column=alt.Column("label:N", title="",
                              header=alt.Header(labelFontSize=13)),
            tooltip=["name", "location", "price_eur", "adults"],
        ).properties(height=320)
    )
    st.altair_chart(bar, use_container_width=False)

    st.markdown("#### Primerjava po vrsti ponudbe")
    hotels = sorted(df["name"].unique().tolist())
    sel    = st.selectbox("Izberi hotel", hotels)
    h_df   = df[df["name"] == sel].copy()
    h_df["label"] = h_df["adults"].astype(str) + " odrasli"

    meal_bar = (
        alt.Chart(h_df)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("meal_plan:N", title=None, axis=alt.Axis(labelAngle=-20)),
            y=alt.Y("price_eur:Q", title="Skupna cena (€)"),
            color=alt.Color("meal_plan:N", legend=None),
            column=alt.Column("label:N", title="",
                              header=alt.Header(labelFontSize=13)),
            tooltip=["meal_plan", "price_eur", "per_night", "adults"],
        ).properties(height=260, width=160)
    )
    st.altair_chart(meal_bar, use_container_width=False)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌊 Nastavitve iskanja")
    st.divider()

    today       = date.today()
    default_in  = today + timedelta(days=14)
    default_out = default_in + timedelta(days=7)

    checkin  = st.date_input("Datum prihoda",  value=default_in,  min_value=today)
    checkout = st.date_input("Datum odhoda",   value=default_out,
                             min_value=checkin + timedelta(days=1))
    nights   = (checkout - checkin).days
    st.caption(f"📅 {nights} {'noč' if nights == 1 else 'noči'}")

    st.divider()
    st.markdown("**Število gostov**")
    show_2 = st.checkbox("2 odrasla", value=True)
    show_3 = st.checkbox("3 odrasli", value=True)
    show_4 = st.checkbox("4 odrasli", value=True)

    st.divider()
    st.markdown("**🏨 Segment**")
    selected_segments = st.multiselect(
        "Prikaži segmente",
        options=list(SHEETS.keys()),
        default=list(SHEETS.keys()),
    )

    st.divider()
    search_btn = st.button("🔍 Poišči cene", use_container_width=True)

    st.markdown("""
<div class="info-box">
<b>📊 Podatki:</b> Seznam konkurentov se nalaga iz
tvojega <b>Google Sheeta</b>. Dodaj hotel v sheet —
app se samodejno posodobi.
</div>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
  <h1>Adria Ankaran – Monitor konkurentov</h1>
  <p>Slovenska obala · Primerjava cen po segmentih in vrsti ponudbe · Booking.com</p>
</div>
""", unsafe_allow_html=True)

# ── Welcome ───────────────────────────────────────────────────────────────────
if not search_btn:
    cols = st.columns(len(SHEETS))
    for i, (seg_key, seg) in enumerate(SHEETS.items()):
        sheet_df = load_sheet(seg_key)
        n_comp   = len(sheet_df[sheet_df["type"] == "competitor"]) \
                   if "type" in sheet_df.columns else "?"
        with cols[i]:
            st.markdown(f"""<div class="metric-card">
                <h4>{seg_key}</h4>
                <p style="color:#666;font-size:0.9rem;">{seg['description']}</p>
                <p style="color:#1a7a9e;font-size:0.85rem;font-weight:600;">
                {n_comp} konkurentov</p>
            </div>""", unsafe_allow_html=True)
    st.info("👈 Izberi datume, goste in segment, nato klikni **Poišči cene**.")
    st.stop()

# ── Validacija ────────────────────────────────────────────────────────────────
adult_counts = [a for a, s in [(2, show_2), (3, show_3), (4, show_4)] if s]
if not adult_counts:
    st.warning("Izberi vsaj eno število gostov.")
    st.stop()
if not selected_segments:
    st.warning("Izberi vsaj en segment.")
    st.stop()

# ── Fetch — MEGA BATCH ────────────────────────────────────────────────────────
token    = _get_apify_token()
all_data = {}
prog     = st.progress(0, text="Nalagam seznam hotelov…")

# 1 — Naložimo vse sheet-e in zberemo unikatne URL-je
sheets_data = {}
all_urls    = []
for seg_key in selected_segments:
    df_sheet = load_sheet(seg_key)
    sheets_data[seg_key] = df_sheet
    for _, row in df_sheet.iterrows():
        u = str(row.get("url", "")).strip()
        if u.startswith("http") and u not in all_urls:
            all_urls.append(u)

n_hotels = len(all_urls)
n_runs   = len(adult_counts) if token else 0

st.caption(f"🏨 {n_hotels} unikatnih hotelov · {'🔴 ' + str(n_runs) + ' Apify runs' if token else '🟡 Demo način'}")

# 2 — En set runov za vse segmente skupaj (1 run na število gostov)
mega_batch: dict = {}
if token and all_urls:
    def _progress(pct, msg):
        prog.progress(pct * 0.85, text=msg)

    mega_batch = apify_fetch_all(all_urls, checkin, checkout,
                                 adult_counts, token, _progress)

# 3 — Sestavi podatke po segmentih
prog.progress(0.9, text="Sestavljam rezultate…")
for seg_key in selected_segments:
    rows = []
    for adults in adult_counts:
        batch = mega_batch.get(adults, {})
        rows.extend(assemble_segment(
            seg_key, sheets_data[seg_key],
            checkin, checkout, adults, batch
        ))
    all_data[seg_key] = pd.DataFrame(rows)

prog.progress(1.0, text="Končano!")
time.sleep(0.3)
prog.empty()

src = "🟢 Živi podatki z Booking.com" if token else "🔴 Ni Apify tokena — dodaj ga v Streamlit Secrets"
st.caption(f"{src} · {nights} noči · {checkin} → {checkout}")

# ── Tabs ──────────────────────────────────────────────────────────────────────
seg_tabs = st.tabs(selected_segments)

for tab, seg_key in zip(seg_tabs, selected_segments):
    seg = SHEETS[seg_key]
    df  = all_data[seg_key]

    if df.empty:
        with tab:
            st.warning("Ni podatkov za ta segment.")
        continue

    df_prices = df[df["price_eur"].notna() & (df["price_eur"] > 0)]
    best      = (df_prices.groupby(["name", "is_self", "adults"])["price_eur"]
                           .min().reset_index()
                 if not df_prices.empty
                 else pd.DataFrame(columns=["name", "is_self", "adults", "price_eur"]))
    self_rows = best[best["is_self"]]
    comp_rows = best[~best["is_self"]]
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
        c1.metric("Naša povp. cena", f"€{self_avg:,.0f}",
                  delta=f"vs €{comp_avg:,.0f} trg",
                  delta_color="inverse" if self_avg > comp_avg else "normal")
        c2.metric("Konkurenti", len(comp_rows["name"].unique()))
        c3.metric("Najcenejši konkurent",
                  f"€{cheapest['price_eur']:,.0f}" if cheapest is not None else "–",
                  cheapest["name"] if cheapest is not None else "")
        c4.metric("Najdražji konkurent",
                  f"€{priciest['price_eur']:,.0f}" if priciest is not None else "–",
                  priciest["name"] if priciest is not None else "")

        st.divider()
        render_table(df, key=seg_key)
