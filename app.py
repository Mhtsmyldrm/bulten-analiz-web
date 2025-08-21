import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime, timedelta, timezone
from collections import Counter
from gdown import download
import math
import json

# =========================
# Sabitler / Başlık
# =========================
st.set_page_config(page_title="Bülten Analiz", layout="wide")
st.title("Bülten Analiz")

IST = timezone(timedelta(hours=3))

# Google Drive fileIds (sen değiştirebilirsin)
# Not: Sheets linkini "export?format=xlsx" yerine gdown ile indiriyoruz (432 hatasını aşmak için)
MATCHES_FILE_ID = "11m7tX2xCavCM_cij69UaSVijFuFQbveM"   # matches.xlsx
LEAGUE_JSON_ID  = "1L8HA_emD92BJSuCn-P9GJF-hH55nIKE7"   # league_mapping.json
MTID_JSON_ID    = "1N1PjFla683BYTAdzVDaajmcnmMB5wiiO"   # mtid_mapping.json

# =========================
# Yardımcılar
# =========================
def drive_download_file(file_id: str, out_path: str):
    url = f"https://drive.google.com/uc?id={file_id}"
    download(url, out_path, quiet=True)

def drive_download_json(file_id: str):
    url = f"https://drive.google.com/uc?id={file_id}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

def to_float(x):
    try:
        return float(x)
    except Exception:
        return None

def prob(odd):
    o = to_float(odd)
    if o is None or o <= 1.0:
        return None
    return 1.0 / o

