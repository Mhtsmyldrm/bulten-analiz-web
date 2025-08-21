# app.py
# -*- coding: utf-8 -*-

import io
import json
import math
import re
import requests
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone
from collections import Counter

# =========================
# Sayfa ve başlık (yan panel gizli)
# =========================
st.set_page_config(page_title="Bülten Analiz",
                   layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] {display:none;}
    footer {visibility:hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Bülten Analiz")

IST = timezone(timedelta(hours=3))

# =========================
# UI — Eski düzen
# =========================
now = datetime.now(IST).replace(second=0, microsecond=0)
default_start = now + timedelta(minutes=5)
st.subheader("Analiz için Saat Aralığı")
st.caption(f"Başlangıç Saati: {default_start.strftime('%d.%m.%Y %H:%M')} (Otomatik, şu an + 5 dakika)")
col1, col2 = st.columns(2)
with col1:
    end_date = st.date_input("Bitiş Tarihi", value=now.date(), format="YYYY/MM/DD")
with col2:
    end_time = st.time_input("Bitiş Saati", value=None)
run = st.button("Analiz Et", use_container_width=True)

if not run:
    st.stop()

if end_time is None:
    st.error("Lütfen bitiş saati seçin!")
    st.stop()

end_dt = datetime.combine(end_date, end_time).replace(tzinfo=IST)
if end_dt <= default_start:
    st.error("Bitiş saati başlangıç saatinden büyük olmalı!")
    st.stop()

# =========================
# Kaynak linkleri (sabit)
# =========================
MATCHES_SHEET_URL = "https://docs.google.com/spreadsheets/d/11m7tX2xCavCM_cij69UaSVijFuFQbveM/edit?usp=drive_link"
LEAGUE_JSON_URL   = "https://drive.google.com/file/d/1L8HA_emD92BJSuCn-P9GJF-hH55nIKE7/view?usp=drive_link"
MTID_JSON_URL     = "https://drive.google.com/file/d/1N1PjFla683BYTAdzVDaajmcnmMB5wiiO/view?usp=drive_link"

# =========================
# Drive yardımcıları (tamamen bellek içi)
# =========================
def _extract_drive_id(url: str) -> str:
    if "drive.google.com/file/d/" in url:
        return url.split("/file/d/")[1].split("/")[0]
    if "docs.google.com/spreadsheets/d/" in url:
        return url.split("/spreadsheets/d/")[1].split("/")[0]
    return url  # doğrudan id verildiyse

def _http_get(url, session=None, **kw):
    s = session or requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
    }
    r = s.get(url, headers=headers, timeout=kw.get("timeout", 30))
    r.raise_for_status()
    return r

@st.cache_data(show_spinner=False)
def download_sheet_as_xlsx_bytes(sheet_url: str) -> bytes | None:
    """
    1) export?format=xlsx
    2) uc?export=download&id=
    Başarısızsa None döner (kullanıcıdan upload isteriz).
    """
    fid = _extract_drive_id(sheet_url)
    s = requests.Session()
    # 1) resmi export
    try:
        url = f"https://docs.google.com/spreadsheets/d/{fid}/export?format=xlsx"
        r = _http_get(url, session=s, timeout=60)
        content = r.content
        # HTML uyarısı gelirse bytes çok küçük olur
        if len(content) > 1024:
            return content
    except Exception:
        pass
    # 2) uc?export=download (confirm cookie)
    try:
        base = "https://docs.google.com/uc?export=download"
        r1 = _http_get(base, session=s, timeout=30)
        r2 = _http_get(f"{base}&id={fid}", session=s, timeout=60)
        token = None
        for k, v in r2.cookies.items():
            if k.startswith("download_warning"):
                token = v
        if token:
            r3 = _http_get(f"{base}&confirm={token}&id={fid}", session=s, timeout=60)
            if len(r3.content) > 1024:
                return r3.content
    except Exception:
        pass
    return None

@st.cache_data(show_spinner=False)
def download_json(url: str) -> dict:
    fid = _extract_drive_id(url)
    # Drive raw (uc?export=download) dene
    s = requests.Session()
    try:
        base = "https://docs.google.com/uc?export=download"
        r = _http_get(f"{base}&id={fid}", session=s, timeout=30)
        token = None
        for k, v in r.cookies.items():
            if k.startswith("download_warning"):
                token = v
        if token:
            r = _http_get(f"{base}&confirm={token}&id={fid}", session=s, timeout=30)
        return r.json()
    except Exception:
        # file API (view link) → uc id
        r = requests.get(f"https://drive.google.com/uc?id={fid}", timeout=30)
        r.raise_for_status()
        return r.json()

