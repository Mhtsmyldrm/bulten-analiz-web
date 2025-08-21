# app.py
# -*- coding: utf-8 -*-

import os
import io
import json
import time
import math
import datetime as dt
from datetime import datetime, timedelta, timezone

import requests
import numpy as np
import pandas as pd
import streamlit as st

# -----------------------------------------------------------
# SAYFA AYARLARI (YAN PANEL KAPALI) ve BASLIK
# -----------------------------------------------------------
st.set_page_config(page_title="Bülten Analiz",
                   layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
    /* Yan paneli tamamen gizle */
    section[data-testid="stSidebar"] {display: none;}
    div[data-testid="stToolbar"] {display: none;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Bülten Analiz")

# -----------------------------------------------------------
# KULLANICI GİRİŞİ (ESKİ DÜZEN)
# -----------------------------------------------------------
IST = timezone(timedelta(hours=3))
now = datetime.now(IST)
default_start = (now + timedelta(minutes=5)).replace(second=0, microsecond=0)
colL, colR = st.columns([1,1])
with colL:
    st.write("Analiz için Saat Aralığı")
    st.caption(f"Başlangıç Saati: {default_start.strftime('%d.%m.%Y %H:%M')} (Otomatik, şu an + 5 dakika)")
with colR:
    end_date = st.date_input("Bitiş Tarihi", value=now.date(), format="YYYY/MM/DD")
    end_time = st.time_input("Bitiş Saati", value=dt.time(19,30))

end_dt = datetime.combine(end_date, end_time).replace(tzinfo=IST)

if end_dt <= default_start:
    st.warning("Bitiş saati başlangıçtan büyük olmalı.")
    st.stop()

run = st.button("Analiz Et", use_container_width=True)

# -----------------------------------------------------------
# YARDIMCI: DRIVE'DAN İNDİRME (GÜVENLİ) + FALLBACK
# -----------------------------------------------------------
def drive_id_from_url(url: str) -> str:
    # https://drive.google.com/file/d/<ID>/view?...
    try:
        return url.split("/d/")[1].split("/")[0]
    except Exception:
        return url

def download_from_drive(url_or_id: str, out_path: str, as_binary=True) -> bool:
    """
    Google Drive dosyasını istek/confirm cookie akışı ile indirir.
    Spreadsheet için export=xlsx kullanır. Başarısızsa False döner.
    """
    file_id = drive_id_from_url(url_or_id)
    session = requests.Session()
    base = "https://docs.google.com/uc?export=download"
    params = {"id": file_id}

    try:
        # İlk talep (confirm token gerekebilir)
        resp = session.get(base, params=params, timeout=30)
        resp.raise_for_status()

        # Büyük dosya onayı:
        token = None
        for k, v in resp.cookies.items():
            if k.startswith("download_warning"):
                token = v
                break
        if token:
            params["confirm"] = token
            resp = session.get(base, params=params, timeout=30)
            resp.raise_for_status()

        content = resp.content
        # Drive bazen HTML uyarı döndürebilir; XLSX/JSON değilse başarısız sayalım
        if len(content) < 100 and b"html" in content.lower():
            return False

        mode = "wb" if as_binary else "w"
        with open(out_path, mode) as f:
            f.write(content if as_binary else content.decode("utf-8"))
        return True
    except Exception:
        return False

# -----------------------------------------------------------
# KAYNAKLAR: MATCHES (EXCEL) + MAPPINGS (JSON)
# -----------------------------------------------------------
MATCHES_URL = "https://docs.google.com/spreadsheets/d/11m7tX2xCavCM_cij69UaSVijFuFQbveM/export?format=xlsx"
LEAGUE_MAP_URL = "https://drive.google.com/file/d/1L8HA_emD92BJSuCn-P9GJF-hH55nIKE7/view?usp=drive_link"
MTID_MAP_URL   = "https://drive.google.com/file/d/1N1PjFla683BYTAdzVDaajmcnmMB5wiiO/view?usp=drive_link"

CACHE_DIR = "/mnt/data"
os.makedirs(CACHE_DIR, exist_ok=True)
matches_xlsx = os.path.join(CACHE_DIR, "matches.xlsx")
league_json   = os.path.join(CACHE_DIR, "league_mapping.json")
mtid_json     = os.path.join(CACHE_DIR, "mtid_mapping.json")

@st.cache_data(show_spinner=False)
def load_matches_df() -> pd.DataFrame:
    # Drive -> XLSX indir; olmazsa yerelde varsa onu kullan
    ok = download_from_drive(MATCHES_URL, matches_xlsx, as_binary=True)
    if not ok and not os.path.exists(matches_xlsx):
        raise RuntimeError("matches.xlsx indirilemedi.")
    df = pd.read_excel(matches_xlsx, engine="openpyxl")
    # Beklenen sütun adları v26/önceki app ile uyumlu olsun
    # (Eski app.py'deki pazar isimleri referans alındı)  :contentReference[oaicite:5]{index=5}
    return df

@st.cache_data(show_spinner=False)
def load_mappings():
    # Önce Drive’dan dene
    league_ok = download_from_drive(LEAGUE_MAP_URL, league_json, as_binary=False)
    mtid_ok   = download_from_drive(MTID_MAP_URL, mtid_json, as_binary=False)

    league_mapping = {}
    mtid_mapping = {}

    try:
        if os.path.exists(league_json):
            with open(league_json, "r", encoding="utf-8") as f:
                league_mapping = {int(k): v for k, v in json.load(f).items()}
    except Exception:
        league_mapping = {}

    try:
        if os.path.exists(mtid_json):
            # v26’daki (mtid, sov) anahtarlı yapı ile uyum: "((mtid, sov))": ["Pazar1", ...]
            raw = json.load(open(mtid_json, "r", encoding="utf-8"))
            mtid_mapping = {}
            for k, v in raw.items():
                if isinstance(k, str) and k.startswith("(") and k.endswith(")"):
                    parts = k[1:-1].split(",")
                    if len(parts) == 2:
                        mtid = int(parts[0].strip())
                        sov  = parts[1].strip()
                        sov = None if sov.lower() == "null" else float(sov)
                        mtid_mapping[(mtid, sov)] = v
    except Exception:
        mtid_mapping = {}

    # Fallback: eski app.py’de gömülü tablo (Drive erişimi kesilirse devreye girer)  :contentReference[oaicite:6]{index=6}
    if not mtid_mapping:
        mtid_mapping = {
            (1, None): ["Maç Sonucu 1", "Maç Sonucu X", "Maç Sonucu 2"],
            (3, None): ["Çifte Şans 1 veya X", "Çifte Şans 1 veya 2", "Çifte Şans X veya 2"],
            (7, None): ["1. Yarı Sonucu 1", "1. Yarı Sonucu X", "1. Yarı Sonucu 2"],
            (8, None): ["1. Yarı Çifte Şans 1-X", "1. Yarı Çifte Şans 1-2", "1. Yarı Çifte Şans X-2"],
            (9, None): ["2. Yarı Sonucu 1", "2. Yarı Sonucu X", "2. Yarı Sonucu 2"],
            (11, 1.5): ["1,5 Alt/Üst Alt", "1,5 Alt/Üst Üst"],
            (12, 2.5): ["2,5 Alt/Üst Alt", "2,5 Alt/Üst Üst"],
            (13, 3.5): ["3,5 Alt/Üst Alt", "3,5 Alt/Üst Üst"],
            (14, 1.5): ["1. Yarı 1,5 Alt/Üst Alt", "1. Yarı 1,5 Alt/Üst Üst"],
            (15, 2.5): ["1. Yarı 2,5 Alt/Üst Alt", "1. Yarı 2,5 Alt/Üst Üst"],
            (20, 1.5): ["Evsahibi 1,5 Alt/Üst Alt", "Evsahibi 1,5 Alt/Üst Üst"],
            (29, 1.5): ["Deplasman 1,5 Alt/Üst Alt", "Deplasman 1,5 Alt/Üst Üst"],
            (38, None): ["Karşılıklı Gol Var", "Karşılıklı Gol Yok"],
            (43, None): ["Toplam Gol Aralığı 0-1 Gol","Toplam Gol Aralığı 2-3 Gol",
                         "Toplam Gol Aralığı 4-5 Gol","Toplam Gol Aralığı 6+ Gol"],
            (63, None): ["İlk Gol 1","İlk Gol Olmaz","İlk Gol 2"],
            (268, -1.0): ["Handikaplı Maç Sonucu (-1,0) 1","Handikaplı Maç Sonucu (-1,0) X","Handikaplı Maç Sonucu (-1,0) 2"],
            (268, 1.0): ["Handikaplı Maç Sonucu (1,0) 1","Handikaplı Maç Sonucu (1,0) X","Handikaplı Maç Sonucu (1,0) 2"],
            (207, 0.5): ["0,5 Alt/Üst Alt","0,5 Alt/Üst Üst"],
            (155, 4.5): ["4,5 Alt/Üst Alt","4,5 Alt/Üst Üst"],
            (212, 0.5): ["Evsahibi 0,5 Alt/Üst Alt","Evsahibi 0,5 Alt/Üst Üst"],
            (326, 2.5): ["Evsahibi 2,5 Alt/Üst Alt","Evsahibi 2,5 Alt/Üst Üst"],
            (256, 0.5): ["Deplasman 0,5 Alt/Üst Alt","Deplasman 0,5 Alt/Üst Üst"],
            (328, 2.5): ["Deplasman 2,5 Alt/Üst Alt","Deplasman 2,5 Alt/Üst Üst"],
        }
    return mtid_mapping, league_mapping

# Pazar isimleri (excel’deki kolonlar) – eski app.py ve v26 ile uyumlu  :contentReference[oaicite:7]{index=7}
EXCEL_COLUMNS = [
    "Maç Sonucu 1", "Maç Sonucu X", "Maç Sonucu 2",
    "Çifte Şans 1 veya X", "Çifte Şans 1 veya 2", "Çifte Şans X veya 2",
    "0,5 Alt/Üst Alt", "0,5 Alt/Üst Üst",
    "1,5 Alt/Üst Alt", "1,5 Alt/Üst Üst",
    "2,5 Alt/Üst Alt", "2,5 Alt/Üst Üst",
    "3,5 Alt/Üst Alt", "3,5 Alt/Üst Üst",
    "4,5 Alt/Üst Alt", "4,5 Alt/Üst Üst",
    "Karşılıklı Gol Var", "Karşılıklı Gol Yok",
    "1. Yarı Sonucu 1", "1. Yarı Sonucu X", "1. Yarı Sonucu 2",
    "1. Yarı 0,5 Alt/Üst Alt", "1. Yarı 0,5 Alt/Üst Üst",
    "1. Yarı 1,5 Alt/Üst Alt", "1. Yarı 1,5 Alt/Üst Üst",
    "1. Yarı 2,5 Alt/Üst Alt", "1. Yarı 2,5 Alt/Üst Üst",
    "2. Yarı Sonucu 1", "2. Yarı Sonucu X", "2. Yarı Sonucu 2",
    "Toplam Gol Aralığı 0-1 Gol", "Toplam Gol Aralığı 2-3 Gol",
    "Toplam Gol Aralığı 4-5 Gol", "Toplam Gol Aralığı 6+ Gol",
    "Evsahibi 0,5 Alt/Üst Alt", "Evsahibi 0,5 Alt/Üst Üst",
    "Evsahibi 1,5 Alt/Üst Alt", "Evsahibi 1,5 Alt/Üst Üst",
    "Evsahibi 2,5 Alt/Üst Alt", "Evsahibi 2,5 Alt/Üst Üst",
    "Deplasman 0,5 Alt/Üst Alt", "Deplasman 0,5 Alt/Üst Üst",
    "Deplasman 1,5 Alt/Üst Alt", "Deplasman 1,5 Alt/Üst Üst",
    "Deplasman 2,5 Alt/Üst Alt", "Deplasman 2,5 Alt/Üst Üst",
    "Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2",
    "Handikaplı Maç Sonucu (1,0) 1",  "Handikaplı Maç Sonucu (1,0) X",  "Handikaplı Maç Sonucu (1,0) 2",
]

# -----------------------------------------------------------
# NESINE API – SAĞLAM GETİRME ve AYIKLAMA
# (v26’daki JSON kullanılabilirliği gözetilerek tasarlandı)  :contentReference[oaicite:8]{index=8}
# -----------------------------------------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nesine.com/",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Connection": "keep-alive",
    "X-Requested-With": "XMLHttpRequest",
}

def fetch_api_json():
    # v26’da kullanılan delta uç noktası – şu an yaygın format (sg.EA)   :contentReference[oaicite:9]{index=9}
    url_v26 = "https://bulten.nesine.com/api/bulten/getprebultendelta?eventVersion=462376563&marketVersion=462376563&oddVersion=1712799325&_=1743545516827"
    try:
        r = requests.get(url_v26, headers=HEADERS, timeout=25)
        r.raise_for_status()
        j = r.json()
        # Beklenen yapı: {"sg":{"EA":[...]}}
        if isinstance(j, dict) and j.get("sg", {}).get("EA"):
            return j
    except Exception:
        pass

    # Fallback 2: eski delta (Data.EventList) – eski app’de kullanıldı
    url_old = "https://bulten.nesine.com/api/bulten/getprebultendelta"
    try:
        r = requests.get(url_old, headers=HEADERS, timeout=25)
        r.raise_for_status()
        j = r.json()
        if isinstance(j, dict):
            # bazen doğrudan EventList olabilir
            if j.get("sg", {}).get("EA"):
                return j
            if j.get("Data", {}).get("EventList"):
                return j
    except Exception:
        pass

    return {}

def parse_api_to_rows(api_json, start_dt: datetime, end_dt: datetime,
                      mtid_mapping: dict, league_mapping: dict) -> list:
    """
    Çıktı: [{Saat, Tarih, Ev Sahibi Takım, Deplasman Takım, Lig Adı, MA(list), MTIDs(set)}...]
    """
    rows = []
    # İki olası formatı karşıla:
    ea_list = None
    if api_json.get("sg", {}).get("EA"):
        ea_list = api_json["sg"]["EA"]
        # v26 alan adları: D (date dd.mm.yyyy), T (HH:MM), H (home), A (away), LN (league id?), MA (markets list)
        for m in ea_list:
            try:
                d_str = m.get("D","")
                t_str = m.get("T","")
                match_dt = datetime.strptime(f"{d_str} {t_str}", "%d.%m.%Y %H:%M").replace(tzinfo=IST)
            except Exception:
                continue
            if not (start_dt <= match_dt <= end_dt):
                continue
            lig_id = m.get("L", None)
            lig_adi = league_mapping.get(int(lig_id), str(lig_id)) if lig_id is not None else ""
            home = m.get("H","").strip()
            away = m.get("A","").strip()
            ma = m.get("MA", []) or []  # Market array
            # MTIDs set
            mtids = set()
            for mk in ma:
                mt = mk.get("MTID")
                if mt is not None:
                    mtids.add(int(mt))
            rows.append({
                "Saat": match_dt.strftime("%H:%M"),
                "Tarih": match_dt.strftime("%d.%m.%Y"),
                "Ev Sahibi Takım": home,
                "Deplasman Takım": away,
                "Lig Adı": lig_adi,
                "MA": ma,
                "MTIDs": list(mtids),
            })
        return rows

    # Eski format – Data.EventList
    ev_list = api_json.get("Data", {}).get("EventList", [])
    for m in ev_list:
        try:
            # Eski yapıda Date/Time farklı alanlarda olabilir
            d_str = m.get("EventDate", "") or m.get("D", "")
            t_str = m.get("EventTime", "") or m.get("T", "")
            # Bazı durumlarda ISO olabilir
            if d_str and "-" in d_str:
                # yyyy-mm-dd
                match_dt = datetime.strptime(f"{d_str} {t_str}", "%Y-%m-%d %H:%M").replace(tzinfo=IST)
            else:
                match_dt = datetime.strptime(f"{d_str} {t_str}", "%d.%m.%Y %H:%M").replace(tzinfo=IST)
        except Exception:
            continue
        if not (start_dt <= match_dt <= end_dt):
            continue

        lig_id = m.get("LeagueId", None) or m.get("L", None)
        lig_adi = league_mapping.get(int(lig_id), str(lig_id)) if lig_id is not None else ""
        home = (m.get("HomeTeamName") or m.get("H") or "").strip()
        away = (m.get("AwayTeamName") or m.get("A") or "").strip()

        # Market’ler farklı anahtarlarla gelebilir; normalize edelim
        ma = m.get("Markets") or m.get("MA") or []
        mtids = set()
        for mk in ma:
            mt = mk.get("MTID") or mk.get("MarketTypeId")
            if mt is not None:
                mtids.add(int(mt))
        rows.append({
            "Saat": match_dt.strftime("%H:%M"),
            "Tarih": match_dt.strftime("%d.%m.%Y"),
            "Ev Sahibi Takım": home,
            "Deplasman Takım": away,
            "Lig Adı": lig_adi,
            "MA": ma,
            "MTIDs": list(mtids),
        })
    return rows

def odds_from_MA(ma_list: list, mtid_mapping: dict) -> dict:
    """
    API MA dizisinden EXCEL_COLUMNS’a denk oran sözlüğü üret.
    v26’daki OCA/N (seçenek no) alanlarını kullanır; yoksa atlar.  :contentReference[oaicite:10]{index=10}
    """
    out = {}
    for market in ma_list or []:
        mtid = market.get("MTID")
        sov  = market.get("SOV")
        try:
            sov = None if sov in (None, "", "null") else float(sov)
        except Exception:
            sov = None
        names = mtid_mapping.get((int(mtid), sov), []) if mtid is not None else []
        if not names:
            continue
        # OCA: [{N: "1", O: 1.85}, ...]
        oca = market.get("OCA", []) or market.get("OC", []) or []
        if not isinstance(oca, list):
            continue
        # Basit eşleme: listedeki pazar adlarını sırayla OCA seçenekleriyle eşle
        # (v26’da çoğunlukla N="1","2","3" sırasıyla 1/X/2 vb.)
        for idx, name in enumerate(names, start=1):
            # OCA içinden N==idx olanı bul
            sel = None
            for item in oca:
                n = str(item.get("N", "")).strip()
                if n == str(idx):
                    sel = item
                    break
            if sel is None:
                # Bazı pazarlarda N alanı olmayabilir; sıraya göre deneriz
                if idx-1 < len(oca):
                    sel = oca[idx-1]
            if sel is not None:
                odd = sel.get("O", None)
                try:
                    odd = float(odd)
                except Exception:
                    continue
                out[name] = odd
    return out

# -----------------------------------------------------------
# v26 BENZERLİK HESABI (kapılı/katmanlı) – birebir uyarlama  :contentReference[oaicite:11]{index=11}
# -----------------------------------------------------------
def _to_float(x):
    try:
        return float(x)
    except Exception:
        return None

def _prob(odd):
    odd = _to_float(odd)
    if odd is None or odd <= 0:
        return None
    return 1.0 / odd

def _fair_trio(a, b, c):
    pa, pb, pc = _prob(a), _prob(b), _prob(c)
    if None in (pa, pb, pc) or min(pa, pb, pc) <= 0:
        return None
    s = pa + pb + pc
    return (pa / s, pb / s, pc / s)

def _rel_diff(pa, pb):
    if pa is None or pb is None or pa <= 0 or pb <= 0:
        return None
    return abs(pa - pb) / ((pa + pb) / 2.0)

def _bin_sim(key, api_odds, match_odds):
    if key not in api_odds or key not in match_odds:
        return None
    pa, pb = _prob(api_odds[key]), _prob(match_odds[key])
    d = _rel_diff(pa, pb)
    if d is None:
        return None
    C = 3.5
    return math.exp(-C * d)

CRITICAL_MARKETS = {
    "Maç Sonucu 1", "Maç Sonucu X", "Maç Sonucu 2",
    "2,5 Alt/Üst Alt", "2,5 Alt/Üst Üst",
    "Karşılıklı Gol Var", "Karşılıklı Gol Yok",
    "1. Yarı Sonucu 1", "1. Yarı Sonucu X", "1. Yarı Sonucu 2",
}

IMPORTANT_MARKETS = {
    "0,5 Alt/Üst Alt", "0,5 Alt/Üst Üst",
    "1,5 Alt/Üst Alt", "1,5 Alt/Üst Üst",
    "3,5 Alt/Üst Alt", "3,5 Alt/Üst Üst",
    "Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2",
}

def quality_filter(api_odds: dict, data_odds: dict) -> bool:
    # v26 kalite filtresi (özet).  :contentReference[oaicite:12]{index=12}
    api_count  = sum(1 for c in EXCEL_COLUMNS if c in api_odds and pd.notna(api_odds[c]))
    data_count = sum(1 for c in EXCEL_COLUMNS if c in data_odds and pd.notna(data_odds[c]))
    if data_count < api_count * 0.7:
        return False
    critical_count = sum(1 for m in CRITICAL_MARKETS if m in data_odds and pd.notna(data_odds[m]))
    if critical_count < max(1, int(len(CRITICAL_MARKETS) * 0.5)):
        return False
    return True

def calculate_similarity(api_odds: dict, match_odds: dict) -> float:
    # (v26 fonksiyonundan birebir – özetlenmiş)  :contentReference[oaicite:13]{index=13}
    MS1, MSX, MS2 = "Maç Sonucu 1", "Maç Sonucu X", "Maç Sonucu 2"
    KG_V, KG_Y    = "Karşılıklı Gol Var", "Karşılıklı Gol Yok"
    O25U, O25A    = "2,5 Alt/Üst Üst", "2,5 Alt/Üst Alt"

    trio_api = _fair_trio(api_odds.get(MS1), api_odds.get(MSX), api_odds.get(MS2))
    trio_mat = _fair_trio(match_odds.get(MS1), match_odds.get(MSX), match_odds.get(MS2))
    if trio_api is None or trio_mat is None:
        return 0.0

    # Hellinger + bacak başı tolerans
    def hellinger(p, q):
        return max(0.0, 1.0 - (math.sqrt((math.sqrt(p[0])-math.sqrt(q[0]))**2
                                        + (math.sqrt(p[1])-math.sqrt(q[1]))**2
                                        + (math.sqrt(p[2])-math.sqrt(q[2]))**2) / math.sqrt(2.0)))
    ms_sim = hellinger(trio_api, trio_mat)
    if ms_sim < 0.85:
        return round(ms_sim * 100.0, 2)
    per_leg_tol = 0.12
    for i in range(3):
        d = _rel_diff(trio_api[i], trio_mat[i])
        if d is None or d > per_leg_tol:
            bad = 0.0 if d is None else max(0.0, 1.0 - d)
            return round(100.0 * min(bad, ms_sim), 2)

    # High group
    high_list = [("__MS__", ms_sim, 1.0)]
    for k in (KG_V, KG_Y, O25U, O25A):
        s = _bin_sim(k, api_odds, match_odds)
        if s is not None:
            high_list.append((k, s, 1.0))
    for k in ("Çifte Şans 1 veya X", "Çifte Şans 1 veya 2", "Çifte Şans X veya 2"):
        s = _bin_sim(k, api_odds, match_odds)
        if s is not None:
            high_list.append((k, s, 0.5))
    for k in ("Handikaplı Maç Sonucu (-1,0) 1","Handikaplı Maç Sonucu (-1,0) X","Handikaplı Maç Sonucu (-1,0) 2",
              "Handikaplı Maç Sonucu (1,0) 1","Handikaplı Maç Sonucu (1,0) X","Handikaplı Maç Sonucu (1,0) 2"):
        s = _bin_sim(k, api_odds, match_odds)
        if s is not None:
            high_list.append((k, s, 1.0))

    MED_KEYS = [
        "1. Yarı Sonucu 1","1. Yarı Sonucu X","1. Yarı Sonucu 2",
        "0,5 Alt/Üst Alt","0,5 Alt/Üst Üst",
        "1,5 Alt/Üst Alt","1,5 Alt/Üst Üst",
        "3,5 Alt/Üst Alt","3,5 Alt/Üst Üst",
        "4,5 Alt/Üst Alt","4,5 Alt/Üst Üst",
        "2. Yarı Sonucu 1","2. Yarı Sonucu X","2. Yarı Sonucu 2",
        "Toplam Gol Aralığı 0-1 Gol","Toplam Gol Aralığı 2-3 Gol",
        "Toplam Gol Aralığı 4-5 Gol","Toplam Gol Aralığı 6+ Gol",
    ]
    med_list = []
    for k in MED_KEYS:
        s = _bin_sim(k, api_odds, match_odds)
        if s is not None:
            w = 0.5 if "Alt/Üst" in k else 1.0
            med_list.append((k, s, w))

    low_list = []
    high_keys = {n for (n,_,_) in high_list}
    for k in match_odds.keys():
        if k in (MS1,MSX,MS2) or k in high_keys or k in MED_KEYS:
            continue
        if ("Korner" in k) or ("Kart" in k):
            continue
        s = _bin_sim(k, api_odds, match_odds)
        if s is not None:
            low_list.append((k, s, 1.0))

    def wmean(items):
        sw = sum(w for _,_,w in items)
        if sw == 0: return None, 0
        return sum(s*w for _,s,w in items)/sw, len(items)

    high_sim, hn = wmean(high_list)
    med_sim,  mn = wmean(med_list)
    low_sim,  ln = wmean(low_list)

    def shrink(val, n, target):
        if val is None or n <= 0: return None
        f = math.sqrt(min(n, target)/float(target))
        return val * f

    high_sim = shrink(high_sim, hn, 6)
    med_sim  = shrink(med_sim,  mn, 6)
    low_sim  = shrink(low_sim,  ln, 6)

    W_HIGH, W_MED, W_LOW = 0.65, 0.25, 0.10
    total, wsum = 0.0, 0.0
    for sim, w in ((high_sim, W_HIGH), (med_sim, W_MED), (low_sim, W_LOW)):
        if sim is not None:
            total += sim*w; wsum += w
    if wsum == 0: return 0.0
    score = total/wsum

    anchors = 0
    def have(*keys): return all(k in api_odds and k in match_odds and _to_float(api_odds[k]) and _to_float(match_odds[k]) for k in keys)
    if have(MS1,MSX,MS2): anchors += 1
    if have(KG_V,KG_Y):   anchors += 1
    if have(O25U,O25A):   anchors += 1
    ah_has = any(k in match_odds for k in (
        "Handikaplı Maç Sonucu (-1,0) 1","Handikaplı Maç Sonucu (-1,0) X","Handikaplı Maç Sonucu (-1,0) 2",
        "Handikaplı Maç Sonucu (1,0) 1","Handikaplı Maç Sonucu (1,0) X","Handikaplı Maç Sonucu (1,0) 2"))
    if ah_has: anchors += 1
    if anchors < 2:
        score = min(score, 0.85)

    return round(score*100.0, 2)

# -----------------------------------------------------------
# TAHMİN KRİTERLERİ (v26 ile aynı mantık)  :contentReference[oaicite:14]{index=14}
# -----------------------------------------------------------
PREDICTION_CRITERIA = {
    # 1X2
    "Maç Sonucu 1": {
        "func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[0]) > int(r["MS SKOR"].split("-")[1]),
        "mtid": 1, "sov": None, "oca_key": "1", "display_name": "MS 1"
    },
    "Maç Sonucu X": {
        "func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[0]) == int(r["MS SKOR"].split("-")[1]),
        "mtid": 1, "sov": None, "oca_key": "2", "display_name": "MS X"
    },
    "Maç Sonucu 2": {
        "func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[0]) < int(r["MS SKOR"].split("-")[1]),
        "mtid": 1, "sov": None, "oca_key": "3", "display_name": "MS 2"
    },

    # KG
    "Karşılıklı Gol Var": {
        "func": lambda r: r.get("MS SKOR") and all(int(x) > 0 for x in r["MS SKOR"].split("-")),
        "mtid": 38, "sov": None, "oca_key": "1", "display_name": "KG Var"
    },
    "Karşılıklı Gol Yok": {
        "func": lambda r: r.get("MS SKOR") and any(int(x) == 0 for x in r["MS SKOR"].split("-")),
        "mtid": 38, "sov": None, "oca_key": "2", "display_name": "KG Yok"
    },

    # O/U merdiveni (0.5..4.5)
    "0,5 Alt/Üst Üst": {"func": lambda r: r.get("MS SKOR") and sum(map(int, r["MS SKOR"].split("-"))) > 0, "mtid": 321, "sov": 0.5, "oca_key": "2", "display_name": "Üst 0.5"},
    "1,5 Alt/Üst Üst": {"func": lambda r: r.get("MS SKOR") and sum(map(int, r["MS SKOR"].split("-"))) > 1, "mtid": 11,  "sov": 1.5, "oca_key": "2", "display_name": "Üst 1.5"},
    "2,5 Alt/Üst Üst": {"func": lambda r: r.get("MS SKOR") and sum(map(int, r["MS SKOR"].split("-"))) > 2, "mtid": 12,  "sov": 2.5, "oca_key": "2", "display_name": "Üst 2.5"},
    "3,5 Alt/Üst Üst": {"func": lambda r: r.get("MS SKOR") and sum(map(int, r["MS SKOR"].split("-"))) > 3, "mtid": 13,  "sov": 3.5, "oca_key": "2", "display_name": "Üst 3.5"},
    "4,5 Alt/Üst Üst": {"func": lambda r: r.get("MS SKOR") and sum(map(int, r["MS SKOR"].split("-"))) > 4, "mtid": 323, "sov": 4.5, "oca_key": "2", "display_name": "Üst 4.5"},
    "0,5 Alt/Üst Alt": {"func": lambda r: r.get("MS SKOR") and sum(map(int, r["MS SKOR"].split("-"))) < 1, "mtid": 321, "sov": 0.5, "oca_key": "1", "display_name": "Alt 0.5"},
    "1,5 Alt/Üst Alt": {"func": lambda r: r.get("MS SKOR") and sum(map(int, r["MS SKOR"].split("-"))) < 2, "mtid": 11,  "sov": 1.5, "oca_key": "1", "display_name": "Alt 1.5"},
    "2,5 Alt/Üst Alt": {"func": lambda r: r.get("MS SKOR") and sum(map(int, r["MS SKOR"].split("-"))) < 3, "mtid": 12,  "sov": 2.5, "oca_key": "1", "display_name": "Alt 2.5"},
    "3,5 Alt/Üst Alt": {"func": lambda r: r.get("MS SKOR") and sum(map(int, r["MS SKOR"].split("-"))) < 4, "mtid": 13,  "sov": 3.5, "oca_key": "1", "display_name": "Alt 3.5"},
    "4,5 Alt/Üst Alt": {"func": lambda r: r.get("MS SKOR") and sum(map(int, r["MS SKOR"].split("-"))) < 5, "mtid": 323, "sov": 4.5, "oca_key": "1", "display_name": "Alt 4.5"},

    # 1. Yarı 1X2
    "1. Yarı Sonucu 1": {
        "func": lambda r: r.get("IY SKOR") and int(r["IY SKOR"].split("-")[0]) > int(r["IY SKOR"].split("-")[1]),
        "mtid": 7, "sov": None, "oca_key": "1", "display_name": "İY 1"
    },
    "1. Yarı Sonucu X": {
        "func": lambda r: r.get("IY SKOR") and int(r["IY SKOR"].split("-")[0]) == int(r["IY SKOR"].split("-")[1]),
        "mtid": 7, "sov": None, "oca_key": "2", "display_name": "İY X"
    },
    "1. Yarı Sonucu 2": {
        "func": lambda r: r.get("IY SKOR") and int(r["IY SKOR"].split("-")[0]) < int(r["IY SKOR"].split("-")[1]),
        "mtid": 7, "sov": None, "oca_key": "3", "display_name": "İY 2"
    },

    # 2. Yarı 1X2
    "2. Yarı Sonucu 1": {
        "func": lambda r: r.get("MS SKOR") and r.get("IY SKOR") and
                          (int(r["MS SKOR"].split("-")[0]) - int(r["IY SKOR"].split("-")[0])) >
                          (int(r["MS SKOR"].split("-")[1]) - int(r["IY SKOR"].split("-")[1])),
        "mtid": 9, "sov": None, "oca_key": "1", "display_name": "2Y 1"
    },
    "2. Yarı Sonucu X": {
        "func": lambda r: r.get("MS SKOR") and r.get("IY SKOR") and
                          (int(r["MS SKOR"].split("-")[0]) - int(r["IY SKOR"].split("-")[0])) ==
                          (int(r["MS SKOR"].split("-")[1]) - int(r["IY SKOR"].split("-")[1])),
        "mtid": 9, "sov": None, "oca_key": "2", "display_name": "2Y X"
    },
    "2. Yarı Sonucu 2": {
        "func": lambda r: r.get("MS SKOR") and r.get("IY SKOR") and
                          (int(r["MS SKOR"].split("-")[0]) - int(r["IY SKOR"].split("-")[0])) <
                          (int(r["MS SKOR"].split("-")[1]) - int(r["IY SKOR"].split("-")[1])),
        "mtid": 9, "sov": None, "oca_key": "3", "display_name": "2Y 2"
    },

    # Takım toplam golleri (0.5 / 1.5 / 2.5)
    "Evsahibi 0,5 Alt/Üst Üst": {"func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[0]) > 0, "mtid": 327, "sov": 0.5, "oca_key": "2", "display_name": "Ev 0.5 Üst"},
    "Evsahibi 1,5 Alt/Üst Üst": {"func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[0]) > 1, "mtid": 20,  "sov": 1.5, "oca_key": "2", "display_name": "Ev 1.5 Üst"},
    "Evsahibi 2,5 Alt/Üst Üst": {"func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[0]) > 2, "mtid": 327, "sov": 2.5, "oca_key": "2", "display_name": "Ev 2.5 Üst"},
    "Evsahibi 0,5 Alt/Üst Alt": {"func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[0]) < 1, "mtid": 327, "sov": 0.5, "oca_key": "1", "display_name": "Ev 0.5 Alt"},
    "Evsahibi 1,5 Alt/Üst Alt": {"func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[0]) < 2, "mtid": 20,  "sov": 1.5, "oca_key": "1", "display_name": "Ev 1.5 Alt"},
    "Evsahibi 2,5 Alt/Üst Alt": {"func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[0]) < 3, "mtid": 327, "sov": 2.5, "oca_key": "1", "display_name": "Ev 2.5 Alt"},

    "Deplasman 0,5 Alt/Üst Üst": {"func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[1]) > 0, "mtid": 328, "sov": 0.5, "oca_key": "2", "display_name": "Dep 0.5 Üst"},
    "Deplasman 1,5 Alt/Üst Üst": {"func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[1]) > 1, "mtid": 29,  "sov": 1.5, "oca_key": "2", "display_name": "Dep 1.5 Üst"},
    "Deplasman 2,5 Alt/Üst Üst": {"func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[1]) > 2, "mtid": 328, "sov": 2.5, "oca_key": "2", "display_name": "Dep 2.5 Üst"},
    "Deplasman 0,5 Alt/Üst Alt": {"func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[1]) < 1, "mtid": 328, "sov": 0.5, "oca_key": "1", "display_name": "Dep 0.5 Alt"},
    "Deplasman 1,5 Alt/Üst Alt": {"func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[1]) < 2, "mtid": 29,  "sov": 1.5, "oca_key": "1", "display_name": "Dep 1.5 Alt"},
    "Deplasman 2,5 Alt/Üst Alt": {"func": lambda r: r.get("MS SKOR") and int(r["MS SKOR"].split("-")[1]) < 3, "mtid": 328, "sov": 2.5, "oca_key": "1", "display_name": "Dep 2.5 Alt"},

    # AH ±1 temel
    "Handikaplı Maç Sonucu (-1,0) 1": {
        "func": lambda r: r.get("MS SKOR") and (int(r["MS SKOR"].split("-")[0]) - int(r["MS SKOR"].split("-")[1])) >= 2,
        "mtid": 308, "sov": None, "oca_key": "1", "display_name": "AH(-1) 1"
    },
    "Handikaplı Maç Sonucu (1,0) 2": {
        "func": lambda r: r.get("MS SKOR") and (int(r["MS SKOR"].split("-")[1]) - int(r["MS SKOR"].split("-")[0])) >= 2,
        "mtid": 312, "sov": None, "oca_key": "3", "display_name": "AH(+1) 2"
    },
}

def predictions_for_match(group_rows, api_row):
    """v26 mantığı: skor yoğunluğu + kriter %>=80 ise tahmine ekle; oransa MA’dan çek.  :contentReference[oaicite:15]{index=15}"""
    preds = []
    match_rows = [r for r in group_rows if r and r.get("Benzerlik (%)") not in (None, "",) and r.get("MS SKOR")]
    if not match_rows:
        return preds

    # Skor kümelenmesi (çoğunluk skoru %65+ ise ayrı yaz)
    from collections import Counter
    ms_scores = [r["MS SKOR"] for r in match_rows if r.get("MS SKOR")]
    if ms_scores:
        c = Counter(ms_scores)
        for sc, cnt in c.items():
            if cnt / len(match_rows) >= 0.65:
                preds.append(f"Maç Skoru {sc}: {cnt/len(match_rows)*100:.1f}%")

    # Diğer kriterler
    for name, info in PREDICTION_CRITERIA.items():
        req_mtid = info["mtid"]; req_sov = info["sov"]; req_oca = str(info["oca_key"])
        # MTID var mı?
        if req_mtid not in api_row.get("MTIDs", []):
            continue
        # SOV kontrolü (gerekliyse)
        if req_sov is not None:
            sov_ok = False
            for m in api_row.get("MA", []):
                if int(m.get("MTID", -1)) == req_mtid:
                    try:
                        if float(m.get("SOV", 0)) == float(req_sov):
                            sov_ok = True
                            break
                    except Exception:
                        pass
            if not sov_ok:
                continue

        # Yüzde
        cnt = sum(1 for r in match_rows if info["func"](r))
        pct = 100.0 * cnt / len(match_rows) if match_rows else 0.0
        if pct < 80.0:
            continue

        # Oran bul
        odds = None
        for m in api_row.get("MA", []):
            if int(m.get("MTID", -1)) != req_mtid:
                continue
            for oca in m.get("OCA", []) or m.get("OC", []):
                if str(oca.get("N", "")).strip() == req_oca:
                    odds = oca.get("O")
                    break
            if odds is not None:
                break

        label = info.get("display_name", name)
        if odds is not None:
            try:
                preds.append(f"{label}: {pct:.1f}% (Oran {float(odds):.2f})")
            except Exception:
                preds.append(f"{label}: {pct:.1f}%")
        else:
            preds.append(f"{label}: {pct:.1f}%")

    return preds[:5]

# -----------------------------------------------------------
# ANA AKIŞ
# -----------------------------------------------------------
if run:
    try:
        with st.spinner("Veriler yükleniyor..."):
            df_data = load_matches_df()
            mtid_map, league_map = load_mappings()
            api_json = fetch_api_json()
    except Exception as e:
        st.error(f"Kaynaklar yüklenemedi: {e}")
        st.stop()

    api_rows = parse_api_to_rows(api_json, default_start, end_dt, mtid_map, league_map)

    if not api_rows:
        st.warning("API verisi boş döndü (zaman aralığında maç bulunamadı).")
        st.stop()

    # ÇIKTI TABLOSU KURULUMU
    OUTPUT_COLUMNS = ["Benzerlik (%)", "Saat", "Tarih", "Ev Sahibi Takım",
                      "Deplasman Takım", "Lig Adı", "IY SKOR", "MS SKOR", "Tahmin"]
    output = []

    # Analiz – her API maçı için
    # Hız için: global aday sayısını sınırla ve v26 filtreleri uygula
    df = df_data.copy()
    # Temel temizlik
    for col in ("Saat","Tarih"):
        if col in df.columns:
            df[col] = df[col].astype(str)
    # MS/IY skorlar metin "x-y" formatında bekleniyor
    # Pazar kolonları numerik
    for c in EXCEL_COLUMNS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    for api in api_rows:
        # MA -> odds
        api_odds = odds_from_MA(api.get("MA", []), mtid_map)

        # Başlık satırı (Benzerlik boş)
        header = {
            "Benzerlik (%)": "",
            "Saat": api["Saat"], "Tarih": api["Tarih"],
            "Ev Sahibi Takım": api["Ev Sahibi Takım"],
            "Deplasman Takım": api["Deplasman Takım"],
            "Lig Adı": api["Lig Adı"],
            "IY SKOR": "", "MS SKOR": "", "Tahmin": "",  # skor yok, sadece grup başlığı
            "MA": api.get("MA", []), "MTIDs": api.get("MTIDs", [])
        }
        output.append(header)

        # Lig adını kullanarak önce lig-içi veri
        league_mask = (df["Lig Adı"] == api["Lig Adı"]) if "Lig Adı" in df.columns else pd.Series([False]*len(df))
        data_league = df[league_mask].copy()
        data_global = df[~league_mask].copy()

        # Aday daraltma – pazar kesişimi
        api_cols = {k for k in EXCEL_COLUMNS if k in api_odds and pd.notna(api_odds[k])}
        if len(api_cols) == 0:
            output.append({})  # grup sonu
            continue

        def top_matches_from_block(block_df, same_league: bool, limit_return: int):
            # Ortak pazar sayısı eşiği (%30)
            out_rows = []
            for _, row in block_df.iterrows():
                row_odds = {c: row[c] for c in EXCEL_COLUMNS if c in row and pd.notna(row[c])}
                if not row_odds:
                    continue
                # minimum ortak pazar
                if len(api_cols.intersection(row_odds.keys())) < max(1, int(len(api_cols)*0.3)):
                    continue
                if not quality_filter(api_odds, row_odds):
                    continue
                sim = calculate_similarity(api_odds, row_odds)
                if sim <= 0:
                    continue
                try:
                    saat = str(row.get("Saat",""))
                    tarih= str(row.get("Tarih",""))
                    iy   = str(row.get("IY SKOR",""))
                    ms   = str(row.get("MS SKOR",""))
                except Exception:
                    continue
                out_rows.append({
                    "Benzerlik (%)": f"{sim:.2f}%",
                    "Saat": saat, "Tarih": tarih,
                    "Ev Sahibi Takım": row.get("Ev Sahibi Takım",""),
                    "Deplasman Takım": row.get("Deplasman Takım",""),
                    "Lig Adı": row.get("Lig Adı",""),
                    "IY SKOR": iy, "MS SKOR": ms,
                })
            # Sırala: önce benzerlik, sonra tarih
            out_rows.sort(key=lambda r: (-(float(r["Benzerlik (%)"].strip('%'))), r.get("Tarih",""), r.get("Saat","")))
            return out_rows[:limit_return]

        # v26: önce lig içi (en fazla 7), sonra global (en fazla 3)  :contentReference[oaicite:16]{index=16}
        top_league  = top_matches_from_block(data_league, True, 7)
        top_global  = top_matches_from_block(data_global, False, 3)
        group_rows  = top_league + top_global

        # Tahminler
        tahmin_list = predictions_for_match(group_rows, header)
        header["Tahmin"] = " • ".join(tahmin_list) if tahmin_list else ""
        # Header’ı güncel yaz (çıktıda ilk satır header’dı)
        output[-1] = header

        # Maç satırlarını ekle
        output.extend(group_rows)
        # Grup ayraç boş satır
        output.append({})

    # DataFrame’e dök (boş ayraçları dışarıda bırak)
    out_df = pd.DataFrame([r for r in output if r])
    if out_df.empty:
        st.info("Seçilen aralık için benzer maç bulunamadı.")
    else:
        st.dataframe(out_df[["Benzerlik (%)","Saat","Tarih","Ev Sahibi Takım","Deplasman Takım","Lig Adı","IY SKOR","MS SKOR","Tahmin"]],
                     use_container_width=True)