# =========================
# Oran başlıkları (v26 ile aynı kapsam)
# =========================
excel_columns = [
    "Maç Sonucu 1", "Maç Sonucu X", "Maç Sonucu 2",
    "Çifte Şans 1 veya X", "Çifte Şans 1 veya 2", "Çifte Şans X veya 2",
    "0,5 Alt/Üst Alt", "0,5 Alt/Üst Üst",
    "1,5 Alt/Üst Alt", "1,5 Alt/Üst Üst",
    "2,5 Alt/Üst Alt", "2,5 Alt/Üst Üst",
    "3,5 Alt/Üst Alt", "3,5 Alt/Üst Üst",
    "4,5 Alt/Üst Alt", "4,5 Alt/Üst Üst",
    "Karşılıklı Gol Var", "Karşılıklı Gol Yok",
    "İlk Yarı/Maç Sonucu 1/1", "İlk Yarı/Maç Sonucu 1/X", "İlk Yarı/Maç Sonucu 1/2",
    "İlk Yarı/Maç Sonucu X/1", "İlk Yarı/Maç Sonucu X/X", "İlk Yarı/Maç Sonucu X/2",
    "İlk Yarı/Maç Sonucu 2/1", "İlk Yarı/Maç Sonucu 2/X", "İlk Yarı/Maç Sonucu 2/2",
    "Toplam Gol Aralığı 0-1 Gol", "Toplam Gol Aralığı 2-3 Gol", "Toplam Gol Aralığı 4-5 Gol", "Toplam Gol Aralığı 6+ Gol",
    "1. Yarı Sonucu 1", "1. Yarı Sonucu X", "1. Yarı Sonucu 2",
    "1. Yarı Çifte Şans 1-X", "1. Yarı Çifte Şans 1-2", "1. Yarı Çifte Şans X-2",
    "2. Yarı Sonucu 1", "2. Yarı Sonucu X", "2. Yarı Sonucu 2",
    "Maç Sonucu ve (1,5) Alt/Üst 1 ve Alt", "Maç Sonucu ve (1,5) Alt/Üst X ve Alt", "Maç Sonucu ve (1,5) Alt/Üst 2 ve Alt",
    "Maç Sonucu ve (1,5) Alt/Üst 1 ve Üst", "Maç Sonucu ve (1,5) Alt/Üst X ve Üst", "Maç Sonucu ve (1,5) Alt/Üst 2 ve Üst",
    "Maç Sonucu ve (2,5) Alt/Üst 1 ve Alt", "Maç Sonucu ve (2,5) Alt/Üst X ve Alt", "Maç Sonucu ve (2,5) Alt/Üst 2 ve Alt",
    "Maç Sonucu ve (2,5) Alt/Üst 1 ve Üst", "Maç Sonucu ve (2,5) Alt/Üst X ve Üst", "Maç Sonucu ve (2,5) Alt/Üst 2 ve Üst",
    "Maç Sonucu ve (3,5) Alt/Üst 1 ve Alt", "Maç Sonucu ve (3,5) Alt/Üst X ve Alt", "Maç Sonucu ve (3,5) Alt/Üst 2 ve Alt",
    "Maç Sonucu ve (3,5) Alt/Üst 1 ve Üst", "Maç Sonucu ve (3,5) Alt/Üst X ve Üst", "Maç Sonucu ve (3,5) Alt/Üst 2 ve Üst",
    "Maç Sonucu ve (4,5) Alt/Üst 1 ve Alt", "Maç Sonucu ve (4,5) Alt/Üst X ve Alt", "Maç Sonucu ve (4,5) Alt/Üst 2 ve Alt",
    "Maç Sonucu ve (4,5) Alt/Üst 1 ve Üst", "Maç Sonucu ve (4,5) Alt/Üst X ve Üst", "Maç Sonucu ve (4,5) Alt/Üst 2 ve Üst",
    "1. Yarı 0,5 Alt/Üst Alt", "1. Yarı 0,5 Alt/Üst Üst",
    "1. Yarı 1,5 Alt/Üst Alt", "1. Yarı 1,5 Alt/Üst Üst",
    "1. Yarı 2,5 Alt/Üst Alt", "1. Yarı 2,5 Alt/Üst Üst",
    "Evsahibi 0,5 Alt/Üst Alt", "Evsahibi 0,5 Alt/Üst Üst",
    "Evsahibi 1,5 Alt/Üst Alt", "Evsahibi 1,5 Alt/Üst Üst",
    "Evsahibi 2,5 Alt/Üst Alt", "Evsahibi 2,5 Alt/Üst Üst",
    "Deplasman 0,5 Alt/Üst Alt", "Deplasman 0,5 Alt/Üst Üst",
    "Deplasman 1,5 Alt/Üst Alt", "Deplasman 1,5 Alt/Üst Üst",
    "Deplasman 2,5 Alt/Üst Alt", "Deplasman 2,5 Alt/Üst Üst",
    "İlk Gol 1", "İlk Gol Olmaz", "İlk Gol 2",
    "Daha Çok Gol Olacak Yarı 1.Y", "Daha Çok Gol Olacak Yarı Eşit", "Daha Çok Gol Olacak Yarı 2.Y",
    "Maç Skoru 1-0", "Maç Skoru 2-0", "Maç Skoru 2-1", "Maç Skoru 3-0", "Maç Skoru 3-1", "Maç Skoru 3-2",
    "Maç Skoru 4-0", "Maç Skoru 4-1", "Maç Skoru 4-2", "Maç Skoru 5-0", "Maç Skoru 5-1", "Maç Skoru 6-0",
    "Maç Skoru 0-0", "Maç Skoru 1-1", "Maç Skoru 2-2", "Maç Skoru 3-3", "Maç Skoru 0-1", "Maç Skoru 0-2",
    "Maç Skoru 1-2", "Maç Skoru 0-3", "Maç Skoru 1-3", "Maç Skoru 2-3", "Maç Skoru 0-4", "Maç Skoru 1-4",
    "Maç Skoru 2-4", "Maç Skoru 0-5", "Maç Skoru 1-5", "Maç Skoru 0-6", "Maç Skoru Diğer",
    "Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2",
    "Handikaplı Maç Sonucu (1,0) 1", "Handikaplı Maç Sonucu (1,0) X", "Handikaplı Maç Sonucu (1,0) 2",
]

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
OTHER_MARKETS = set(excel_columns) - CRITICAL_MARKETS - IMPORTANT_MARKETS

# =========================
# JSON yükleyiciler (Drive)
# =========================
@st.cache_data(show_spinner=False)
def load_mappings_from_drive():
    league_data = drive_download_json(LEAGUE_JSON_ID)
    league_mapping = {}
    for k, v in league_data.items():
        try:
            league_mapping[int(k)] = v
        except Exception:
            pass

    mtid_data = drive_download_json(MTID_JSON_ID)
    mtid_mapping = {}
    reverse_mapping = {}
    for key_str, value in mtid_data.items():
        if not (isinstance(key_str, str) and key_str.startswith("(") and key_str.endswith(")")):
            continue
        parts = key_str[1:-1].split(",")
        if len(parts) != 2:
            continue
        mtid = int(parts[0].strip())
        sov_raw = parts[1].strip()
        sov = None
        if sov_raw.lower() != "null":
            try:
                sov = float(sov_raw)
            except Exception:
                sov = None
        if not isinstance(value, list):
            continue
        mtid_mapping[(mtid, sov)] = value
        for i, col_name in enumerate(value, start=1):
            if isinstance(col_name, str):
                reverse_mapping[col_name] = {"mtid": mtid, "sov": sov, "oca_key": str(i)}
    return league_mapping, mtid_mapping, reverse_mapping