# =========================
# Excel kolonları (v26 ile uyumlu çekirdek)
# =========================
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
    "Toplam Gol Aralığı 0-1 Gol", "Toplam Gol Aralığı 2-3 Gol", "Toplam Gol Aralığı 4-5 Gol", "Toplam Gol Aralığı 6+ Gol",
    "Evsahibi 0,5 Alt/Üst Alt", "Evsahibi 0,5 Alt/Üst Üst",
    "Evsahibi 1,5 Alt/Üst Alt", "Evsahibi 1,5 Alt/Üst Üst",
    "Evsahibi 2,5 Alt/Üst Alt", "Evsahibi 2,5 Alt/Üst Üst",
    "Deplasman 0,5 Alt/Üst Alt", "Deplasman 0,5 Alt/Üst Üst",
    "Deplasman 1,5 Alt/Üst Alt", "Deplasman 1,5 Alt/Üst Üst",
    "Deplasman 2,5 Alt/Üst Alt", "Deplasman 2,5 Alt/Üst Üst",
    "Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2",
    "Handikaplı Maç Sonucu (1,0) 1",  "Handikaplı Maç Sonucu (1,0) X",  "Handikaplı Maç Sonucu (1,0) 2",
]

CRITICAL_MARKETS = {
    "Maç Sonucu 1","Maç Sonucu X","Maç Sonucu 2",
    "2,5 Alt/Üst Alt","2,5 Alt/Üst Üst",
    "Karşılıklı Gol Var","Karşılıklı Gol Yok",
    "1. Yarı Sonucu 1","1. Yarı Sonucu X","1. Yarı Sonucu 2",
}
IMPORTANT_MARKETS = {
    "0,5 Alt/Üst Alt","0,5 Alt/Üst Üst",
    "1,5 Alt/Üst Alt","1,5 Alt/Üst Üst",
    "3,5 Alt/Üst Alt","3,5 Alt/Üst Üst",
    "Handikaplı Maç Sonucu (-1,0) 1","Handikaplı Maç Sonucu (-1,0) X","Handikaplı Maç Sonucu (-1,0) 2",
}
OTHER_MARKETS = set(EXCEL_COLUMNS) - CRITICAL_MARKETS - IMPORTANT_MARKETS

# =========================
# Mappings (Drive JSON → mapping ve reverse)
# =========================
@st.cache_data(show_spinner=False)
def load_mappings():
    league_data = download_json(LEAGUE_JSON_URL)
    league_mapping = {}
    for k, v in league_data.items():
        try: league_mapping[int(k)] = v
        except: pass

    mtid_data = download_json(MTID_JSON_URL)
    mtid_mapping = {}
    reverse_mapping = {}
    for key_str, value in mtid_data.items():
        if not (isinstance(key_str, str) and key_str.startswith("(") and key_str.endswith(")")):
            continue
        parts = key_str[1:-1].split(",")
        if len(parts) != 2:
            continue
        try:
            mtid = int(parts[0].strip()); sov_raw = parts[1].strip()
            sov = None if sov_raw.lower() == "null" else float(sov_raw)
        except Exception:
            continue
        if not isinstance(value, list):
            continue
        mtid_mapping[(mtid, sov)] = value
        for i, col_name in enumerate(value, start=1):
            if isinstance(col_name, str):
                reverse_mapping[col_name] = {"mtid": mtid, "sov": sov, "oca_key": str(i)}
    return league_mapping, mtid_mapping, reverse_mapping

# =========================
# Geçmiş maçlar (Excel)
# =========================
uploaded_backup = st.file_uploader("İndirme problemi olursa buradan matches.xlsx yükleyin", type=["xlsx"], accept_multiple_files=False)

@st.cache_data(show_spinner=False)
def load_matches_df(sheet_url: str, uploaded) -> pd.DataFrame:
    if uploaded is not None:
        content = uploaded.read()
    else:
        content = download_sheet_as_xlsx_bytes(sheet_url)
        if content is None:
            # indirme başarısız; kullanıcıdan upload bekle
            return pd.DataFrame()
    bio = io.BytesIO(content)
    df = pd.read_excel(bio, dtype=str)  # sayfa adı verilmişse otomatik algılıyor
    # odds kolonları numerik
    for c in EXCEL_COLUMNS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            df[c] = df[c].where(df[c] > 1.0, np.nan)
    return df

