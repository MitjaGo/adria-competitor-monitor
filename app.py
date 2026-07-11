import streamlit as st
import pandas as pd
from datetime import date, timedelta
from collections import defaultdict
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
        "description": "Historic convent hotel · Ankaran",
        "adults":      2,
    },
    "Vile brez balkona": {
        "csv_url":     f"{SHEET_BASE}?gid=1313360174&single=true&output=csv",
        "description": "Villas without balcony · Ankaran",
        "adults":      2,
    },
    "Vile z balkonom": {
        "csv_url":     f"{SHEET_BASE}?gid=996668368&single=true&output=csv",
        "description": "Villas with balcony · Ankaran",
        "adults":      2,
    },
    "Olive Suites": {
        "csv_url":     f"{SHEET_BASE}?gid=91411090&single=true&output=csv",
        "description": "Olive Suites · Ankaran",
        "adults":      2,
    },
    "Premium Mobile Homes": {
        "csv_url":     f"{SHEET_BASE}?gid=1775050597&single=true&output=csv",
        "description": "Premium Mobile Homes · Ankaran",
        "adults":      4,
    },
    "Adria Apartments": {
        "csv_url":     f"{SHEET_BASE}?gid=1575590147&single=true&output=csv",
        "description": "Adria Apartments · Ankaran",
        "adults":      4,
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
        {"hotel": "Vile brez Balkona",          "type": "self",       "location": "Ankaran",  "url": "https://www.booking.com/hotel/si/depandansa-bor.sl.html"},
        {"hotel": "Hotel Vile Park",            "type": "competitor", "location": "Portorož", "url": "https://www.booking.com/hotel/si/vile-park.sl.html"},
        {"hotel": "Depandanse San Simon",       "type": "competitor", "location": "Izola",    "url": "https://www.booking.com/hotel/si/san-simon-resort-depandances.sl.html"},
        {"hotel": "Vile Krka Talasso Strunjan", "type": "competitor", "location": "Strunjan", "url": "https://www.booking.com/hotel/si/vile-talaso-strunjan.sl.html"},
        {"hotel": "Hotel Barbara Fiesa",        "type": "competitor", "location": "Fiesa",    "url": "https://www.booking.com/hotel/si/barbara-fiesa.sl"},
        {"hotel": "Bio Hotel Koper",            "type": "competitor", "location": "Koper",    "url": "https://www.booking.com/hotel/si/bio.sl.html"},
    ],
    "Vile z balkonom":      [],
    "Olive Suites":         [],
    "Premium Mobile Homes": [],
    "Adria Apartments":     [],
}

APIFY_ACTOR = "voyager~booking-scraper"
APIFY_BASE  = "https://api.apify.com/v2"