# =========================
# API verisini çekme (Nesine)
# =========================
@st.cache_data(show_spinner=False)
def fetch_api_data(league_mapping: dict, mtid_mapping: dict) -> pd.DataFrame:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.nesine.com/",
        "Accept": "application/json, text/plain, */*",
    }
    url = "https://bulten.nesine.com/api/bulten/getprebultendelta?marketVersion=1716908400&eventVersion=1716908400"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    match_list = data.get("Data", {}).get("EventList", [])
    rows = []
    for m in match_list:
        try:
            D = m.get("D", "")
            T = m.get("T", "")
            if not (D and T):
                continue
            dt = datetime.strptime(f"{D} {T}", "%d.%m.%Y %H:%M").replace(tzinfo=IST)
            league_code = m.get("LC", None)
            league_name = league_mapping.get(int(league_code)) if league_code is not None else str(league_code)
            base = {
                "Saat": T, "Tarih": D,
                "Ev Sahibi Takım": m.get("HN", ""), "Deplasman Takım": m.get("AN", ""),
                "Lig Adı": league_name if league_name else "",
                "match_datetime": dt,
                "MA": m.get("MA", []),
            }
            for col in excel_columns:
                base[col] = np.nan

            for market in m.get("MA", []):
                mtid = market.get("MTID")
                sov  = market.get("SOV", None)
                try:
                    sov_key = None if sov is None else float(sov)
                except Exception:
                    sov_key = None
                key = (int(mtid), sov_key) if mtid is not None else None
                if key and key in mtid_mapping:
                    col_names = mtid_mapping[key]
                    oca_list = market.get("OCA", [])
                    for idx, col_name in enumerate(col_names, start=1):
                        val = None
                        for oca in oca_list:
                            if str(oca.get("N")) == str(idx):
                                val = oca.get("O")
                                break
                        if col_name in base:
                            try:
                                base[col_name] = float(val) if val not in (None, "") else np.nan
                            except Exception:
                                base[col_name] = np.nan
            rows.append(base)
        except Exception:
            continue
    return pd.DataFrame(rows)

# =========================
# Excel (geçmiş maçlar) indir + yükle
# =========================
@st.cache_data(show_spinner=False)
def load_matches_xlsx() -> pd.DataFrame:
    drive_download_file(MATCHES_FILE_ID, "matches.xlsx")
    # Varsayılan sayfa "Bahisler" (önceki app.py ile uyumlu)
    df = pd.read_excel("matches.xlsx", sheet_name="Bahisler", dtype=str)
    # Kullanacağımız kolonları normalize et
    basic = ["Tarih", "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY SKOR", "MS SKOR"]
    keep = basic + excel_columns
    # Kesin var olanları seç; olmayanları atla
    cols_lower = {c.lower().strip(): c for c in df.columns}
    selected = [cols_lower[c.lower()] for c in keep if c.lower() in cols_lower]
    df = pd.read_excel("matches.xlsx", sheet_name="Bahisler", usecols=selected, dtype=str)
    # Odds -> float; 1.00 ve altını NaN yap
    for col in excel_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].where(df[col] > 1.0, np.nan)
    return df

# =========================
# Benzerlik (v26 ile aynı mantık)
# =========================
def fair_trio_from_odds(odds_dict, k1, kx, k2):
    p1, px, p2 = prob(odds_dict.get(k1)), prob(odds_dict.get(kx)), prob(odds_dict.get(k2))
    if None in (p1, px, p2): return None
    s = p1 + px + p2
    if s <= 0: return None
    return (p1/s, px/s, p2/s)