# =========================
# Nesine API — iki şemayı da destekleyen çekici
# =========================
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nesine.com/",
}

@st.cache_data(show_spinner=False)
def fetch_api_json() -> dict:
    # v26 yeni şema (sg.EA)
    try:
        url1 = "https://bulten.nesine.com/api/bulten/getprebultendelta"
        r = requests.get(url1, headers=HEADERS, timeout=25)
        r.raise_for_status()
        j = r.json()
        if isinstance(j, dict) and (j.get("sg", {}).get("EA") or j.get("Data", {}).get("EventList")):
            return j
    except Exception:
        pass
    # yedek (aynı uç – bazı ortamlarda farklı gövde)
    try:
        r = requests.get("https://bulten.nesine.com/api/bulten/getprebulten", headers=HEADERS, timeout=25)
        r.raise_for_status()
        j = r.json()
        if isinstance(j, dict):
            return j
    except Exception:
        pass
    return {}

def parse_api_to_rows(api_json: dict, start_dt: datetime, end_dt: datetime, league_mapping: dict):
    rows = []
    # 1) yeni şema
    ea = api_json.get("sg", {}).get("EA") or []
    for m in ea:
        try:
            d, t = m.get("D",""), m.get("T","")
            dtm = datetime.strptime(f"{d} {t}", "%d.%m.%Y %H:%M").replace(tzinfo=IST)
        except Exception:
            continue
        if not (start_dt <= dtm <= end_dt): continue
        L = m.get("L", None)
        lig = league_mapping.get(int(L), str(L)) if L is not None else ""
        rows.append({
            "Saat": dtm.strftime("%H:%M"), "Tarih": dtm.strftime("%d.%m.%Y"),
            "Ev Sahibi Takım": (m.get("H","") or "").strip(),
            "Deplasman Takım": (m.get("A","") or "").strip(),
            "Lig Adı": lig,
            "MA": m.get("MA", []) or [],
        })
    if rows:
        return rows
    # 2) eski şema
    ev = api_json.get("Data", {}).get("EventList", []) or []
    for m in ev:
        d = m.get("D") or m.get("EventDate") or ""
        t = m.get("T") or m.get("EventTime") or ""
        fmt = "%Y-%m-%d %H:%M" if "-" in d else "%d.%m.%Y %H:%M"
        try:
            dtm = datetime.strptime(f"{d} {t}", fmt).replace(tzinfo=IST)
        except Exception:
            continue
        if not (start_dt <= dtm <= end_dt): continue
        L = m.get("L") or m.get("LeagueId")
        lig = league_mapping.get(int(L), str(L)) if L is not None else ""
        rows.append({
            "Saat": dtm.strftime("%H:%M"), "Tarih": dtm.strftime("%d.%m.%Y"),
            "Ev Sahibi Takım": (m.get("H") or m.get("HomeTeamName") or "").strip(),
            "Deplasman Takım": (m.get("A") or m.get("AwayTeamName") or "").strip(),
            "Lig Adı": lig,
            "MA": m.get("MA") or m.get("Markets") or [],
        })
    return rows

# =========================
# Oran sözlüğü üretimi (MA → EXCEL_COLUMNS)
# =========================
def odds_from_MA(ma_list: list, mtid_mapping: dict) -> dict:
    out = {}
    for mk in ma_list or []:
        mtid = mk.get("MTID")
        sov  = mk.get("SOV", None)
        try:
            sov_key = None if sov in (None, "", "null") else float(sov)
        except Exception:
            sov_key = None
        names = mtid_mapping.get((int(mtid), sov_key), []) if mtid is not None else []
        if not names:
            continue
        oca = mk.get("OCA", []) or mk.get("OC", []) or []
        if not isinstance(oca, list):
            continue
        for idx, col_name in enumerate(names, start=1):
            sel = None
            # öncelikle N alanı eşleşmesi
            for item in oca:
                if str(item.get("N","")).strip() == str(idx):
                    sel = item; break
            if sel is None and idx-1 < len(oca):
                sel = oca[idx-1]
            if sel is not None:
                try:
                    odd = float(sel.get("O"))
                except Exception:
                    continue
                out[col_name] = odd
    return out

