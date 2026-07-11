import streamlit as st
import pandas as pd
from datetime import date, timedelta
from collections import defaultdict
import time
import requests
import io

st.set_page_config(page_title="Adria Ankaran – Monitor", layout="wide")

SHEET_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRbx6EnzVBv0ZlRvF6_GuO2ZlCUkrwFp9iR_GmViy5r41hzsexrBW84MdvXI-0DtNul4fEUaLGjx27C/pub"

SHEETS = {
    "Hotel Convent":       {"csv_url": f"{SHEET_BASE}?gid=0&single=true&output=csv",          "adults": 2},
    "Vile brez balkona":   {"csv_url": f"{SHEET_BASE}?gid=1313360174&single=true&output=csv", "adults": 2},
    "Vile z balkonom":     {"csv_url": f"{SHEET_BASE}?gid=996668368&single=true&output=csv",  "adults": 2},
    "Olive Suites":        {"csv_url": f"{SHEET_BASE}?gid=91411090&single=true&output=csv",   "adults": 2},
    "Premium Mobile Homes":{"csv_url": f"{SHEET_BASE}?gid=1775050597&single=true&output=csv", "adults": 4},
    "Adria Apartments":    {"csv_url": f"{SHEET_BASE}?gid=1575590147&single=true&output=csv", "adults": 4},
}

APIFY_ACTOR = "voyager~booking-scraper"
APIFY_BASE  = "https://api.apify.com/v2"

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
    "Vile z balkonom": [], "Olive Suites": [], "Premium Mobile Homes": [], "Adria Apartments": [],
}


def fix_encoding(s):
    try:
        return s.encode("latin-1").decode("utf-8")
    except Exception:
        return s


def _get_apify_token():
    import os
    try:
        t = st.secrets["APIFY_TOKEN"]
        if t:
            return t
    except Exception:
        pass
    return os.getenv("APIFY_TOKEN")