def hellinger_trio(p, q):
    return max(0.0, 1.0 - (math.sqrt(
        (math.sqrt(p[0]) - math.sqrt(q[0]))**2 +
        (math.sqrt(p[1]) - math.sqrt(q[1]))**2 +
        (math.sqrt(p[2]) - math.sqrt(q[2]))**2
    ) / math.sqrt(2.0)))

def rel_diff(a, b):
    if a is None or b is None or a <= 0 or b <= 0: return None
    return abs(a - b) / ((a + b) / 2.0)

def bin_sim(key, api_odds, match_odds):
    if key not in api_odds or key not in match_odds: return None
    pa, pb = prob(api_odds[key]), prob(match_odds[key])
    d = rel_diff(pa, pb)
    if d is None: return None
    C = 3.5
    return math.exp(-C * d)

def calculate_similarity(api_odds: dict, match_odds: dict) -> float:
    MS1, MSX, MS2 = "Maç Sonucu 1", "Maç Sonucu X", "Maç Sonucu 2"
    KG_V, KG_Y    = "Karşılıklı Gol Var", "Karşılıklı Gol Yok"
    O25A, O25U    = "2,5 Alt/Üst Alt", "2,5 Alt/Üst Üst"

    api_ms = fair_trio_from_odds(api_odds, MS1, MSX, MS2)
    mat_ms = fair_trio_from_odds(match_odds, MS1, MSX, MS2)
    if not api_ms or not mat_ms:
        return 0.0

    base = hellinger_trio(api_ms, mat_ms)
    if base < 0.85:
        return base * 100.0

    for a, b in zip(api_ms, mat_ms):
        d = rel_diff(a, b)
        if d is None or d > 0.12:
            return base * 100.0

    high_list = [("1X2", base, 1.0)]
    for k in (KG_V, KG_Y, O25A, O25U):
        s = bin_sim(k, api_odds, match_odds)
        if s is not None:
            high_list.append((k, s, 1.0))
    for k in ("Çifte Şans 1 veya X", "Çifte Şans 1 veya 2", "Çifte Şans X veya 2"):
        s = bin_sim(k, api_odds, match_odds)
        if s is not None:
            high_list.append((k, s, 0.5))
    for k in ("Handikaplı Maç Sonucu (-1,0) 1","Handikaplı Maç Sonucu (-1,0) X","Handikaplı Maç Sonucu (-1,0) 2",
              "Handikaplı Maç Sonucu (1,0) 1","Handikaplı Maç Sonucu (1,0) X","Handikaplı Maç Sonucu (1,0) 2"):
        s = bin_sim(k, api_odds, match_odds)
        if s is not None:
            high_list.append((k, s, 1.0))

    MED_KEYS = [
        "1. Yarı Sonucu 1", "1. Yarı Sonucu X", "1. Yarı Sonucu 2",
        "0,5 Alt/Üst Alt", "0,5 Alt/Üst Üst",
        "1,5 Alt/Üst Alt", "1,5 Alt/Üst Üst",
        "3,5 Alt/Üst Alt", "3,5 Alt/Üst Üst",
        "4,5 Alt/Üst Alt", "4,5 Alt/Üst Üst",
        "5,5 Alt/Üst Alt", "5,5 Alt/Üst Üst",
        "6,5 Alt/Üst Alt", "6,5 Alt/Üst Üst",
        "7,5 Alt/Üst Alt", "7,5 Alt/Üst Üst",
        "2. Yarı Sonucu 1", "2. Yarı Sonucu X", "2. Yarı Sonucu 2",
        "Toplam Gol Aralığı 0-1 Gol", "Toplam Gol Aralığı 2-3 Gol", "Toplam Gol Aralığı 4-5 Gol", "Toplam Gol Aralığı 6+ Gol",
        "Handikaplı Maç Sonucu (-2,0) 1", "Handikaplı Maç Sonucu (-2,0) X", "Handikaplı Maç Sonucu (-2,0) 2",
        "Handikaplı Maç Sonucu (2,0) 1",  "Handikaplı Maç Sonucu (2,0) X",  "Handikaplı Maç Sonucu (2,0) 2",
    ]
    med_list = []
    for k in MED_KEYS:
        s = bin_sim(k, api_odds, match_odds)
        if s is not None:
            w = 0.5 if "Alt/Üst" in k else 1.0
            med_list.append((k, s, w))

    low_list = []
    for k in match_odds.keys():
        if k in (MS1, MSX, MS2) or any(k == n for n,_,_ in high_list) or k in MED_KEYS:
            continue
        if ("Korner" in k) or ("Kart" in k):
            continue
        s = bin_sim(k, api_odds, match_odds)
        if s is not None:
            low_list.append((k, s, 1.0))

    def wmean(items):
        sw = sum(w for _,_,w in items)
        if sw == 0: return None, 0
        return sum(s*w for _,s,w in items)/sw, len(items)

    high_sim, nh = wmean(high_list)
    med_sim,  nm = wmean(med_list)
    low_sim,  nl = wmean(low_list)

    def shrink(val, n, target=6):
        if val is None or n <= 0: return None
        f = math.sqrt(min(n, target)/float(target))
        return val * f

    high_sim = shrink(high_sim, nh)
    med_sim  = shrink(med_sim, nm)
    low_sim  = shrink(low_sim, nl)

    W_HIGH, W_MED, W_LOW = 0.65, 0.25, 0.10
    total, wsum = 0.0, 0.0
    for sim, w in ((high_sim, W_HIGH), (med_sim, W_MED), (low_sim, W_LOW)):
        if sim is not None:
            total += sim * w
            wsum  += w
    score = total/wsum if wsum > 0 else base

    anchors = 0
    def have(*keys):
        return all(key in api_odds and key in match_odds and to_float(api_odds[key]) and to_float(match_odds[key]) for key in keys)
    if have(MS1, MSX, MS2): anchors += 1
    if have(KG_V, KG_Y):    anchors += 1
    if have(O25A, O25U):    anchors += 1
    ah_has = any(k in match_odds for k in (
        "Handikaplı Maç Sonucu (-1,0) 1","Handikaplı Maç Sonucu (-1,0) X","Handikaplı Maç Sonucu (-1,0) 2",
        "Handikaplı Maç Sonucu (1,0) 1","Handikaplı Maç Sonucu (1,0) X","Handikaplı Maç Sonucu (1,0) 2"))
    if ah_has: anchors += 1
    if anchors < 2:
        score = min(score, 0.85)
    return float(score*100.0)

