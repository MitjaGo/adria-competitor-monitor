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
    "Hotel Convent": {
        "csv_url":     f"{SHEET_BASE}?gid=0&single=true&output=csv",
        "color":       "#0058a3",
        "description": "Historic convent hotel · Ankaran",
    },
    "Vile brez balkona": {
        "csv_url":     f"{SHEET_BASE}?gid=1313360174&single=true&output=csv",
        "color":       "#0058a3",
        "description": "Villas without balcony · Ankaran",
    },
}

FALLBACK_DATA = {
    "Hotel Convent": [
        {"hotel": "Hotel Convent",   "type": "self",       "location": "Ankaran",  "url": "https://www.booking.com/hotel/si/convent.sl.html"},
        {"hotel": "Hotel Riviera",   "type": "competitor", "location": "Portorož", "url": "https://www.booking.com/hotel/si/lifeclass-resort-portoroz-sr.sl.html"},
        {"hotel": "Hotel Histrion",  "type": "competitor", "location": "Portorož", "url": "https://www.booking.com/hotel/si/histrion.sl.html"},
        {"hotel": "Hotel Haliaetum", "type": "competitor", "location": "Izola",    "url": "https://www.booking.com/hotel/si/haliaetum.sl.html"},
        {"hotel": "Hotel Marko",     "type": "competitor", "location": "Portorož", "url": "https://www.booking.com/hotel/si/marko.sl.html"},
        {"hotel": "Hotel Lucija",    "type": "competitor", "location": "Portorož", "url": "https://www.booking.com/hotel/si/lucija.sl.html"},
    ],
    "Vile brez balkona": [
        {"hotel": "Vile brez Balkona",          "type": "self",       "location": "Ankaran", "url": "https://www.booking.com/hotel/si/depandansa-bor.sl.html"},
        {"hotel": "Hotel Vile Park",            "type": "competitor", "location": "Portorož","url": "https://www.booking.com/hotel/si/vile-park.sl.html"},
        {"hotel": "Depandanse San Simon",       "type": "competitor", "location": "Izola",   "url": "https://www.booking.com/hotel/si/san-simon-resort-depandances.sl.html"},
        {"hotel": "Vile Krka Talasso Strunjan", "type": "competitor", "location": "Strunjan","url": "https://www.booking.com/hotel/si/vile-talaso-strunjan.sl.html"},
        {"hotel": "Hotel Barbara Fiesa",        "type": "competitor", "location": "Fiesa",   "url": "https://www.booking.com/hotel/si/barbara-fiesa.sl"},
        {"hotel": "Bio Hotel Koper",            "type": "competitor", "location": "Koper",   "url": "https://www.booking.com/hotel/si/bio.sl.html"},
    ],
}

APIFY_ACTOR = "voyager~booking-scraper"
APIFY_BASE  = "https://api.apify.com/v2"