# =========================
# Benzerlik (v26 mantığı, optimize kapılar)
# =========================
def _to_float(x):
    try: return float(x)
    except: return None

def _prob(odd):
    odd = _to_float(odd)
    if odd is None or odd <= 1.0: return None
    return 1.0/odd

def _fair_trio(d, k1, kx, k2):
    p1, px, p2 = _prob(d.get(k1)), _prob(d.get(kx)), _prob(d.get(k2))
    if None in (p1, px, p2): return None
    s = p1+px+p2
    if s <= 0: return None
    return (p1/s, px/s, p2/s)

def _rel(a,b):
    if a is None or b is None or a<=0 or b<=0: return None
    return abs(a-b)/((a+b)/2.0)

def _bin_sim(key, A, B):
    if key not in A or key not in B: return None
    pa, pb = _prob(A[key]), _prob(B[key])
    d = _rel(pa,pb)
    if d is None: return None
    return math.exp(-3.5*d)

def hellinger_trio(p,q):
    return max(0.0, 1.0 - (math.sqrt(
        (math.sqrt(p[0])-math.sqrt(q[0]))**2 +
        (math.sqrt(p[1])-math.sqrt(q[1]))**2 +
        (math.sqrt(p[2])-math.sqrt(q[2]))**2
    )/math.sqrt(2.0)))

def calculate_similarity(api_odds: dict, match_odds: dict) -> float:
    MS1,MSX,MS2 = "Maç Sonucu 1","Maç Sonucu X","Maç Sonucu 2"
    KG_V,KG_Y   = "Karşılıklı Gol Var","Karşılıklı Gol Yok"
    O25A,O25U   = "2,5 Alt/Üst Alt","2,5 Alt/Üst Üst"

    A = _fair_trio(api_odds, MS1,MSX,MS2)
    B = _fair_trio(match_odds, MS1,MSX,MS2)
    if not A or not B: return 0.0

    base = hellinger_trio(A,B)
    if base < 0.85: return base*100.0
    # bacak başı tolerans
    for a,b in zip(A,B):
        d=_rel(a,b)
        if d is None or d>0.12: return base*100.0

    high = [("__MS__", base, 1.0)]
    for k in (KG_V,KG_Y,O25A,O25U):
        s=_bin_sim(k, api_odds, match_odds)
        if s is not None: high.append((k,s,1.0))
    for k in ("Çifte Şans 1 veya X","Çifte Şans 1 veya 2","Çifte Şans X veya 2"):
        s=_bin_sim(k, api_odds, match_odds)
        if s is not None: high.append((k,s,0.5))
    for k in ("Handikaplı Maç Sonucu (-1,0) 1","Handikaplı Maç Sonucu (-1,0) X","Handikaplı Maç Sonucu (-1,0) 2",
              "Handikaplı Maç Sonucu (1,0) 1","Handikaplı Maç Sonucu (1,0) X","Handikaplı Maç Sonucu (1,0) 2"):
        s=_bin_sim(k, api_odds, match_odds)
        if s is not None: high.append((k,s,1.0))

    MED = [
        "1. Yarı Sonucu 1","1. Yarı Sonucu X","1. Yarı Sonucu 2",
        "0,5 Alt/Üst Alt","0,5 Alt/Üst Üst",
        "1,5 Alt/Üst Alt","1,5 Alt/Üst Üst",
        "3,5 Alt/Üst Alt","3,5 Alt/Üst Üst",
        "4,5 Alt/Üst Alt","4,5 Alt/Üst Üst",
        "2. Yarı Sonucu 1","2. Yarı Sonucu X","2. Yarı Sonucu 2",
        "Toplam Gol Aralığı 0-1 Gol","Toplam Gol Aralığı 2-3 Gol","Toplam Gol Aralığı 4-5 Gol","Toplam Gol Aralığı 6+ Gol",
    ]
    med=[]
    for k in MED:
        s=_bin_sim(k, api_odds, match_odds)
        if s is not None: med.append((k,s,0.5 if "Alt/Üst" in k else 1.0))

    low=[]
    used={n for n,_,_ in high} | set(MED) | {MS1,MSX,MS2}
    for k in match_odds.keys():
        if k in used: continue
        if ("Korner" in k) or ("Kart" in k): continue
        s=_bin_sim(k, api_odds, match_odds)
        if s is not None: low.append((k,s,1.0))

    def wmean(items):
        sw=sum(w for *_,w in items)
        return (sum(s*w for _,s,w in items)/sw if sw else None, len(items))
    def shrink(v,n,t=6):
        if v is None or n<=0: return None
        f=math.sqrt(min(n,t)/t)
        return v*f

    h,hn=wmean(high); m,mn=wmean(med); l,ln=wmean(low)
    h=shrink(h,hn); m=shrink(m,mn); l=shrink(l,ln)
    total,ws=0.0,0.0
    for sim,w in ((h,0.65),(m,0.25),(l,0.10)):
        if sim is not None: total+=sim*w; ws+=w
    score = total/ws if ws else base

    anchors=0
    def have(*ks): return all(k in api_odds and k in match_odds and _to_float(api_odds[k]) and _to_float(match_odds[k]) for k in ks)
    if have(MS1,MSX,MS2): anchors+=1
    if have(KG_V,KG_Y):   anchors+=1
    if have(O25A,O25U):   anchors+=1
    if any(k in match_odds for k in ("Handikaplı Maç Sonucu (-1,0) 1","Handikaplı Maç Sonucu (1,0) 1")): anchors+=1
    if anchors<2: score=min(score,0.85)
    return float(score*100.0)