def quality_filter(api_odds: dict, data_odds: dict) -> bool:
    api_cnt  = sum(1 for col in excel_columns if col in api_odds and pd.notna(api_odds[col]))
    data_cnt = sum(1 for col in excel_columns if col in data_odds and pd.notna(data_odds[col]))
    if data_cnt < api_cnt * 0.7:
        return False
    critical_count = sum(1 for m in CRITICAL_MARKETS if m in data_odds and pd.notna(data_odds[m]))
    if critical_count < max(1, int(len(CRITICAL_MARKETS)*0.5)):
        return False
    return True

def build_odds_row_from_row(row: pd.Series) -> dict:
    return {col: row[col] for col in excel_columns if col in row and pd.notna(row[col])}

# =========================
# Prediction (v26’ye uygun)
# =========================
def _parse_score(score_text: str):
    try:
        a, b = score_text.strip().split("-")
        return int(a), int(b)
    except Exception:
        return None, None

def v26_prediction_rules():
    # v26_lig_gpt’deki kural kümesini kapsayacak şekilde:
    rules = {
        # 1X2
        "Maç Sonucu 1": {"func": lambda r: (lambda h,a: h>a)(*_parse_score(r.get("MS SKOR","")) )},
        "Maç Sonucu X": {"func": lambda r: (lambda h,a: h==a)(*_parse_score(r.get("MS SKOR","")) )},
        "Maç Sonucu 2": {"func": lambda r: (lambda h,a: h<a)(*_parse_score(r.get("MS SKOR","")) )},
        # 1. Yarı 1X2
        "1. Yarı Sonucu 1": {"func": lambda r: (lambda h,a: h>a)(*_parse_score(r.get("IY SKOR","")) )},
        "1. Yarı Sonucu X": {"func": lambda r: (lambda h,a: h==a)(*_parse_score(r.get("IY SKOR","")) )},
        "1. Yarı Sonucu 2": {"func": lambda r: (lambda h,a: h<a)(*_parse_score(r.get("IY SKOR","")) )},
        # O/U 2.5
        "2,5 Alt/Üst Alt": {"func": lambda r: (lambda h,a: (h+a) <= 2)(*_parse_score(r.get("MS SKOR","")) )},
        "2,5 Alt/Üst Üst": {"func": lambda r: (lambda h,a: (h+a) >= 3)(*_parse_score(r.get("MS SKOR","")) )},
        # KG
        "Karşılıklı Gol Var": {"func": lambda r: (lambda h,a: (h>0 and a>0))(*_parse_score(r.get("MS SKOR","")) )},
        "Karşılıklı Gol Yok": {"func": lambda r: (lambda h,a: (h==0 or a==0))(*_parse_score(r.get("MS SKOR","")) )},
        # ÇŞ
        "Çifte Şans 1 veya X": {"func": lambda r: (lambda h,a: h>=a)(*_parse_score(r.get("MS SKOR","")) )},
        "Çifte Şans 1 veya 2": {"func": lambda r: (lambda h,a: h!=a)(*_parse_score(r.get("MS SKOR","")) )},
        "Çifte Şans X veya 2": {"func": lambda r: (lambda h,a: h<=a)(*_parse_score(r.get("MS SKOR","")) )},
        # AH -1, +1
        "Handikaplı Maç Sonucu (-1,0) 1": {"func": lambda r: (lambda h,a: (h-1) > a)(*_parse_score(r.get("MS SKOR","")) )},
        "Handikaplı Maç Sonucu (-1,0) X": {"func": lambda r: (lambda h,a: (h-1) == a)(*_parse_score(r.get("MS SKOR","")) )},
        "Handikaplı Maç Sonucu (-1,0) 2": {"func": lambda r: (lambda h,a: (h-1) < a)(*_parse_score(r.get("MS SKOR","")) )},
        "Handikaplı Maç Sonucu (1,0) 1":  {"func": lambda r: (lambda h,a: (h+1) > a)(*_parse_score(r.get("MS SKOR","")) )},
        "Handikaplı Maç Sonucu (1,0) X":  {"func": lambda r: (lambda h,a: (h+1) == a)(*_parse_score(r.get("MS SKOR","")) )},
        "Handikaplı Maç Sonucu (1,0) 2":  {"func": lambda r: (lambda h,a: (h+1) < a)(*_parse_score(r.get("MS SKOR","")) )},
    }
    return rules