@st.cache_data(ttl=300)
def load_sheet(seg_key):
    try:
        resp = requests.get(SHEETS[seg_key]["csv_url"], timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame(FALLBACK_DATA.get(seg_key, []))


def _match_url(h_url, urls):
    for u in urls:
        if "/hotel/" in u:
            slug = u.split("/hotel/")[1].split(".")[0]
            if slug and slug in h_url:
                return u
    return None


def _run_apify(run_input, token, max_items=20):
    hdrs = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    r = requests.post(f"{APIFY_BASE}/acts/{APIFY_ACTOR}/runs", json=run_input, headers=hdrs, timeout=30)
    r.raise_for_status()
    data = r.json()["data"]
    run_id = data["id"]
    dataset_id = data["defaultDatasetId"]
    for _ in range(60):
        time.sleep(5)
        status = requests.get(f"{APIFY_BASE}/actor-runs/{run_id}", headers=hdrs, timeout=15).json()["data"]["status"]
        if status == "SUCCEEDED":
            break
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            return []
    raw = requests.get(f"{APIFY_BASE}/datasets/{dataset_id}/items", headers=hdrs,
                       params={"format": "json", "clean": "true", "limit": max_items}, timeout=20).json()
    return raw if isinstance(raw, list) else []


def _extract_price(h):
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


def _apify_single_run(urls, checkin, checkout, adults, nights, token):
    out = {}
    run_input = {
        "startUrls": [{"url": u} for u in urls if u.startswith("http")],
        "checkIn":   checkin.strftime("%Y-%m-%d"),
        "checkOut":  checkout.strftime("%Y-%m-%d"),
        "adults":    adults,
        "children":  0,
        "currency":  "EUR",
        "language":  "en-gb",
        "maxItems":  len(urls) * 3,
        "minScore":  "1",
        "minMaxPrice": "0-999999",
        "flexWindow": "0",
        "sortBy":    "price",
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
            out[matched] = [{"price_eur": price, "per_night": round(price / nights, 2),
                             "stars": stars, "rating": rating, "meal_plan": "Najnižja cena", "source": "apify_live"}]
    return out


def apify_fetch_all(urls_per_adults, checkin, checkout, token, progress_cb=None):
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


def assemble_segment(seg_key, sheet_df, checkin, checkout, adults, batch):
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
                results.append({"name": name, "location": location, "is_self": is_self,
                                "adults": adults, "nights": nights, "booking_url": url, "segment": seg_key, **v})
        else:
            results.append({"name": name, "location": location, "is_self": is_self,
                            "adults": adults, "nights": nights, "booking_url": url, "segment": seg_key,
                            "price_eur": None, "per_night": None, "stars": 0, "rating": 0.0,
                            "meal_plan": "Ni razpoložljivosti", "source": "error"})
    return results


def render_table(df, key="default"):
    disp = df[["name", "location", "stars", "rating", "meal_plan",
               "adults", "nights", "price_eur", "per_night", "is_self", "booking_url"]].copy()
    disp.columns = ["Hotel", "Kraj", "Zvezdice", "Ocena", "Vrsta ponudbe",
                    "Odrasli", "Noči", "Skupaj €", "Na noč €", "Naš hotel", "Link"]
    disp = disp.sort_values(["Hotel", "Skupaj €"])
    disp["Zvezdice"]  = disp["Zvezdice"].apply(lambda n: "★" * int(n) if n else "–")
    disp["Naš hotel"] = disp["Naš hotel"].apply(lambda x: "✓" if x else "")
    st.dataframe(disp, use_container_width=True, hide_index=True,
                 column_config={
                     "Skupaj €": st.column_config.NumberColumn(format="€%.0f"),
                     "Na noč €": st.column_config.NumberColumn(format="€%.0f"),
                     "Ocena":    st.column_config.NumberColumn(format="%.1f"),
                     "Link":     st.column_config.LinkColumn("Booking.com"),
                 })
    csv = disp.to_csv(index=False).encode("utf-8")
    safe_key = key.replace(" ", "_").replace(".", "").replace("–", "_").replace("/", "_")
    st.download_button("↓ Prenesi CSV", csv, f"konkurenti_{safe_key}.csv", "text/csv", key=f"dl_{safe_key}")


def render_segment(df, seg_key, t_label):
    if df is None or df.empty:
        st.warning("Ni podatkov.")
        return
    if not {"name", "is_self", "price_eur"}.issubset(df.columns):
        st.warning("Napačni stolpci.")
        return

    df_p = df[df["price_eur"].notna() & (df["price_eur"] > 0)].copy()
    self_avg = comp_avg = 0.0
    n_comp = 0
    cheapest = priciest = None

    if not df_p.empty:
        best    = df_p.groupby(["name", "is_self"], as_index=False)["price_eur"].min()
        self_df = best[best["is_self"] == True]
        comp_df = best[best["is_self"] == False]
        if not self_df.empty:
            self_avg = float(self_df["price_eur"].mean())
        if not comp_df.empty:
            comp_avg = float(comp_df["price_eur"].mean())
            n_comp   = int(comp_df["name"].nunique())
            cheapest = comp_df.loc[comp_df["price_eur"].idxmin()]
            priciest = comp_df.loc[comp_df["price_eur"].idxmax()]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Naša povp. cena", f"€{self_avg:,.0f}" if self_avg else "–",
              delta=f"vs €{comp_avg:,.0f} trg" if comp_avg else None,
              delta_color="inverse" if self_avg > comp_avg else "normal")
    c2.metric("Konkurenti", n_comp)
    c3.metric("Najcenejši", f"€{float(cheapest['price_eur']):,.0f}" if cheapest is not None else "–",
              str(cheapest["name"]) if cheapest is not None else "")
    c4.metric("Najdražji",  f"€{float(priciest['price_eur']):,.0f}" if priciest is not None else "–",
              str(priciest["name"]) if priciest is not None else "")

    st.divider()
    render_table(df, key=f"{seg_key}_{t_label}")


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Nastavitve iskanja")

    today = date.today()

    st.subheader("Termin")
    c_in  = st.date_input("Datum prihoda", value=today, key="checkin")
    c_out = st.date_input("Datum odhoda",  value=today + timedelta(days=1), key="checkout")

    if c_out <= c_in:
        st.warning("Odhod mora biti po prihodu.")
        termini = [(today, today + timedelta(days=1))]
    else:
        termini = [(c_in, c_out)]

    st.divider()
    st.subheader("Objekti")
    selected_segments = st.multiselect("Izberi objekte", options=list(SHEETS.keys()), default=[])

    st.divider()
    search_btn = st.button("POIŠČI CENE", use_container_width=True)

    st.info("2 osebi: Hotel Convent, Vile brez balkona, Vile z balkonom, Olive Suites\n\n4 osebe: Premium Mobile Homes, Adria Apartments")

# ── Main ──────────────────────────────────────────────────────────────────────
st.title("Adria Ankaran — Monitor konkurentov")
st.caption("Slovenska obala · Primerjava cen · Booking.com")

if not search_btn:
    cols = st.columns(3)
    for idx, (seg_key, seg) in enumerate(SHEETS.items()):
        sheet_df = load_sheet(seg_key)
        n_comp   = len(sheet_df[sheet_df["type"] == "competitor"]) if "type" in sheet_df.columns else "?"
        with cols[idx % 3]:
            st.metric(seg_key, f"{n_comp} konkurentov", f"{seg['adults']} odrasli")
    st.info("Vnesi termine, izberi objekte in klikni POIŠČI CENE.")
    st.stop()

if not selected_segments:
    st.warning("Izberi vsaj en objekt.")
    st.stop()

t_labels = [f"{ci.strftime('%d.%m.%y')}–{co.strftime('%d.%m.%y')}" for ci, co in termini]

token = _get_apify_token()
if not token:
    st.error("Manjka APIFY_TOKEN v Streamlit Secrets.")
    st.stop()

prog = st.progress(0, text="Nalagam…")

sheets_data = {}
for seg_key in selected_segments:
    sheets_data[seg_key] = load_sheet(seg_key)

urls_per_adults = defaultdict(list)
for seg_key in selected_segments:
    adults = SHEETS[seg_key]["adults"]
    for _, row in sheets_data[seg_key].iterrows():
        u = str(row.get("url", "")).strip()
        if u.startswith("http") and u not in urls_per_adults[adults]:
            urls_per_adults[adults].append(u)

n_termini   = len(termini)
all_batches = {}
for t_idx, (t_in, t_out) in enumerate(termini):
    def _make_cb(idx=t_idx):
        def _cb(pct, msg):
            prog.progress(min((idx + pct) / n_termini * 0.85, 0.85), text=msg)
        return _cb
    all_batches[(t_in, t_out)] = apify_fetch_all(dict(urls_per_adults), t_in, t_out, token, _make_cb())

prog.progress(0.9, text="Sestavljam rezultate…")
all_data = {}
for seg_key in selected_segments:
    all_data[seg_key] = {}
    adults = SHEETS[seg_key]["adults"]
    for (t_in, t_out), t_label in zip(termini, t_labels):
        rows = assemble_segment(seg_key, sheets_data[seg_key], t_in, t_out, adults,
                                all_batches[(t_in, t_out)].get(adults, {}))
        df = pd.DataFrame(rows)
        df["termin"] = t_label
        all_data[seg_key][t_label] = df

prog.progress(1.0, text="Končano.")
time.sleep(0.3)
prog.empty()

st.caption(f"Termini: {', '.join(t_labels)}")

seg_tabs = st.tabs(selected_segments)
for tab, seg_key in zip(seg_tabs, selected_segments):
    with tab:
        st.subheader(f"{seg_key} · {SHEETS[seg_key]['adults']} odrasli")
        if len(termini) == 1:
            render_segment(all_data[seg_key][t_labels[0]], seg_key, t_labels[0])
        else:
            t_tabs = st.tabs(t_labels)
            for t_tab, t_label in zip(t_tabs, t_labels):
                with t_tab:
                    render_segment(all_data[seg_key][t_label], seg_key, t_label)