def quality_filter(api_odds: dict, data_odds: dict) -> bool:
    api_cnt  = sum(1 for c in EXCEL_COLUMNS if c in api_odds and pd.notna(api_odds[c]))
    data_cnt = sum(1 for c in EXCEL_COLUMNS if c in data_odds and pd.notna(data_odds[c]))
    if data_cnt < api_cnt*0.7: return False
    crit = sum(1 for m in CRITICAL_MARKETS if m in data_odds and pd.notna(data_odds[m]))
    if crit < max(1, int(len(CRITICAL_MARKETS)*0.5)): return False
    return True

# =========================
# Prediction kriterleri (geniş set; v26 ile uyumlu isimler)
# =========================
def _score(row, key):
    s = str(row.get(key,"") or "").strip()
    if not s or "-" not in s: return None
    try:
        a,b = s.split("-"); return int(a), int(b)
    except Exception:
        return None

def _iy(row): return _score(row, "IY SKOR")
def _ms(row): return _score(row, "MS SKOR")

def build_prediction_criteria():
    crit = {}
    # 1X2
    crit["Maç Sonucu 1"] = {"func": lambda r: (_ms(r) and (_ms(r)[0] >  _ms(r)[1]))}
    crit["Maç Sonucu X"] = {"func": lambda r: (_ms(r) and (_ms(r)[0] == _ms(r)[1]))}
    crit["Maç Sonucu 2"] = {"func": lambda r: (_ms(r) and (_ms(r)[0] <  _ms(r)[1]))}
    # KG
    crit["Karşılıklı Gol Var"] = {"func": lambda r: (_ms(r) and (_ms(r)[0]>0 and _ms(r)[1]>0))}
    crit["Karşılıklı Gol Yok"] = {"func": lambda r: (_ms(r) and (_ms(r)[0]==0 or  _ms(r)[1]==0))}
    # O/U 0.5..4.5
    for val in [0.5,1.5,2.5,3.5,4.5]:
        crit[f"{val:.1f} Alt/Üst Üst".replace(".",",")] = {"func": lambda r, v=val: (_ms(r) and (_ms(r)[0]+_ms(r)[1] > int(v)))}
        crit[f"{val:.1f} Alt/Üst Alt".replace(".",",")] = {"func": lambda r, v=val: (_ms(r) and (_ms(r)[0]+_ms(r)[1] < int(v)+1))}
    # 1. yarı 1X2
    crit["1. Yarı Sonucu 1"] = {"func": lambda r: (_iy(r) and (_iy(r)[0] >  _iy(r)[1]))}
    crit["1. Yarı Sonucu X"] = {"func": lambda r: (_iy(r) and (_iy(r)[0] == _iy(r)[1]))}
    crit["1. Yarı Sonucu 2"] = {"func": lambda r: (_iy(r) and (_iy(r)[0] <  _iy(r)[1]))}
    # 1. yarı O/U 0.5,1.5,2.5
    for val in [0.5,1.5,2.5]:
        crit[f"1. Yarı {val:.1f} Alt/Üst Üst".replace(".",",")] = {"func": lambda r, v=val: (_iy(r) and (_iy(r)[0]+_iy(r)[1] > int(v)))}
        crit[f"1. Yarı {val:.1f} Alt/Üst Alt".replace(".",",")] = {"func": lambda r, v=val: (_iy(r) and (_iy(r)[0]+_iy(r)[1] < int(v)+1))}
    # 2. yarı 1X2
    crit["2. Yarı Sonucu 1"] = {"func": lambda r: (_iy(r) and _ms(r) and ((_ms(r)[0]-_iy(r)[0]) >  (_ms(r)[1]-_iy(r)[1])))}
    crit["2. Yarı Sonucu X"] = {"func": lambda r: (_iy(r) and _ms(r) and ((_ms(r)[0]-_iy(r)[0]) == (_ms(r)[1]-_iy(r)[1])))}
    crit["2. Yarı Sonucu 2"] = {"func": lambda r: (_iy(r) and _ms(r) and ((_ms(r)[0]-_iy(r)[0]) <  (_ms(r)[1]-_iy(r)[1])))}
    # 1Y KG ve 2Y KG
    crit["İlk Yarı Karşılıklı Gol Var"] = {"func": lambda r: (_iy(r) and (_iy(r)[0]>0 and _iy(r)[1]>0))}
    crit["İlk Yarı Karşılıklı Gol Yok"] = {"func": lambda r: (_iy(r) and (_iy(r)[0]==0 or _iy(r)[1]==0))}
    crit["2. Yarı KG Var"] = {"func": lambda r: (_iy(r) and _ms(r) and ((_ms(r)[0]-_iy(r)[0])>0 and (_ms(r)[1]-_iy(r)[1])>0))}
    crit["2. Yarı KG Yok"] = {"func": lambda r: (_iy(r) and _ms(r) and ((_ms(r)[0]-_iy(r)[0])==0 or (_ms(r)[1]-_iy(r)[1])==0))}
    # Takım toplam (0.5/1.5/2.5)
    for side, label in [(0,"Evsahibi"), (1,"Deplasman")]:
        for v in [0.5,1.5,2.5]:
            crit[f"{label} {v:.1f} Alt/Üst Üst".replace(".",",")] = {"func": (lambda r, s=side, t=v: (_ms(r) and (_ms(r)[s] > int(t))))}
            crit[f"{label} {v:.1f} Alt/Üst Alt".replace(".",",")] = {"func": (lambda r, s=side, t=v: (_ms(r) and (_ms(r)[s] < int(t)+1)))}
    # Kombinasyon örnekleri (MS & KG)
    crit["Maç Sonucu 1 ve KG Var"] = {"func": lambda r: (crit["Maç Sonucu 1"]["func"](r) and crit["Karşılıklı Gol Var"]["func"](r))}
    crit["Maç Sonucu X ve KG Var"] = {"func": lambda r: (crit["Maç Sonucu X"]["func"](r) and crit["Karşılıklı Gol Var"]["func"](r))}
    crit["Maç Sonucu 2 ve KG Var"] = {"func": lambda r: (crit["Maç Sonucu 2"]["func"](r) and crit["Karşılıklı Gol Var"]["func"](r))}
    crit["Maç Sonucu 1 ve KG Yok"] = {"func": lambda r: (crit["Maç Sonucu 1"]["func"](r) and crit["Karşılıklı Gol Yok"]["func"](r))}
    crit["Maç Sonucu X ve KG Yok"] = {"func": lambda r: (crit["Maç Sonucu X"]["func"](r) and crit["Karşılıklı Gol Yok"]["func"](r))}
    crit["Maç Sonucu 2 ve KG Yok"] = {"func": lambda r: (crit["Maç Sonucu 2"]["func"](r) and crit["Karşılıklı Gol Yok"]["func"](r))}
    # Kombinasyon örnekleri (2.5 & KG)
    crit["2,5 Üst ve KG Var"] = {"func": lambda r: (crit["2,5 Alt/Üst Üst"]["func"](r) and crit["Karşılıklı Gol Var"]["func"](r))}
    crit["2,5 Üst ve KG Yok"] = {"func": lambda r: (crit["2,5 Alt/Üst Üst"]["func"](r) and crit["Karşılıklı Gol Yok"]["func"](r))}
    # AH ±1 (basit skor kuralları)
    crit["Handikaplı Maç Sonucu (-1,0) 1"] = {"func": lambda r: (_ms(r) and ((_ms(r)[0]-_ms(r)[1]) >= 2))}
    crit["Handikaplı Maç Sonucu (1,0) 2"]  = {"func": lambda r: (_ms(r) and ((_ms(r)[1]-_ms(r)[0]) >= 2))}
    return crit