def predict_for_api_row(api_row: pd.Series, similars, reverse_mapping: dict, pred_threshold=80.0, majority_ratio=0.65):
    if not similars:
        return "", "", []

    # Skor modları (çoğunluk)
    ms_scores = [s["row"].get("MS SKOR","") for s in similars if str(s["row"].get("MS SKOR","")).strip()]
    iy_scores = [s["row"].get("IY SKOR","") for s in similars if str(s["row"].get("IY SKOR","")).strip()]

    def majority(scores):
        if not scores: return ""
        counts = Counter(scores)
        score, count = counts.most_common(1)[0]
        return score if count/len(scores) >= majority_ratio else ""

    pred_ms = majority(ms_scores)
    pred_iy = majority(iy_scores)

    rules = v26_prediction_rules()
    predictions = []
    total = len(similars)

    def find_market_odds(api_row_local, mtid, sov, oca_key):
        for market in api_row_local.get("MA", []):
            if market.get("MTID") != mtid: continue
            if sov is not None:
                try:
                    if float(market.get("SOV", 0)) != float(sov):
                        continue
                except Exception:
                    continue
            for oca in market.get("OCA", []):
                if str(oca.get("N")) == str(oca_key):
                    return oca.get("O")
        return None

    for display_name, info in rules.items():
        if display_name not in reverse_mapping:
            continue
        mtid = reverse_mapping[display_name]["mtid"]
        sov  = reverse_mapping[display_name]["sov"]
        oca_key = reverse_mapping[display_name]["oca_key"]

        # MTID + (varsa) SOV kontrolü
        market_available = False
        for mrk in api_row.get("MA", []):
            if mrk.get("MTID") != mtid:
                continue
            if (sov is None) or (str(mrk.get("SOV")) == str(sov)):
                market_available = True; break
        if not market_available:
            continue

        count_true = sum(1 for s in similars if info["func"](s["row"]))
        pct = (count_true / total) * 100.0
        if pct < pred_threshold:
            continue

        odds = find_market_odds(api_row, mtid, sov, oca_key)
        if odds is not None:
            try:
                predictions.append(f"{display_name}: {pct:.1f}% (Oran {float(odds):.2f})")
            except Exception:
                predictions.append(f"{display_name}: {pct:.1f}% (Oran {odds})")
        else:
            predictions.append(f"{display_name}: {pct:.1f}%")

    return pred_iy, pred_ms, predictions