# ── CSS ───────────────────────────────────────────────────────────────────────
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
.metric-card h4 { margin: 0 0 0.3rem 0; font-size: 0.95rem; font-weight: 700; }
.metric-card p  { margin: 0; font-size: 0.82rem; color: #555; }
.metric-card .n-comp { font-size: 0.8rem; color: #0058a3; font-weight: 600; margin-top: 0.5rem; }
.metric-card .adults-badge {
    display: inline-block; margin-top: 0.4rem;
    background: #f0f0f0; color: #333;
    font-size: 0.72rem; font-weight: 600;
    padding: 2px 8px; border-radius: 2px; letter-spacing: 0.04em;
}

.segment-header {
    padding: 0.3rem 0 0.7rem 0;
    margin-bottom: 0.8rem;
    border-bottom: 2px solid #111;
}
.segment-header span { font-size: 0.8rem; color: #666; font-weight: 300; }
.adults-pill {
    display: inline-block;
    background: #0058a3; color: white;
    font-size: 0.7rem; font-weight: 700;
    padding: 2px 9px; border-radius: 2px;
    letter-spacing: 0.05em; text-transform: uppercase;
    vertical-align: middle; margin-left: 0.5rem;
}

[data-testid="metric-container"] {
    background: white; border: 1px solid #e0e0e0;
    border-radius: 2px; padding: 1rem 1.2rem;
}

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
    # Najprej poskusi Streamlit secrets (Streamlit Cloud)
    try:
        token = st.secrets["APIFY_TOKEN"]
        if token:
            return token
    except Exception:
        pass
    # Fallback: environment variable (lokalno)
    return os.getenv("APIFY_TOKEN")


@st.cache_data(ttl=300)
def load_sheet(seg_key: str) -> pd.DataFrame:
    try:
        resp = requests.get(SHEETS[seg_key]["csv_url"], timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        df.columns = [c.strip().lower() for c in df.columns]
        for col in df.select_dtypes(include=["object", "string"]).columns:
            df[col] = df[col].astype(str).apply(fix_encoding)
        return df
    except Exception:
        return pd.DataFrame(FALLBACK_DATA.get(seg_key, []))


# ── Apify ─────────────────────────────────────────────────────────────────────
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
        status = requests.get(
            f"{APIFY_BASE}/actor-runs/{run_id}", headers=hdrs, timeout=15
        ).json()["data"]["status"]
        if status == "SUCCEEDED":
            break
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            return []
    raw = requests.get(
        f"{APIFY_BASE}/datasets/{dataset_id}/items",
        headers=hdrs,
        params={"format": "json", "clean": "true", "limit": max_items},
        timeout=20,
    ).json()
    return raw if isinstance(raw, list) else []


def _extract_price(h: dict) -> float:
    for f in ["price", "minPrice", "lowestPrice", "totalPrice", "priceFrom"]:
        val = h.get(f)
        if val:
            try:
                p = float(str(val).replace(",", "").replace("€", "").replace("EUR", "").strip())
                if p > 0:
                    return p
            except Exception:
                pass
    return 0.0


def _apify_single_run(urls: list, checkin: date, checkout: date,
                      adults: int, nights: int, token: str) -> dict:
    out: dict = {}

    run_input = {
        "startUrls":                [{"url": u} for u in urls if u.startswith("http")],
        "checkIn":                  checkin.strftime("%Y-%m-%d"),
        "checkOut":                 checkout.strftime("%Y-%m-%d"),
        "adults":                   adults,
        "children":                 0,
        "currency":                 "EUR",
        "language":                 "en-gb",
        "maxItems":                 len(urls) * 3,
        "minScore":                 "1",
        "minMaxPrice":              "0-999999",
        "flexWindow":               "0",
        "sortBy":                   "price",
        "extractAdditionalHotelData": True,
    }

    raw = _run_apify(run_input, token, max_items=len(urls) * 5)

    for h in raw:
        if not isinstance(h, dict):
            continue
        h_url  = h.get("url") or h.get("bookingUrl") or ""
        price  = _extract_price(h)
        stars  = int(h.get("stars") or h.get("starRating") or 0)
        rating = float(h.get("reviewScore") or h.get("rating") or 0)
        if price == 0:
            continue
        matched = _match_url(h_url, urls)
        if not matched:
            continue
        if matched not in out:
            out[matched] = [{
                "price_eur": price,
                "per_night": round(price / nights, 2),
                "stars":     stars,
                "rating":    rating,
                "meal_plan": "Najnižja cena",
                "source":    "apify_live",
            }]
    return out


def apify_fetch_all(urls_per_adults: dict, checkin: date, checkout: date,
                    token: str, progress_cb=None) -> dict:
    """En Apify run na unikaten adults_count. Vrne {adults -> {url -> [...]}}"""
    nights  = (checkout - checkin).days or 1
    results = {}
    items   = list(urls_per_adults.items())
    for i, (adults, urls) in enumerate(items):
        if not urls:
            results[adults] = {}
            continue
        if progress_cb:
            progress_cb(i / len(items), f"Iskanje: {adults} odrasli · {len(urls)} hotelov…")
        try:
            results[adults] = _apify_single_run(urls, checkin, checkout, adults, nights, token)
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
                    "name": name, "location": location, "is_self": is_self,
                    "adults": adults, "nights": nights,
                    "booking_url": url, "segment": seg_key, **v,
                })
        else:
            results.append({
                "name": name, "location": location, "is_self": is_self,
                "adults": adults, "nights": nights,
                "booking_url": url, "segment": seg_key,
                "price_eur": None, "per_night": None,
                "stars": 0, "rating": 0.0,
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
                    "Odrasli", "Noči", "Skupaj €", "Na noč €", "Naš hotel", "Link"]
    disp = disp.sort_values(["Hotel", "Skupaj €"])
    disp["Zvezde"]    = disp["Zvezde"].apply(stars_html)
    disp["Naš hotel"] = disp["Naš hotel"].apply(lambda x: "✓" if x else "")
    st.dataframe(
        disp,
        width='stretch',
        hide_index=True,
        column_config={
            "Skupaj €": st.column_config.NumberColumn(format="€%.0f"),
            "Na noč €": st.column_config.NumberColumn(format="€%.0f"),
            "Ocena":    st.column_config.NumberColumn(format="%.1f"),
            "Link":     st.column_config.LinkColumn("Booking.com"),
        },
    )
    csv = disp.to_csv(index=False).encode("utf-8")
    # Key mora biti unikaten za vsak segment+termin kombinacijo
    safe_key = key.replace(" ", "_").replace(".", "").replace("–", "_").replace("/", "_")
    st.download_button(
        "↓ Prenesi CSV", csv,
        f"konkurenti_{safe_key}.csv", "text/csv",
        key=f"dl_{safe_key}",
    )


def _render_segment_content(df: pd.DataFrame, seg_key: str, t_label: str):
    """KPI vrstica + tabela za en segment + en termin."""
    if df is None or df.empty:
        st.warning("Ni podatkov za ta segment.")
        return

    # Poskrbi da stolpci obstajajo
    required = {"name", "is_self", "price_eur"}
    if not required.issubset(df.columns):
        st.warning("Podatki nimajo pravilnih stolpcev.")
        return

    df_prices = df[df["price_eur"].notna() & (df["price_eur"] > 0)].copy()

    self_avg  = 0.0
    comp_avg  = 0.0
    n_comp    = 0
    cheapest  = None
    priciest  = None

    if not df_prices.empty:
        best = df_prices.groupby(["name", "is_self"], as_index=False)["price_eur"].min()
        self_df = best[best["is_self"] == True]
        comp_df = best[best["is_self"] == False]

        if not self_df.empty:
            self_avg = float(self_df["price_eur"].mean())
        if not comp_df.empty:
            comp_avg  = float(comp_df["price_eur"].mean())
            n_comp    = int(comp_df["name"].nunique())
            cheapest  = comp_df.loc[comp_df["price_eur"].idxmin()]
            priciest  = comp_df.loc[comp_df["price_eur"].idxmax()]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Naša povp. cena",
        f"€{self_avg:,.0f}" if self_avg else "–",
        delta=f"vs €{comp_avg:,.0f} trg" if comp_avg else None,
        delta_color="inverse" if self_avg > comp_avg else "normal",
    )
    c2.metric("Konkurenti", n_comp)
    c3.metric(
        "Najcenejši konkurent",
        f"€{float(cheapest['price_eur']):,.0f}" if cheapest is not None else "–",
        str(cheapest["name"]) if cheapest is not None else "",
    )
    c4.metric(
        "Najdražji konkurent",
        f"€{float(priciest['price_eur']):,.0f}" if priciest is not None else "–",
        str(priciest["name"]) if priciest is not None else "",
    )

    st.divider()
    render_table(df, key=f"{seg_key}_{t_label}")


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Nastavitve iskanja")
    st.divider()

    today = date.today()

    st.markdown("**Termini**")
    st.caption("Vnesi 1–4 termine iskanja.")

    termini = []
    for i in range(1, 5):
        with st.expander(f"Termin {i}" + (" ✱" if i == 1 else ""), expanded=(i == 1)):
            c_in  = st.date_input("Prihod", value=today, key=f"ci_{i}")
            c_out = st.date_input("Odhod",  value=today, key=f"co_{i}")
            active = st.checkbox("Vključi ta termin", value=(i == 1), key=f"active_{i}")
            if active and c_out > c_in:
                termini.append((c_in, c_out))

    # Fallback — vsaj en termin mora biti
    if not termini:
        termini = [(today, today + timedelta(days=1))]

    st.divider()
    st.markdown("**Objekt**")
    selected_segments = st.multiselect(
        "Prikaži objekte",
        options=list(SHEETS.keys()),
        default=[],
        placeholder="Izberi objekte…",
    )

    st.divider()
    search_btn = st.button("Poišči cene", use_container_width=True)

    st.markdown("""
<div class="info-box">
<b>Iskanje gostov:</b><br>
2 osebi — Hotel Convent, Vile brez balkona, Vile z balkonom, Olive Suites<br>
4 osebe — Premium Mobile Homes, Adria Apartments
</div>
""", unsafe_allow_html=True)
    st.markdown("""
<div class="info-box" style="margin-top:0.5rem;">
<b>Podatki:</b> Seznam konkurentov se nalaga iz tvojega
<b>Google Sheeta</b>. Dodaj hotel v sheet — app se samodejno posodobi.
</div>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div>
      <h1>Adria Ankaran — Monitor konkurentov</h1>
      <p>Slovenska obala · Primerjava cen · Booking.com</p>
    </div>
    <img src="https://www.adria-ankaran.si//app/uploads/2025/10/logo-Adria.jpg"
         style="height:105px;width:105px;object-fit:contain;flex-shrink:0;margin-left:2rem;">
  </div>
</div>
""", unsafe_allow_html=True)

# ── Welcome screen ────────────────────────────────────────────────────────────
if not search_btn:
    n_cols = min(3, len(SHEETS))
    seg_items = list(SHEETS.items())
    for chunk_start in range(0, len(seg_items), n_cols):
        chunk = seg_items[chunk_start:chunk_start + n_cols]
        cols  = st.columns(len(chunk))
        for col, (seg_key, seg) in zip(cols, chunk):
            sheet_df = load_sheet(seg_key)
            n_comp = (
                len(sheet_df[sheet_df["type"] == "competitor"])
                if "type" in sheet_df.columns else "?"
            )
            with col:
                st.markdown(f"""<div class="metric-card">
                    <h4>{seg_key}</h4>
                    <p>{seg['description']}</p>
                    <p class="n-comp">{n_comp} konkurentov</p>
                    <span class="adults-badge">{seg['adults']} odrasli</span>
                </div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
    st.info("Vnesi termine, izberi segment, nato klikni **Poišči cene**.")
    st.stop()

# ── Validacija ────────────────────────────────────────────────────────────────
if not selected_segments:
    st.warning("Izberi vsaj en segment.")
    st.stop()

# ── Pripravi termin labele ────────────────────────────────────────────────────
t_labels = [f"{ci.strftime('%d.%m')}–{co.strftime('%d.%m')}" for ci, co in termini]

# ── Fetch ─────────────────────────────────────────────────────────────────────
token = _get_apify_token()

# ── Brez tokena ne moremo nič prikazati ──────────────────────────────────────
if not token:
    st.error("### 🔑 Manjka Apify token")
    st.markdown("""
Brez Apify tokena aplikacija ne more pridobiti cen z Booking.com.

**Kako dodaš token:**
1. Pojdi na [apify.com](https://apify.com) in se prijavi
2. V meniju klikni **Settings → Integrations → API tokens**
3. Kopiraj svoj token
4. Na Streamlit Cloud odpri **Manage app → Secrets** in dodaj:

```toml
APIFY_TOKEN = "apify_api_xxxxxxxxxxxx"
```
5. Shrani in restartaj app
""")
    st.stop()

prog  = st.progress(0, text="Nalagam seznam hotelov…")

# 1. Naložimo sheet-e
sheets_data: dict = {}
for seg_key in selected_segments:
    sheets_data[seg_key] = load_sheet(seg_key)

# 2. Zberemo URL-je grupirane po adults_count
urls_per_adults: dict = defaultdict(list)
for seg_key in selected_segments:
    adults = SHEETS[seg_key]["adults"]
    for _, row in sheets_data[seg_key].iterrows():
        u = str(row.get("url", "")).strip()
        if u.startswith("http") and u not in urls_per_adults[adults]:
            urls_per_adults[adults].append(u)

total_hotels = sum(len(v) for v in urls_per_adults.values())
n_runs       = len(urls_per_adults) * len(termini)
st.caption(f"{total_hotels} hotelov · {len(termini)} termin(i) · {n_runs} Apify runs")

# 3. En set Apify runov na termin (progress popravno izračunan)
all_batches: dict = {}   # {(ci, co) -> {adults -> {url -> [...]}}}
n_termini    = len(termini)
n_adult_grps = len(urls_per_adults)

for t_idx, (t_in, t_out) in enumerate(termini):
    def _make_progress(t_idx_=t_idx):
        def _cb(pct, msg):
            overall = (t_idx_ + pct) / n_termini * 0.85
            prog.progress(min(overall, 0.85), text=msg)
        return _cb
    batch = apify_fetch_all(
        dict(urls_per_adults), t_in, t_out, token, _make_progress()
    )
    all_batches[(t_in, t_out)] = batch

# 4. Sestavi DataFrames
prog.progress(0.9, text="Sestavljam rezultate…")
all_data: dict = {}   # {seg_key -> {t_label -> pd.DataFrame}}
for seg_key in selected_segments:
    all_data[seg_key] = {}
    adults = SHEETS[seg_key]["adults"]
    for (t_in, t_out), t_label in zip(termini, t_labels):
        batch = all_batches[(t_in, t_out)].get(adults, {})
        rows  = assemble_segment(seg_key, sheets_data[seg_key],
                                 t_in, t_out, adults, batch)
        df    = pd.DataFrame(rows)
        df["termin"] = t_label
        all_data[seg_key][t_label] = df

prog.progress(1.0, text="Končano.")
time.sleep(0.3)
prog.empty()

st.caption(f"Živi podatki · Booking.com · Termini: {', '.join(t_labels)}")

# ── Segment tabs ──────────────────────────────────────────────────────────────
seg_tabs = st.tabs(selected_segments)

for tab, seg_key in zip(seg_tabs, selected_segments):
    seg    = SHEETS[seg_key]
    adults = seg["adults"]

    with tab:
        st.markdown(f"""
<div class="segment-header">
  <b style="font-size:1.05rem;">{seg_key}</b>
  <span class="adults-pill">{adults} odrasli</span>
  &nbsp;&nbsp;<span>{seg['description']}</span>
</div>""", unsafe_allow_html=True)

        if len(termini) == 1:
            # En termin — direktno prikažemo vsebino
            _render_segment_content(
                all_data[seg_key][t_labels[0]], seg_key, t_labels[0]
            )
        else:
            # Več terminov — sub-tabs
            t_tabs = st.tabs(t_labels)
            for t_tab, t_label in zip(t_tabs, t_labels):
                with t_tab:
                    _render_segment_content(
                        all_data[seg_key][t_label], seg_key, t_label
                    )  