# =========================
# Tahmin üretimi
# =========================
def reverse_map_from_mtid(mtid_mapping: dict):
    rev = {}
    for (mtid, sov), cols in mtid_mapping.items():
        for i, name in enumerate(cols, start=1):
            rev[name] = {"mtid": mtid, "sov": sov, "oca_key": str(i)}
    return rev

def predictions_for(api_header_row: dict, similar_rows: list, reverse_mapping: dict,
                    pred_threshold: float = 80.0, majority_ratio: float = 0.65):
    if not similar_rows:
        return "", "", []

    ms_list = [r["MS SKOR"] for r in similar_rows if str(r.get("MS SKOR","")).strip()]
    iy_list = [r["IY SKOR"] for r in similar_rows if str(r.get("IY SKOR","")).strip()]

    def majority(lst):
        if not lst: return ""
        c = Counter(lst); top, cnt = c.most_common(1)[0]
        return top if (cnt/len(lst)) >= majority_ratio else ""

    pred_ms = majority(ms_list)
    pred_iy = majority(iy_list)

    rules = build_prediction_criteria()
    total = len(similar_rows)
    preds = []

    def find_odds_from_MA(ma_list, mtid, sov, oca_key):
        for mk in ma_list or []:
            if mk.get("MTID") != mtid: continue
            if sov is not None:
                try:
                    if float(mk.get("SOV", 0)) != float(sov):
                        continue
                except Exception:
                    continue
            for o in mk.get("OCA", []) or mk.get("OC", []):
                if str(o.get("N","")).strip() == str(oca_key):
                    return o.get("O")
        return None

    for display_name, info in rules.items():
        # bu kriterin bir markete bağlanabilmesi için reverse_mapping’te kolon adı olmalı
        if display_name not in reverse_mapping:
            # reverse_mapping yoksa yine de yüzdesini hesaplayıp gösteririz (oran olmadan)
            count_true = sum(1 for r in similar_rows if info["func"](r))
            pct = (count_true/total)*100.0
            if pct >= pred_threshold:
                preds.append(f"{display_name}: {pct:.1f}%")
            continue

        m = reverse_mapping[display_name]
        count_true = sum(1 for r in similar_rows if info["func"](r))
        pct = (count_true/total)*100.0
        if pct < pred_threshold:
            continue

        odds = find_odds_from_MA(api_header_row.get("MA", []), m["mtid"], m["sov"], m["oca_key"])
        if odds is not None:
            try:
                preds.append(f"{display_name}: {pct:.1f}% (Oran {float(odds):.2f})")
            except Exception:
                preds.append(f"{display_name}: {pct:.1f}% (Oran {odds})")
        else:
            preds.append(f"{display_name}: {pct:.1f}%")

    return pred_iy, pred_ms, preds[:5]