# =========================
# Benzer arama
# =========================
def find_similar_matches_for_all(api_df: pd.DataFrame, hist_df: pd.DataFrame, top_k: int = 25, pred_threshold=80.0):
    out_rows = []
    for _, api_row in api_df.iterrows():
        api_odds = build_odds_row_from_row(api_row)
        if not api_odds:
            continue

        # Adaylar: aynı lig öncelikli
        if "Lig Adı" in api_row and pd.notna(api_row["Lig Adı"]):
            same_league = hist_df[hist_df["Lig Adı"] == api_row["Lig Adı"]]
        else:
            same_league = pd.DataFrame(columns=hist_df.columns)
        others = hist_df if same_league.empty else hist_df[hist_df["Lig Adı"] != api_row["Lig Adı"]]
        candidates = pd.concat([same_league, others], ignore_index=True)

        scored = []
        for _, drow in candidates.iterrows():
            data_odds = build_odds_row_from_row(drow)
            if not data_odds: continue
            if not quality_filter(api_odds, data_odds): continue
            sim = calculate_similarity(api_odds, data_odds)
            if sim <= 0: continue
            scored.append({"similarity": sim, "row": drow})
            if len(scored) >= 5000:
                break

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        similars = scored[:top_k]

        pred_iy, pred_ms, preds = predict_for_api_row(api_row, similars, reverse_mapping, pred_threshold=pred_threshold)
        best = max((s["similarity"] for s in similars), default=0.0)

        out_rows.append({
            "Benzerlik (%)": round(float(best),1),
            "Saat": api_row.get("Saat",""),
            "Tarih": api_row.get("Tarih",""),
            "Ev Sahibi Takım": api_row.get("Ev Sahibi Takım",""),
            "Deplasman Takım": api_row.get("Deplasman Takım",""),
            "Lig Adı": api_row.get("Lig Adı",""),
            "IY SKOR": pred_iy,
            "MS SKOR": pred_ms,
            "Tahmin": " | ".join(preds[:2]) if preds else ""
        })
    return out_rows

# =========================
# UI – Bitiş zamanı seçimi (sade)
# =========================
st.subheader("Analiz için Saat Aralığı")
default_start = datetime.now(IST) + timedelta(minutes=5)
st.write(f"Başlangıç Saati: {default_start.strftime('%d.%m.%Y %H:%M')} (Otomatik, şu an + 5 dakika)")

end_date = st.date_input("Bitiş Tarihi", value=datetime.now(IST).date())
end_time = st.time_input("Bitiş Saati", value=None)

if st.button("Analize Başla"):
    if end_time is None:
        st.error("Lütfen bitiş saati seçin!")
        st.stop()

    end_dt = datetime.combine(end_date, end_time).replace(tzinfo=IST)
    start_dt = default_start
    if end_dt <= start_dt:
        st.error("Bitiş saati başlangıç saatinden önce olamaz!")
        st.stop()

    try:
        with st.spinner("Veriler yükleniyor..."):
            league_mapping, mtid_mapping, reverse_mapping = load_mappings_from_drive()
            hist_df = load_matches_xlsx()

            api_df = fetch_api_data(league_mapping, mtid_mapping)
            if api_df.empty:
                st.error("API verisi boş döndü.")
                st.stop()

            api_df = api_df[api_df["match_datetime"].between(start_dt, end_dt)].copy()
            if api_df.empty:
                st.info("Seçilen aralıkta maç bulunamadı.")
                st.stop()

            output = find_similar_matches_for_all(api_df, hist_df, top_k=25, pred_threshold=80.0)
            result_df = pd.DataFrame(output)
            if result_df.empty:
                st.info("Eşleşme bulunamadı.")
                st.stop()

            result_df.sort_values(by=["Benzerlik (%)","Tarih","Saat"], ascending=[False,True,True], inplace=True)
            st.dataframe(result_df.reset_index(drop=True), hide_index=True, use_container_width=True)
            st.success("Analiz tamamlandı!")
    except Exception as e:
        st.error(f"Hata oluştu: {e}")
        st.stop()