# ── CSS — Scandinavian / IKEA style ──────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@300;400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans', 'Helvetica Neue', Arial, sans-serif;
    color: #111;
}
.main { background: #f5f5f0; }

.hero-banner {
    background: #0058a3;
    padding: 1.5rem 2rem;
    color: white;
    margin-bottom: 2rem;
    border-radius: 2px;
}
.hero-banner h1 {
    color: white; margin: 0 0 0.15rem 0;
    font-size: 1.5rem; font-weight: 700; letter-spacing: -0.01em;
}
.hero-banner p { margin: 0; opacity: 0.7; font-size: 0.85rem; font-weight: 300; }

.metric-card {
    background: white;
    padding: 1.4rem 1.6rem;
    border: 1px solid #e0e0e0;
    border-top: 3px solid #0058a3;
    border-radius: 2px;
}
.metric-card h4 { margin: 0 0 0.3rem 0; font-size: 0.95rem; font-weight: 700; letter-spacing: 0.01em; }
.metric-card p  { margin: 0; font-size: 0.82rem; color: #555; }
.metric-card .n-comp { font-size: 0.8rem; color: #0058a3; font-weight: 600; margin-top: 0.5rem; }

.segment-header {
    padding: 0.3rem 0 0.7rem 0;
    margin-bottom: 0.8rem;
    border-bottom: 2px solid #111;
}
.segment-header span { font-size: 0.8rem; color: #666; font-weight: 300; }

[data-testid="metric-container"] {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 2px;
    padding: 1rem 1.2rem;
}

.tag {
    display: inline-block; padding: 1px 7px;
    font-size: 0.65rem; font-weight: 700;
    letter-spacing: 0.07em; text-transform: uppercase;
    border-radius: 1px;
}
.tag-self    { background: #ffd600; color: #111; }
.tag-cheaper { background: #d4edda; color: #155724; }
.tag-pricier { background: #f8d7da; color: #721c24; }
.tag-similar { background: #ebebeb; color: #444; }

.stButton > button {
    background: #0058a3 !important;
    color: white !important; border: none !important; border-radius: 2px !important;
    font-weight: 700 !important; padding: 0.65rem 1.5rem !important;
    font-size: 0.88rem !important; width: 100% !important;
    letter-spacing: 0.05em !important; text-transform: uppercase !important;
}
.stButton > button:hover { background: #004a8c !important; }

.stDownloadButton > button {
    background: white !important; color: #0058a3 !important;
    border: 2px solid #0058a3 !important; border-radius: 2px !important;
    font-weight: 700 !important; font-size: 0.8rem !important;
    letter-spacing: 0.05em !important; text-transform: uppercase !important;
}
.stDownloadButton > button:hover { background: #eef4fb !important; }

.info-box {
    background: #fff9e0; border: 1px solid #ffd600;
    padding: 0.75rem 1rem; font-size: 0.8rem; color: #333; border-radius: 2px;
}

.stTabs [data-baseweb="tab-list"] { gap: 0; border-bottom: 2px solid #111; }
.stTabs [data-baseweb="tab"] {
    border-radius: 0; font-weight: 600; font-size: 0.8rem;
    letter-spacing: 0.05em; text-transform: uppercase;
    padding: 0.5rem 1.2rem; color: #777;
    border: none; background: transparent;
}
.stTabs [aria-selected="true"] { color: #111; border-bottom: 3px solid #0058a3; }

hr { border-color: #e0e0e0; }
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
                "meal_plan": "Najnižja cena",
                "source":    "apify_live",
            })
    return out


def apify_fetch_all(all_urls: list, checkin: date, checkout: date,
                    adult_counts: list, token: str, progress_cb=None) -> dict:
    nights  = (checkout - checkin).days or 1
    results = {}
    for i, adults in enumerate(adult_counts):
        if progress_cb:
            progress_cb(i / len(adult_counts),
                        f"Iskanje: {adults} odrasli · {len(all_urls)} hotelov…")
        try:
            results[adults] = _apify_single_run(all_urls, checkin, checkout,
                                                adults, nights, token)
        except Exception as e:
            st.warning(f"Napaka za {adults} odrasle: {e}")
            results[adults] = {}
    return results


def assemble_segment(seg_key: str, sheet_df: pd.DataFrame,
                     checkin: date, checkout: date,
                     adults: int, batch: dict) -> list:
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
                    "name": name, "location": location,
                    "is_self": is_self, "adults": adults,
                    "nights": nights, "booking_url": url,
                    "segment": seg_key, **v,
                })
        else:
            results.append({
                "name": name, "location": location,
                "is_self": is_self, "adults": adults,
                "nights": nights, "booking_url": url,
                "segment": seg_key, "price_eur": None,
                "per_night": None, "stars": 0, "rating": 0.0,
                "meal_plan": "Ni podatka", "source": "error",
            })
    return results


# ── UI helpers ────────────────────────────────────────────────────────────────
def stars_html(n):
    return "★" * int(n) if n else "–"


def render_table(df: pd.DataFrame, key: str = "default"):
    disp = df[["name", "location", "stars", "rating", "meal_plan",
               "adults", "nights", "price_eur", "per_night",
               "is_self", "booking_url"]].copy()
    disp.columns = ["Hotel", "Kraj", "Zvezde", "Ocena", "Vrsta ponudbe",
                    "Odrasli", "Noči", "Skupaj €", "Na noč €",
                    "Naš hotel", "Link"]
    disp = disp.sort_values(["Odrasli", "Hotel", "Skupaj €"])
    disp["Zvezde"]    = disp["Zvezde"].apply(stars_html)
    disp["Naš hotel"] = disp["Naš hotel"].apply(lambda x: "✓" if x else "")
    st.dataframe(
        disp,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Skupaj €": st.column_config.NumberColumn(format="€%.0f"),
            "Na noč €": st.column_config.NumberColumn(format="€%.0f"),
            "Ocena":    st.column_config.NumberColumn(format="%.1f"),
            "Link":     st.column_config.LinkColumn("Booking.com"),
        },
    )
    csv = disp.to_csv(index=False).encode("utf-8")
    st.download_button(
        "↓ Prenesi CSV",
        csv,
        f"konkurenti_{key}.csv",
        "text/csv",
        key=f"download_csv_{key}",
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Nastavitve iskanja")
    st.divider()

    today       = date.today()
    default_in  = today + timedelta(days=14)
    default_out = default_in + timedelta(days=7)

    checkin  = st.date_input("Datum prihoda",  value=default_in,  min_value=today)
    checkout = st.date_input("Datum odhoda",   value=default_out,
                             min_value=checkin + timedelta(days=1))
    nights   = (checkout - checkin).days
    st.caption(f"{nights} {'noč' if nights == 1 else 'noči'}")

    st.divider()
    st.markdown("**Število gostov**")
    show_2 = st.checkbox("2 odrasla", value=True)
    show_3 = st.checkbox("3 odrasli", value=True)
    show_4 = st.checkbox("4 odrasli", value=True)

    st.divider()
    st.markdown("**Segment**")
    selected_segments = st.multiselect(
        "Prikaži segmente",
        options=list(SHEETS.keys()),
        default=list(SHEETS.keys()),
    )

    st.divider()
    search_btn = st.button("Poišči cene", use_container_width=True)

    st.markdown("""
<div class="info-box">
<b>Podatki:</b> Seznam konkurentov se nalaga iz tvojega
<b>Google Sheeta</b>. Dodaj hotel v sheet — app se samodejno posodobi.
</div>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
  <h1>Adria Ankaran — Monitor konkurentov</h1>
  <p>Slovenska obala · Primerjava cen · Booking.com</p>
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
                <p>{seg['description']}</p>
                <p class="n-comp">{n_comp} konkurentov</p>
            </div>""", unsafe_allow_html=True)
    st.info("Izberi datume, goste in segment, nato klikni **Poišči cene**.")
    st.stop()

# ── Validacija ────────────────────────────────────────────────────────────────
adult_counts = [a for a, s in [(2, show_2), (3, show_3), (4, show_4)] if s]
if not adult_counts:
    st.warning("Izberi vsaj eno število gostov.")
    st.stop()
if not selected_segments:
    st.warning("Izberi vsaj en segment.")
    st.stop()

# ── Fetch ─────────────────────────────────────────────────────────────────────
token    = _get_apify_token()
all_data = {}
prog     = st.progress(0, text="Nalagam seznam hotelov…")

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
st.caption(f"{n_hotels} hotelov · {str(n_runs) + ' Apify runs' if token else 'ni Apify tokena'}")

mega_batch: dict = {}
if token and all_urls:
    def _progress(pct, msg):
        prog.progress(pct * 0.85, text=msg)
    mega_batch = apify_fetch_all(all_urls, checkin, checkout,
                                 adult_counts, token, _progress)

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

prog.progress(1.0, text="Končano.")
time.sleep(0.3)
prog.empty()

src = "Živi podatki · Booking.com" if token else "Ni Apify tokena — dodaj ga v Streamlit Secrets"
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
    best = (df_prices.groupby(["name", "is_self", "adults"])["price_eur"]
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
  <b style="font-size:1.05rem;">{seg_key}</b>
  &nbsp;&nbsp;<span>{seg['description']}</span>
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