# =========================
# Benzer arama (lig-içi → global), hızlı ön-eleme
# =========================
def build_odds_row(row: dict) -> dict:
    return {c: row[c] for c in EXCEL_COLUMNS if c in row and pd.notna(row[c])}

def prefilter_candidates(api_odds: dict, df: pd.DataFrame) -> pd.DataFrame:
    """ 1X2 fair trio’ya göre hızlı kapı (yaklaşık eş dağılım) """
    MS1,MSX,MS2="Maç Sonucu 1","Maç Sonucu X","Maç Sonucu 2"
    def trio(d):
        p1,pX,p2=_prob(d.get(MS1)),_prob(d.get(MSX)),_prob(d.get(MS2))
        if None in (p1,pX,p2): return None
        s=p1+pX+p2
        if s<=0: return None
        return (p1/s,pX/s,p2/s)
    A=trio(api_odds)
    if not A: return pd.DataFrame(columns=df.columns)
    # kabaca ±%25 bacak toleransı
    def pass_row(row):
        B=trio(row)
        if not B: return False
        for a,b in zip(A,B):
            d=_rel(a,b)
            if d is None or d>0.25: return False
        return True
    mask = df[[MS1,MSX,MS2]].notna().all(axis=1)
    cand = df[mask].copy()
    if cand.empty: return cand
    return cand[cand.apply(pass_row, axis=1)]

def find_similars_for_match(api_header: dict, hist_df: pd.DataFrame, top_league=7, top_global=3):
    api_odds = odds_from_MA(api_header.get("MA", []), mtid_mapping)
    if not api_odds: return [], 0.0

    # Lig-içi öncelik
    league = api_header.get("Lig Adı","")
    in_league = hist_df[hist_df["Lig Adı"] == league] if "Lig Adı" in hist_df.columns else pd.DataFrame()
    others    = hist_df[hist_df["Lig Adı"] != league] if not in_league.empty else hist_df

    def score_block(block, limit):
        out=[]
        if block.empty: return out
        block2 = prefilter_candidates(api_odds, block)
        for _, row in block2.iterrows():
            row_odds = build_odds_row(row)
            if not row_odds: continue
            if not quality_filter(api_odds, row_odds): continue
            sim = calculate_similarity(api_odds, row_odds)
            if sim <= 0: continue
            out.append({
                "Benzerlik (%)": sim,
                "Saat": str(row.get("Saat","")), "Tarih": str(row.get("Tarih","")),
                "Ev Sahibi Takım": row.get("Ev Sahibi Takım",""),
                "Deplasman Takım": row.get("Deplasman Takım",""),
                "Lig Adı": row.get("Lig Adı",""),
                "IY SKOR": str(row.get("IY SKOR","")),
                "MS SKOR": str(row.get("MS SKOR","")),
            })
        out.sort(key=lambda r: (-r["Benzerlik (%)"], r["Tarih"], r["Saat"]))
        return out[:limit]

    top1 = score_block(in_league, top_league)
    top2 = score_block(others,    top_global)
    allr = top1 + top2
    best = max((r["Benzerlik (%)"] for r in allr), default=0.0)
    return allr, best

# =========================
# AKIŞ
# =========================
with st.spinner("Veriler yükleniyor..."):
    league_mapping, mtid_mapping, reverse_mapping = load_mappings()
    df_hist = load_matches_df(MATCHES_SHEET_URL, uploaded_backup)
    if df_hist.empty:
        st.error("matches.xlsx indirilemedi. Lütfen üstteki alandan dosyayı yükleyin.")
        st.stop()
    # odds kolonları numerik kalmalı
    for c in EXCEL_COLUMNS:
        if c in df_hist.columns:
            df_hist[c] = pd.to_numeric(df_hist[c], errors="coerce")

    api_json = fetch_api_json()
    api_rows = parse_api_to_rows(api_json, default_start, end_dt, league_mapping)

if not api_rows:
    st.warning("Seçilen aralıkta uygun maç bulunamadı (API geçici boş dönmüş olabilir).")
    st.stop()

OUTPUT_COLUMNS = ["Benzerlik (%)","Saat","Tarih","Ev Sahibi Takım","Deplasman Takım","Lig Adı","IY SKOR","MS SKOR","Tahmin"]
out_rows = []

for api in api_rows:
    # Grup başlığı satırı
    header = {
        "Benzerlik (%)": "",
        "Saat": api["Saat"], "Tarih": api["Tarih"],
        "Ev Sahibi Takım": api["Ev Sahibi Takım"],
        "Deplasman Takım": api["Deplasman Takım"],
        "Lig Adı": api["Lig Adı"],
        "IY SKOR": "", "MS SKOR": "",
        "Tahmin": "",
        "MA": api.get("MA", [])
    }
    similars, best = find_similars_for_match(header, df_hist)
    pred_iy, pred_ms, preds = predictions_for(header, similars, reverse_mapping,
                                              pred_threshold=80.0, majority_ratio=0.65)
    header["IY SKOR"] = pred_iy
    header["MS SKOR"] = pred_ms
    header["Tahmin"] = " • ".join(preds) if preds else ""
    out_rows.append(header)
    out_rows.extend(similars)
    out_rows.append({})  # ayraç

result_df = pd.DataFrame([r for r in out_rows if r])
if result_df.empty:
    st.info("Benzer maç bulunamadı.")
else:
    st.dataframe(result_df[OUTPUT_COLUMNS], use_container_width=True, hide_index=True)
