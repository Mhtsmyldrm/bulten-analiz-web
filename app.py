import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, timezone
from gdown import download
import time
import json
import math
from collections import Counter

# ==============================
# UI & THEME
# ==============================
st.markdown("""
<style>
/* Title */
h1 { font-weight: 800; color: #05f705; }

/* Buttons */
.stButton button { background-color: #4CAF50; color: white; border-radius: 8px; padding: 0.5rem 1rem; }

/* Dataframe: make last column ("Tahmin") wider and wrap text */
div[data-testid="stDataFrame"] table { table-layout: fixed; }
div[data-testid="stDataFrame"] td, div[data-testid="stDataFrame"] th {
  white-space: normal !important;
  word-wrap: break-word !important;
}
div[data-testid="stDataFrame"] [role="gridcell"]:last-child {
  min-width: 380px !important;
}

/* Sticky header for dataframe */
.stDataFrame thead tr th { position: sticky; top: 0; background-color: #f0f0f0; z-index: 1; pointer-events: none; }
.stDataFrame th:hover { cursor: default; }
</style>
""", unsafe_allow_html=True)

# Title
st.title("Bülten Analiz")

# ==============================
# SESSION STATE
# ==============================
for key, default in [
    ("data", None),
    ("analysis_done", False),
    ("mtid_mapping", {}),
    ("league_mapping", {}),
    ("iyms_df", None),
    ("main_df", None),
    ("output_rows", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

status_placeholder = st.empty()

# ==============================
# CONSTANTS / IDS
# ==============================
LEAGUE_MAPPING_ID = "1L8HA_emD92BJSuCn-P9GJF-hH55nIKE7"
MTID_MAPPING_ID   = "1N1PjFla683BYTAdzVDaajmcnmMB5wiiO"
EXCEL_FILE_ID     = "11m7tX2xCavCM_cij69UaSVijFuFQbveM"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nesine.com/",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Connection": "keep-alive",
    "X-Requested-With": "XMLHttpRequest",
}

IST = timezone(timedelta(hours=3))

# ==============================
# LOAD JSON MAPPINGS
# ==============================
def load_json_mappings():
    try:
        download(f"https://drive.google.com/uc?id={LEAGUE_MAPPING_ID}", "league_mapping.json", quiet=True)
        with open("league_mapping.json", "r", encoding="utf-8") as f:
            league_data = json.load(f)
            league_mapping = {int(k): v for k, v in league_data.items()}
    except Exception as e:
        st.error(f"league_mapping.json yüklenirken hata: {str(e)}")
        league_mapping = {}

    try:
        download(f"https://drive.google.com/uc?id={MTID_MAPPING_ID}", "mtid_mapping.json", quiet=True)
        with open("mtid_mapping.json", "r", encoding="utf-8") as f:
            mtid_data = json.load(f)
            mtid_mapping = {}
            for key_str, value in mtid_data.items():
                if key_str.startswith("(") and key_str.endswith(")"):
                    parts = key_str[1:-1].split(", ")
                    if len(parts) == 2:
                        mtid = int(parts[0])
                        sov = None if parts[1] == "null" else float(parts[1])
                        mtid_mapping[(mtid, sov)] = value
    except Exception as e:
        st.error(f"mtid_mapping.json yüklenirken hata: {str(e)}")
        mtid_mapping = {}

    st.session_state.league_mapping = league_mapping
    st.session_state.mtid_mapping = mtid_mapping
    return True if league_mapping and mtid_mapping else False

# ==============================
# SIMILARITY
# ==============================
def calculate_similarity(api_odds: dict, match_odds: dict) -> float:
    def to_float(x):
        try:
            return float(x)
        except Exception:
            return None

    def prob(odd):
        odd = to_float(odd)
        if odd is None or odd <= 0:
            return None
        return 1.0 / odd

    def fair_trio(a, b, c):
        pa, pb, pc = prob(a), prob(b), prob(c)
        if None in (pa, pb, pc) or min(pa, pb, pc) <= 0:
            return None
        s = pa + pb + pc
        return (pa / s, pb / s, pc / s)

    def hellinger(p, q):
        return max(0.0, 1.0 - (math.sqrt((math.sqrt(p[0])-math.sqrt(q[0]))**2 +
                                         (math.sqrt(p[1])-math.sqrt(q[1]))**2 +
                                         (math.sqrt(p[2])-math.sqrt(q[2]))**2) / math.sqrt(2.0)))

    def rel_diff(pa, pb):
        if pa is None or pb is None or pa <= 0 or pb <= 0:
            return None
        return abs(pa - pb) / ((pa + pb) / 2.0)

    def bin_sim(key):
        if key not in api_odds or key not in match_odds:
            return None
        pa, pb = prob(api_odds[key]), prob(match_odds[key])
        d = rel_diff(pa, pb)
        if d is None:
            return None
        C = 3.5
        return math.exp(-C * d)

    def have(*keys):
        return all(k in api_odds and k in match_odds and to_float(api_odds[k]) and to_float(match_odds[k]) for k in keys)

    MS1, MSX, MS2 = "Maç Sonucu 1", "Maç Sonucu X", "Maç Sonucu 2"
    KG_V, KG_Y   = "Karşılıklı Gol Var", "Karşılıklı Gol Yok"
    O25U, O25A   = "2,5 Alt/Üst Üst", "2,5 Alt/Üst Alt"

    trio_api = fair_trio(api_odds.get(MS1), api_odds.get(MSX), api_odds.get(MS2))
    trio_mat = fair_trio(match_odds.get(MS1), match_odds.get(MSX), match_odds.get(MS2))
    if trio_api is None or trio_mat is None:
        return 0.0

    ms_sim = hellinger(trio_api, trio_mat)
    if ms_sim < 0.85:
        return round(ms_sim * 100.0, 2)

    per_leg_tol = 0.12
    for i in range(3):
        d = rel_diff(trio_api[i], trio_mat[i])
        if d is None or d > per_leg_tol:
            bad = 0.0 if d is None else max(0.0, 1.0 - d)
            return round(100.0 * min(bad, ms_sim), 2)

    high_list = [("__MS__", ms_sim, 1.0)]

    # KG
    s = bin_sim(KG_V)
    if s is not None: high_list.append((KG_V, s, 1.0))
    s = bin_sim(KG_Y)
    if s is not None: high_list.append((KG_Y, s, 1.0))

    # O/U 2.5
    s = bin_sim(O25U)
    if s is not None: high_list.append((O25U, s, 1.0))
    s = bin_sim(O25A)
    if s is not None: high_list.append((O25A, s, 1.0))

    # Double chance
    for k in ("Çifte Şans 1 veya X", "Çifte Şans 1 veya 2", "Çifte Şans X veya 2"):
        s = bin_sim(k)
        if s is not None: high_list.append((k, s, 0.5))

    # AH
    for k in ("Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2",
              "Handikaplı Maç Sonucu (1,0) 1", "Handikaplı Maç Sonucu (1,0) X", "Handikaplı Maç Sonucu (1,0) 2"):
        s = bin_sim(k)
        if s is not None: high_list.append((k, s, 1.0))

    MED_KEYS = [
        "1. Yarı Sonucu 1", "1. Yarı Sonucu X", "1. Yarı Sonucu 2",
        "0,5 Alt/Üst Alt", "0,5 Alt/Üst Üst",
        "1,5 Alt/Üst Alt", "1,5 Alt/Üst Üst",
        "3,5 Alt/Üst Alt", "3,5 Alt/Üst Üst",
        "4,5 Alt/Üst Alt", "4,5 Alt/Üst Üst",
        "2. Yarı Sonucu 1", "2. Yarı Sonucu X", "2. Yarı Sonucu 2",
        "Toplam Gol Aralığı 0-1 Gol", "Toplam Gol Aralığı 2-3 Gol",
        "Toplam Gol Aralığı 4-5 Gol", "Toplam Gol Aralığı 6+ Gol",
    ]

    high_keys = {name for (name, _, _) in high_list}
    med_list, low_list = [], []

    for k in MED_KEYS:
        s = bin_sim(k)
        if s is not None:
            w = 0.5 if "Alt/Üst" in k else 1.0
            med_list.append((k, s, w))

    for k in match_odds.keys():
        if k in (MS1, MSX, MS2) or k in high_keys or k in MED_KEYS:
            continue
        if ("Korner" in k) or ("Kart" in k):
            continue
        s = bin_sim(k)
        if s is not None:
            low_list.append((k, s, 1.0))

    def weighted_mean(items):
        sw = sum(w for _, _, w in items)
        if sw == 0: return None, 0
        val = sum(s * w for _, s, w in items) / sw
        return val, len(items)

    high_sim, high_n = weighted_mean(high_list)
    med_sim,  med_n  = weighted_mean(med_list)
    low_sim,  low_n  = weighted_mean(low_list)

    def shrink(val, n, target):
        if val is None or n <= 0: return None
        f = math.sqrt(min(n, target) / float(target))
        return val * f

    high_sim = shrink(high_sim, high_n, 6)
    med_sim  = shrink(med_sim,  med_n, 6)
    low_sim  = shrink(low_sim,  low_n, 6)

    W_HIGH, W_MED, W_LOW = 0.65, 0.25, 0.10
    total, wsum = 0.0, 0.0
    for sim, w in ((high_sim, W_HIGH), (med_sim, W_MED), (low_sim, W_LOW)):
        if sim is not None: total += sim * w; wsum += w
    if wsum == 0: return 0.0
    score = total / wsum

    anchors = 0
    if have(MS1, MSX, MS2): anchors += 1
    if have(KG_V, KG_Y):     anchors += 1
    if have(O25U, O25A):     anchors += 1
    ah_has = any(k in match_odds for k in (
        "Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2",
        "Handikaplı Maç Sonucu (1,0) 1",  "Handikaplı Maç Sonucu (1,0) X",  "Handikaplı Maç Sonucu (1,0) 2"))
    if ah_has: anchors += 1

    if anchors < 2:
        score = min(score, 0.85)

    return round(score * 100.0, 2)

# ==============================
# PREDICTION CRITERIA
# ==============================
prediction_criteria = {
    "Maç Sonucu 1": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) > int(r["MS SKOR"].split("-")[1]),
        "mtid": 1, "sov": None, "oca_key": "1", "column_name": "Maç Sonucu 1",
    },
    "Maç Sonucu X": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) == int(r["MS SKOR"].split("-")[1]),
        "mtid": 1, "sov": None, "oca_key": "2", "column_name": "Maç Sonucu X",
    },
    "Maç Sonucu 2": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) < int(r["MS SKOR"].split("-")[1]),
        "mtid": 1, "sov": None, "oca_key": "3", "column_name": "Maç Sonucu 2",
    },

    "İlk Yarı Karşılıklı Gol Var": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) > 0 and int(r["IY SKOR"].split("-")[1]) > 0,
        "mtid": 452, "sov": None, "oca_key": "1", "column_name": "Karşılıklı Gol Var",
    },
    "İlk Yarı 0,5 Gol Üst": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and sum(map(int, r["IY SKOR"].split("-"))) > 0,
        "mtid": 209, "sov": 0.50, "oca_key": "2", "column_name": "1. Yarı 0,5 Alt/Üst Üst",
    },
    "İlk Yarı 1,5 Gol Üst": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and sum(map(int, r["IY SKOR"].split("-"))) > 1,
        "mtid": 14, "sov": 1.50, "oca_key": "2", "column_name": "1. Yarı 1,5 Alt/Üst Üst",
    },

    "Toplam Gol 2,5 Gol Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and sum(map(int, r["MS SKOR"].split("-"))) > 2,
        "mtid": 12, "sov": 2.50, "oca_key": "2", "column_name": "2,5 Alt/Üst Üst",
    },
    "Toplam Gol 2,5 Gol Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and sum(map(int, r["MS SKOR"].split("-"))) < 3,
        "mtid": 12, "sov": 2.50, "oca_key": "1", "column_name": "2,5 Alt/Üst Alt",
    },

    "1. Yarı Sonucu 1": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) > int(r["IY SKOR"].split("-")[1]),
        "mtid": 7, "sov": None, "oca_key": "1", "column_name": "1. Yarı Sonucu 1",
    },
    "1. Yarı Sonucu X": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) == int(r["IY SKOR"].split("-")[1]),
        "mtid": 7, "sov": None, "oca_key": "2", "column_name": "1. Yarı Sonucu X",
    },
    "1. Yarı Sonucu 2": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) < int(r["IY SKOR"].split("-")[1]),
        "mtid": 7, "sov": None, "oca_key": "3", "column_name": "1. Yarı Sonucu 2",
    },

    "Handikaplı Maç Sonucu (-1,0) 1": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) >= int(r["MS SKOR"].split("-")[1]) + 2,
        "mtid": 268, "sov": -1.0, "oca_key": "1",
        "column_name": "Handikaplı Maç Sonucu (-1,0) 1",
        "display_name": "Handikaplı Maç Sonucu (0,1) 1",
    },
    "Handikaplı Maç Sonucu (-1,0) X": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) == int(r["MS SKOR"].split("-")[1]) + 1,
        "mtid": 268, "sov": -1.0, "oca_key": "2",
        "column_name": "Handikaplı Maç Sonucu (-1,0) X",
        "display_name": "Handikaplı Maç Sonucu (0,1) X",
    },
    "Handikaplı Maç Sonucu (-1,0) 2": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) <= int(r["MS SKOR"].split("-")[1]),
        "mtid": 268, "sov": -1.0, "oca_key": "3",
        "column_name": "Handikaplı Maç Sonucu (-1,0) 2",
        "display_name": "Handikaplı Maç Sonucu (0,1) 2",
    },

    "Handikaplı Maç Sonucu (1,0) 1": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) >= int(r["MS SKOR"].split("-")[1]),
        "mtid": 268, "sov": 1.0, "oca_key": "1", "column_name": "Handikaplı Maç Sonucu (1,0) 1",
    },
    "Handikaplı Maç Sonucu (1,0) X": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[1]) == int(r["MS SKOR"].split("-")[0]) + 1,
        "mtid": 268, "sov": 1.0, "oca_key": "2", "column_name": "Handikaplı Maç Sonucu (1,0) X",
    },
    "Handikaplı Maç Sonucu (1,0) 2": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[1]) >= int(r["MS SKOR"].split("-")[0]) + 2,
        "mtid": 268, "sov": 1.0, "oca_key": "3", "column_name": "Handikaplı Maç Sonucu (1,0) 2",
    },

    "İlk Yarı/Maç Sonucu 1/1": {
        "func": lambda r: r.get("IY SKOR") and r.get("MS SKOR") and "-" in r["IY SKOR"] and "-" in r["MS SKOR"] and int(r["IY SKOR"].split("-")[0]) > int(r["IY SKOR"].split("-")[1]) and int(r["MS SKOR"].split("-")[0]) > int(r["MS SKOR"].split("-")[1]),
        "mtid": 5, "sov": None, "oca_key": "1", "column_name": "İlk Yarı/Maç Sonucu 1/1",
    },
    "İlk Yarı/Maç Sonucu 1/X": {
        "func": lambda r: r.get("IY SKOR") and r.get("MS SKOR") and "-" in r["IY SKOR"] and "-" in r["MS SKOR"] and int(r["IY SKOR"].split("-")[0]) > int(r["IY SKOR"].split("-")[1]) and int(r["MS SKOR"].split("-")[0]) == int(r["MS SKOR"].split("-")[1]),
        "mtid": 5, "sov": None, "oca_key": "2", "column_name": "İlk Yarı/Maç Sonucu 1/X",
    },
    "İlk Yarı/Maç Sonucu 1/2": {
        "func": lambda r: r.get("IY SKOR") and r.get("MS SKOR") and "-" in r["IY SKOR"] and "-" in r["MS SKOR"] and int(r["IY SKOR"].split("-")[0]) > int(r["IY SKOR"].split("-")[1]) and int(r["MS SKOR"].split("-")[0]) < int(r["MS SKOR"].split("-")[1]),
        "mtid": 5, "sov": None, "oca_key": "3", "column_name": "İlk Yarı/Maç Sonucu 1/2",
    },
    "İlk Yarı/Maç Sonucu X/1": {
        "func": lambda r: r.get("IY SKOR") and r.get("MS SKOR") and "-" in r["IY SKOR"] and "-" in r["MS SKOR"] and int(r["IY SKOR"].split("-")[0]) == int(r["IY SKOR"].split("-")[1]) and int(r["MS SKOR"].split("-")[0]) > int(r["MS SKOR"].split("-")[1]),
        "mtid": 5, "sov": None, "oca_key": "4", "column_name": "İlk Yarı/Maç Sonucu X/1",
    },
    "İlk Yarı/Maç Sonucu X/X": {
        "func": lambda r: r.get("IY SKOR") and r.get("MS SKOR") and "-" in r["IY SKOR"] and "-" in r["MS SKOR"] and int(r["IY SKOR"].split("-")[0]) == int(r["IY SKOR"].split("-")[1]) and int(r["MS SKOR"].split("-")[0]) == int(r["MS SKOR"].split("-")[1]),
        "mtid": 5, "sov": None, "oca_key": "5", "column_name": "İlk Yarı/Maç Sonucu X/X",
    },
    "İlk Yarı/Maç Sonucu X/2": {
        "func": lambda r: r.get("IY SKOR") and r.get("MS SKOR") and "-" in r["IY SKOR"] and "-" in r["MS SKOR"] and int(r["IY SKOR"].split("-")[0]) == int(r["IY SKOR"].split("-")[1]) and int(r["MS SKOR"].split("-")[0]) < int(r["MS SKOR"].split("-")[1]),
        "mtid": 5, "sov": None, "oca_key": "6", "column_name": "İlk Yarı/Maç Sonucu X/2",
    },
    "İlk Yarı/Maç Sonucu 2/1": {
        "func": lambda r: r.get("IY SKOR") and r.get("MS SKOR") and "-" in r["IY SKOR"] and "-" in r["MS SKOR"] and int(r["IY SKOR"].split("-")[0]) < int(r["IY SKOR"].split("-")[1]) and int(r["MS SKOR"].split("-")[0]) > int(r["MS SKOR"].split("-")[1]),
        "mtid": 5, "sov": None, "oca_key": "7", "column_name": "İlk Yarı/Maç Sonucu 2/1",
    },
    "İlk Yarı/Maç Sonucu 2/X": {
        "func": lambda r: r.get("IY SKOR") and r.get("MS SKOR") and "-" in r["IY SKOR"] and "-" in r["MS SKOR"] and int(r["IY SKOR"].split("-")[0]) < int(r["IY SKOR"].split("-")[1]) and int(r["MS SKOR"].split("-")[0]) == int(r["MS SKOR"].split("-")[1]),
        "mtid": 5, "sov": None, "oca_key": "8", "column_name": "İlk Yarı/Maç Sonucu 2/X",
    },
    "İlk Yarı/Maç Sonucu 2/2": {
        "func": lambda r: r.get("IY SKOR") and r.get("MS SKOR") and "-" in r["IY SKOR"] and "-" in r["MS SKOR"] and int(r["IY SKOR"].split("-")[0]) < int(r["IY SKOR"].split("-")[1]) and int(r["MS SKOR"].split("-")[0]) < int(r["MS SKOR"].split("-")[1]),
        "mtid": 5, "sov": None, "oca_key": "9", "column_name": "İlk Yarı/Maç Sonucu 2/2",
    },

    "Maç Sonucu 1 ve 1,5 Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) > int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) < 2,
        "mtid": 342, "sov": 1.50, "oca_key": "1", "column_name": "Maç Sonucu ve (1,5) Alt/Üst 1 ve Alt",
    },
    "Maç Sonucu X ve 1,5 Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) == int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) < 2,
        "mtid": 342, "sov": 1.50, "oca_key": "2", "column_name": "Maç Sonucu ve (1,5) Alt/Üst X ve Alt",
    },
    "Maç Sonucu 2 ve 1,5 Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) < int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) < 2,
        "mtid": 342, "sov": 1.50, "oca_key": "3", "column_name": "Maç Sonucu ve (1,5) Alt/Üst 2 ve Alt",
    },
    "Maç Sonucu 1 ve 1,5 Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) > int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) > 1,
        "mtid": 342, "sov": 1.50, "oca_key": "4", "column_name": "Maç Sonucu ve (1,5) Alt/Üst 1 ve Üst",
    },
    "Maç Sonucu X ve 1,5 Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) == int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) > 1,
        "mtid": 342, "sov": 1.50, "oca_key": "5", "column_name": "Maç Sonucu ve (1,5) Alt/Üst X ve Üst",
    },
    "Maç Sonucu 2 ve 1,5 Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) < int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) > 1,
        "mtid": 342, "sov": 1.50, "oca_key": "6", "column_name": "Maç Sonucu ve (1,5) Alt/Üst 2 ve Üst",
    },

    "Maç Sonucu 1 ve 2,5 Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) > int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) < 3,
        "mtid": 343, "sov": 2.50, "oca_key": "1", "column_name": "Maç Sonucu ve (2,5) Alt/Üst 1 ve Alt",
    },
    "Maç Sonucu X ve 2,5 Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) == int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) < 3,
        "mtid": 343, "sov": 2.50, "oca_key": "2", "column_name": "Maç Sonucu ve (2,5) Alt/Üst X ve Alt",
    },
    "Maç Sonucu 2 ve 2,5 Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) < int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) < 3,
        "mtid": 343, "sov": 2.50, "oca_key": "3", "column_name": "Maç Sonucu ve (2,5) Alt/Üst 2 ve Alt",
    },
    "Maç Sonucu 1 ve 2,5 Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) > int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) > 2,
        "mtid": 343, "sov": 2.50, "oca_key": "4", "column_name": "Maç Sonucu ve (2,5) Alt/Üst 1 ve Üst",
    },
    "Maç Sonucu X ve 2,5 Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) == int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) > 2,
        "mtid": 343, "sov": 2.50, "oca_key": "5", "column_name": "Maç Sonucu ve (2,5) Alt/Üst X ve Üst",
    },
    "Maç Sonucu 2 ve 2,5 Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) < int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) > 2,
        "mtid": 343, "sov": 2.50, "oca_key": "6", "column_name": "Maç Sonucu ve (2,5) Alt/Üst 2 ve Üst",
    },

    "Maç Sonucu 1 ve 3,5 Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) > int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) < 4,
        "mtid": 272, "sov": 3.50, "oca_key": "1", "column_name": "Maç Sonucu ve (3,5) Alt/Üst 1 ve Alt",
    },
    "Maç Sonucu X ve 3,5 Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) == int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) < 4,
        "mtid": 272, "sov": 3.50, "oca_key": "2", "column_name": "Maç Sonucu ve (3,5) Alt/Üst X ve Alt",
    },
    "Maç Sonucu 2 ve 3,5 Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) < int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) < 4,
        "mtid": 272, "sov": 3.50, "oca_key": "3", "column_name": "Maç Sonucu ve (3,5) Alt/Üst 2 ve Alt",
    },
    "Maç Sonucu 1 ve 3,5 Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) > int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) > 3,
        "mtid": 272, "sov": 3.50, "oca_key": "4", "column_name": "Maç Sonucu ve (3,5) Alt/Üst 1 ve Üst",
    },
    "Maç Sonucu X ve 3,5 Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) == int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) > 3,
        "mtid": 272, "sov": 3.50, "oca_key": "5", "column_name": "Maç Sonucu ve (3,5) Alt/Üst X ve Üst",
    },
    "Maç Sonucu 2 ve 3,5 Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) < int(r["MS SKOR"].split("-")[1]) and sum(map(int, r["MS SKOR"].split("-"))) > 3,
        "mtid": 272, "sov": 3.50, "oca_key": "6", "column_name": "Maç Sonucu ve (3,5) Alt/Üst 2 ve Üst",
    },

    "Maç Sonucu 1 ve KG Var": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) > int(r["MS SKOR"].split("-")[1]) and int(r["MS SKOR"].split("-")[0]) > 0 and int(r["MS SKOR"].split("-")[1]) > 0,
        "mtid": 414, "sov": None, "oca_key": "1", "column_name": "Maç Sonucu 1 ve KG Var",
    },
    "Maç Sonucu X ve KG Var": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) == int(r["MS SKOR"].split("-")[1]) and int(r["MS SKOR"].split("-")[0]) > 0 and int(r["MS SKOR"].split("-")[1]) > 0,
        "mtid": 414, "sov": None, "oca_key": "3", "column_name": "Maç Sonucu X ve KG Var",
    },
    "Maç Sonucu 2 ve KG Var": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) < int(r["MS SKOR"].split("-")[1]) and int(r["MS SKOR"].split("-")[0]) > 0 and int(r["MS SKOR"].split("-")[1]) > 0,
        "mtid": 414, "sov": None, "oca_key": "5", "column_name": "Maç Sonucu 2 ve KG Var",
    },
    "Maç Sonucu 1 ve KG Yok": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) > int(r["MS SKOR"].split("-")[1]) and int(r["MS SKOR"].split("-")[1]) == 0,
        "mtid": 414, "sov": None, "oca_key": "2", "column_name": "Maç Sonucu 1 ve KG Yok",
    },
    "Maç Sonucu X ve KG Yok": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) == int(r["MS SKOR"].split("-")[1]) and int(r["MS SKOR"].split("-")[0]) == 0 and int(r["MS SKOR"].split("-")[1]) == 0,
        "mtid": 414, "sov": None, "oca_key": "4", "column_name": "Maç Sonucu X ve KG Yok",
    },
    "Maç Sonucu 2 ve KG Yok": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) == 0 and int(r["MS SKOR"].split("-")[1]) > 0,
        "mtid": 414, "sov": None, "oca_key": "6", "column_name": "Maç Sonucu 2 ve KG Yok",
    },

    "1.Y Sonucu 1 ve 1.Y 1,5 Alt": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) > int(r["IY SKOR"].split("-")[1]) and sum(map(int, r["IY SKOR"].split("-"))) < 2,
        "mtid": 459, "sov": 1.50, "oca_key": "1", "column_name": "1.Y Sonucu 1 ve 1.Y 1,5 Alt",
    },
    "1.Y Sonucu X ve 1.Y 1,5 Alt": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) == int(r["IY SKOR"].split("-")[1]) and sum(map(int, r["IY SKOR"].split("-"))) < 2,
        "mtid": 459, "sov": 1.50, "oca_key": "2", "column_name": "1.Y Sonucu X ve 1.Y 1,5 Alt",
    },
    "1.Y Sonucu 2 ve 1.Y 1,5 Alt": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) < int(r["IY SKOR"].split("-")[1]) and sum(map(int, r["IY SKOR"].split("-"))) < 2,
        "mtid": 459, "sov": 1.50, "oca_key": "3", "column_name": "1.Y Sonucu 2 ve 1.Y 1,5 Alt",
    },
    "1.Y Sonucu 1 ve 1.Y 1,5 Üst": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) > int(r["IY SKOR"].split("-")[1]) and sum(map(int, r["IY SKOR"].split("-"))) > 1,
        "mtid": 459, "sov": 1.50, "oca_key": "4", "column_name": "1.Y Sonucu 1 ve 1.Y 1,5 Üst",
    },
    "1.Y Sonucu X ve 1.Y 1,5 Üst": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) == int(r["IY SKOR"].split("-")[1]) and sum(map(int, r["IY SKOR"].split("-"))) > 1,
        "mtid": 459, "sov": 1.50, "oca_key": "5", "column_name": "1.Y Sonucu X ve 1.Y 1,5 Üst",
    },
    "1.Y Sonucu 2 ve 1.Y 1,5 Üst": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) < int(r["IY SKOR"].split("-")[1]) and sum(map(int, r["IY SKOR"].split("-"))) > 1,
        "mtid": 459, "sov": 1.50, "oca_key": "6", "column_name": "1.Y Sonucu 2 ve 1.Y 1,5 Üst",
    },

    "1. Yarı Sonucu 1 ve 1. Yarı KG Var": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) > int(r["IY SKOR"].split("-")[1]) and int(r["IY SKOR"].split("-")[0]) > 0 and int(r["IY SKOR"].split("-")[1]) > 0,
        "mtid": 416, "sov": None, "oca_key": "1", "column_name": "1. Yarı Sonucu 1 ve 1. Yarı KG Var",
    },
    "1. Yarı Sonucu X ve 1. Yarı KG Var": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) == int(r["IY SKOR"].split("-")[1]) and int(r["IY SKOR"].split("-")[0]) > 0 and int(r["IY SKOR"].split("-")[1]) > 0,
        "mtid": 416, "sov": None, "oca_key": "3", "column_name": "1. Yarı Sonucu X ve 1. Yarı KG Var",
    },
    "1. Yarı Sonucu 2 ve 1. Yarı KG Var": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) < int(r["IY SKOR"].split("-")[1]) and int(r["IY SKOR"].split("-")[0]) > 0 and int(r["IY SKOR"].split("-")[1]) > 0,
        "mtid": 416, "sov": None, "oca_key": "5", "column_name": "1. Yarı Sonucu 2 ve 1. Yarı KG Var",
    },
    "1. Yarı Sonucu 1 ve 1. Yarı KG Yok": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) > int(r["IY SKOR"].split("-")[1]) and (int(r["IY SKOR"].split("-")[0]) > 0) and (int(r["IY SKOR"].split("-")[1]) == 0),
        "mtid": 416, "sov": None, "oca_key": "2", "column_name": "1. Yarı Sonucu 1 ve 1. Yarı KG Yok",
    },
    "1. Yarı Sonucu X ve 1. Yarı KG Yok": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) == int(r["IY SKOR"].split("-")[1]) and (int(r["IY SKOR"].split("-")[0]) == 0) and (int(r["IY SKOR"].split("-")[1]) == 0),
        "mtid": 416, "sov": None, "oca_key": "4", "column_name": "1. Yarı Sonucu X ve 1. Yarı KG Yok",
    },
    "1. Yarı Sonucu 2 ve 1. Yarı KG Yok": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) < int(r["IY SKOR"].split("-")[1]) and (int(r["IY SKOR"].split("-")[0]) == 0) and (int(r["IY SKOR"].split("-")[1]) > 0),
        "mtid": 416, "sov": None, "oca_key": "6", "column_name": "1. Yarı Sonucu 2 ve 1. Yarı KG Yok",
    },

    "2,5 Alt ve KG Var": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and sum(map(int, r["MS SKOR"].split("-"))) < 3 and int(r["MS SKOR"].split("-")[0]) > 0 and int(r["MS SKOR"].split("-")[1]) > 0,
        "mtid": 446, "sov": 2.50, "oca_key": "1", "column_name": "2,5 Alt ve KG Var",
    },
    "2,5 Alt ve KG Yok": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and ((int(r["MS SKOR"].split("-")[0]) == 0 and sum(map(int, r["MS SKOR"].split("-"))) < 3) or (int(r["MS SKOR"].split("-")[1]) == 0 and sum(map(int, r["MS SKOR"].split("-"))) < 3)),
        "mtid": 446, "sov": 2.50, "oca_key": "3", "column_name": "2,5 Alt ve KG Yok",
    },
    "2,5 Üst ve KG Var": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and sum(map(int, r["MS SKOR"].split("-"))) > 2 and int(r["MS SKOR"].split("-")[0]) > 0 and int(r["MS SKOR"].split("-")[1]) > 0,
        "mtid": 446, "sov": 2.50, "oca_key": "2", "column_name": "2,5 Üst ve KG Var",
    },
    "2,5 Üst ve KG Yok": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and ((int(r["MS SKOR"].split("-")[0]) == 0 and sum(map(int, r["MS SKOR"].split("-"))) > 2) or (int(r["MS SKOR"].split("-")[1]) == 0 and sum(map(int, r["MS SKOR"].split("-"))) > 2)),
        "mtid": 446, "sov": 2.50, "oca_key": "4", "column_name": "2,5 Üst ve KG Yok",
    },

    "2. Yarı KG Var": {
        "func": lambda r: r.get("MS SKOR") and r.get("IY SKOR") and "-" in r["MS SKOR"] and "-" in r["IY SKOR"] and (int(r["MS SKOR"].split("-")[0]) - int(r["IY SKOR"].split("-")[0])) > 0 and (int(r["MS SKOR"].split("-")[1]) - int(r["IY SKOR"].split("-")[1])) > 0,
        "mtid": 599, "sov": None, "oca_key": "1", "column_name": "2. Yarı KG Var",
    },
    "2. Yarı KG Yok": {
        "func": lambda r: r.get("MS SKOR") and r.get("IY SKOR") and "-" in r["MS SKOR"] and "-" in r["IY SKOR"] and (((int(r["MS SKOR"].split("-")[0]) - int(r["IY SKOR"].split("-")[0])) == 0 and (int(r["MS SKOR"].split("-")[1]) - int(r["IY SKOR"].split("-")[1])) > 0) or ((int(r["MS SKOR"].split("-")[0]) - int(r["IY SKOR"].split("-")[0])) > 0 and (int(r["MS SKOR"].split("-")[1]) - int(r["IY SKOR"].split("-")[1])) == 0)),
        "mtid": 599, "sov": None, "oca_key": "2", "column_name": "2. Yarı KG Yok",
    },

    "Ev Sahibi 1.Y 0,5 Gol Alt": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) < 1,
        "mtid": 455, "sov": 0.50, "oca_key": "1", "column_name": "Ev Sahibi 0,5 Alt/Üst Alt",
    },
    "Ev Sahibi 1.Y 0,5 Gol Üst": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[0]) > 0,
        "mtid": 455, "sov": 0.50, "oca_key": "2", "column_name": "Ev Sahibi 0,5 Alt/Üst Üst",
    },
    "Deplasman 1.Y 0,5 Gol Alt": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[1]) < 1,
        "mtid": 457, "sov": 0.50, "oca_key": "1", "column_name": "Deplasman 0,5 Alt/Üst Alt",
    },
    "Deplasman 1.Y 0,5 Gol Üst": {
        "func": lambda r: r.get("IY SKOR") and "-" in r["IY SKOR"] and int(r["IY SKOR"].split("-")[1]) > 0,
        "mtid": 457, "sov": 0.50, "oca_key": "2", "column_name": "Deplasman 0,5 Alt/Üst Üst",
    },

    "Ev Sahibi 1,5 Gol Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) < 2,
        "mtid": 20, "sov": 1.50, "oca_key": "1", "column_name": "Ev Sahibi 1,5 Alt/Üst Alt",
    },
    "Ev Sahibi 1,5 Gol Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) > 1,
        "mtid": 20, "sov": 1.50, "oca_key": "2", "column_name": "Ev Sahibi 1,5 Alt/Üst Üst",
    },
    "Ev Sahibi 2,5 Gol Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) < 3,
        "mtid": 326, "sov": 2.50, "oca_key": "1", "column_name": "Ev Sahibi 2,5 Alt/Üst Alt",
    },
    "Ev Sahibi 2,5 Gol Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[0]) > 2,
        "mtid": 326, "sov": 2.50, "oca_key": "2", "column_name": "Ev Sahibi 2,5 Alt/Üst Üst",
    },

    "Deplasman 1,5 Gol Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[1]) < 2,
        "mtid": 29, "sov": 1.50, "oca_key": "1", "column_name": "Deplasman 1,5 Alt/Üst Alt",
    },
    "Deplasman 1,5 Gol Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[1]) > 1,
        "mtid": 29, "sov": 1.50, "oca_key": "2", "column_name": "Deplasman 1,5 Alt/Üst Üst",
    },
    "Deplasman 2,5 Gol Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[1]) < 3,
        "mtid": 328, "sov": 2.50, "oca_key": "1", "column_name": "Deplasman 2,5 Alt/Üst Alt",
    },
    "Deplasman 2,5 Gol Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and int(r["MS SKOR"].split("-")[1]) > 2,
        "mtid": 328, "sov": 2.50, "oca_key": "2", "column_name": "Deplasman 2,5 Alt/Üst Üst",
    },
}

def calculate_predictions(group_rows, api_row):
    predictions = []
    match_rows = [r for r in group_rows if r and r.get("Benzerlik (%)", "") != "" and r.get("MS SKOR", "")]
    if not match_rows:
        return predictions

    # Skor baskınlıkları
    ms_scores = [r.get("MS SKOR", "") for r in match_rows if r.get("MS SKOR", "")]
    if ms_scores:
        counts = Counter(ms_scores)
        for score, cnt in counts.items():
            if cnt / len(match_rows) >= 0.65:
                predictions.append(f"Maç Skoru {score}: {cnt / len(match_rows) * 100:.1f}%")

    # Diğer kriterler
    for title, info in prediction_criteria.items():
        req_mtid = info["mtid"]
        req_sov  = info["sov"]
        req_key  = str(info["oca_key"])

        # API tarafında pazar var mı?
        api_mtids = set(api_row.get("MTIDs", []))
        if req_mtid not in api_mtids:
            continue

        # SOV eşleşmesi (varsa)
        if req_sov is not None:
            ok = False
            for m in api_row.get("MA", []):
                if m.get("MTID") == req_mtid:
                    try:
                        if float(m.get("SOV", 0)) == float(req_sov):
                            ok = True
                            break
                    except (ValueError, TypeError):
                        pass
            if not ok:
                continue

        # Geçmiş benzer satırlarda gerçekleşme oranı
        cnt = sum(1 for r in match_rows if info["func"](r))
        pct = (cnt / len(match_rows)) * 100.0
        if pct < 80.0:
            continue

        # Oran
        odds = None
        for m in api_row.get("MA", []):
            if m.get("MTID") != req_mtid:
                continue
            if req_sov is not None:
                try:
                    if float(m.get("SOV", 0)) != float(req_sov):
                        continue
                except (ValueError, TypeError):
                    continue
            for oca in m.get("OCA", []):
                if str(oca.get("N", "")) == req_key:
                    odds = oca.get("O")
                    break
            if odds is not None:
                break

        text = f"{title}: {pct:.1f}%"
        if odds is not None:
            try:
                text += f" (Oran {float(odds):.2f})"
            except Exception:
                pass
        predictions.append(text)

    return predictions[:10]  # max 10 tahmin

# ==============================
# FETCH & PROCESS API
# ==============================
def fetch_api_data():
    url = "https://bulten.nesine.com/api/bulten/getprebultendelta?marketVersion=1716908400&eventVersion=1716908400"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # EA listesi
        if isinstance(data, dict) and "sg" in data and "EA" in data["sg"]:
            return data["sg"]["EA"], data
        return [], {"error": "EA listesi bulunamadı"}
    except Exception as e:
        return [], {"error": str(e)}

def process_api_data(match_list, raw_data, start_dt, end_dt):
    status_placeholder.write("Bültendeki maçlar işleniyor...")
    time.sleep(0.05)

    api_rows = []
    for m in match_list:
        if not isinstance(m, dict):
            continue

        d = m.get("D", "")
        t = m.get("T", "")
        try:
            if not d or not t:
                continue
            mdt = datetime.strptime(f"{d} {t}", "%d.%m.%Y %H:%M").replace(tzinfo=IST)
        except Exception:
            continue

        if not (start_dt <= mdt <= end_dt):
            continue

        markets = m.get("MA", [])
        league_code = m.get("LC", None)
        league_name = st.session_state.league_mapping.get(league_code, str(league_code))

        row = {
            "Saat": t,
            "Tarih": d,
            "Ev Sahibi Takım": m.get("HN", ""),
            "Deplasman Takım": m.get("AN", ""),
            "Lig Adı": league_name,
            "İY/MS": "Var" if any(mm.get("MTID") == 5 for mm in markets) else "Yok",  # İY/MS MTID kontrolü
            "MTIDs": [mm.get("MTID") for mm in markets],
            "MA": markets,
            "_match_dt": mdt,
        }

        # MTID -> sütun isimleri eşleme
        filled = 0
        for market in markets:
            mtid = market.get("MTID")
            sov  = market.get("SOV")
            key  = (mtid, float(sov) if sov is not None else None) if isinstance(sov, (int, float, str)) else (mtid, None)
            if key not in st.session_state.mtid_mapping:
                # MTID bazlı (SOV'suz) fallback
                key = (mtid, None)
                if key not in st.session_state.mtid_mapping:
                    continue
            column_names = st.session_state.mtid_mapping.get(key, [])
            oca_list = market.get("OCA", [])
            for idx, oc in enumerate(oca_list):
                if idx >= len(column_names):
                    break
                try:
                    odd = oc.get("O")
                    if odd is None:
                        continue
                    row[column_names[idx]] = float(odd)
                    filled += 1
                except Exception:
                    pass

        row["Oran Sayısı"] = str(filled)
        api_rows.append(row)

    api_df = pd.DataFrame(api_rows)
    if api_df.empty:
        status_placeholder.write("Seçilen aralıkta uygun maç yok.")
        return api_df

    api_df = api_df.sort_values(by="_match_dt").reset_index(drop=True)
    api_df = api_df.drop(columns=["_match_dt"])
    status_placeholder.write(f"Bültenden {len(api_df)} maç işlendi.")
    return api_df

# ==============================
# FIND SIMILAR MATCHES (with GLOBAL)
# ==============================
def find_similar_matches(api_df, data):
    status_placeholder.write("Maçlar analiz ediliyor...")
    time.sleep(0.05)

    output_rows = []
    league_values = set(st.session_state.league_mapping.values())

    # Minimum ortak oran sayısı
    MIN_COLS = 5

    # Her API maçı için
    for _, api_row in api_df.iterrows():
        # API odds (sadece sayısal kolonlar)
        numeric_cols = [c for c in data.columns if c not in ["Saat","Tarih","Lig Adı","Ev Sahibi Takım","Deplasman Takım","IY SKOR","MS SKOR","Tahmin"]]
        api_odds = {c: api_row[c] for c in numeric_cols if c in api_row and pd.notna(api_row[c])}
        if len(api_odds) < MIN_COLS:
            continue

        api_league = api_row["Lig Adı"]
        same_league_df  = data[data["Lig Adı"] == api_league] if api_league in league_values else pd.DataFrame()
        other_league_df = data[data["Lig Adı"] != api_league]

        # Ortak kolonlar
        common_same  = [c for c in api_odds.keys() if c in same_league_df.columns] if not same_league_df.empty else []
        common_other = [c for c in api_odds.keys() if c in other_league_df.columns] if not other_league_df.empty else []

        # Başlık satırı (API maçı) — İY/MS ekliyoruz
        header = {
            "Benzerlik (%)": "",
            "Saat": api_row["Saat"],
            "Tarih": api_row["Tarih"],
            "Ev Sahibi Takım": api_row["Ev Sahibi Takım"],
            "Deplasman Takım": api_row["Deplasman Takım"],
            "Lig Adı": api_row["Lig Adı"],
            "IY SKOR": "",
            "MS SKOR": "",
            "Tahmin": "",
            "İY/MS": api_row.get("İY/MS", "Yok"),
            "MTIDs": api_row.get("MTIDs", []),
            "MA": api_row.get("MA", []),
        }
        output_rows.append(header)

        # Lig içi benzerler
        league_sim = []
        if not same_league_df.empty and len(common_same) >= MIN_COLS:
            for _, r in same_league_df.iterrows():
                row_odds = {c: r[c] for c in common_same if pd.notna(r[c])}
                if len(row_odds) < MIN_COLS:
                    continue
                sim = calculate_similarity(api_odds, row_odds)
                if np.isnan(sim) or sim < 70:
                    continue
                # tarihe göre ikincil sıralama
                try:
                    md = pd.to_datetime(str(r.get("Tarih","01.01.2000")) + " " + str(r.get("Saat","00:00")), format="%d.%m.%Y %H:%M", errors="coerce")
                except Exception:
                    md = pd.NaT
                league_sim.append((sim, md, r))

            league_sim.sort(key=lambda x: (-x[0], x[1] if not pd.isna(x[1]) else pd.Timestamp.min))
            league_sim = league_sim[:5]

        # Global benzerler
        global_sim = []
        if not other_league_df.empty and len(common_other) >= MIN_COLS:
            # yükü azalt
            if len(other_league_df) > 4000:
                other_league_df = other_league_df.sample(4000, random_state=1)
            for _, r in other_league_df.iterrows():
                row_odds = {c: r[c] for c in common_other if pd.notna(r[c])}
                if len(row_odds) < MIN_COLS:
                    continue
                sim = calculate_similarity(api_odds, row_odds)
                if np.isnan(sim) or sim < 70:
                    continue
                try:
                    md = pd.to_datetime(str(r.get("Tarih","01.01.2000")) + " " + str(r.get("Saat","00:00")), format="%d.%m.%Y %H:%M", errors="coerce")
                except Exception:
                    md = pd.NaT
                global_sim.append((sim, md, r))

            global_sim.sort(key=lambda x: (-x[0], x[1] if not pd.isna(x[1]) else pd.Timestamp.min))
            global_sim = global_sim[:5]

        # 10 satırlık blok (5 lig + 5 global). Tahminleri bu satırlara dağıtacağız.
        combined = league_sim + global_sim
        combined = combined[:10]

        # Benzer satırlar -> display rows
        similar_rows = []
        for sim, md, r in combined:
            similar_rows.append({
                "Benzerlik (%)": f"{sim:.2f}%",
                "Saat": "",
                "Tarih": str(r.get("Tarih","")),
                "Ev Sahibi Takım": str(r.get("Ev Sahibi Takım","")),
                "Deplasman Takım": str(r.get("Deplasman Takım","")),
                "Lig Adı": str(r.get("Lig Adı","")),
                "IY SKOR": str(r.get("IY SKOR","")),
                "MS SKOR": str(r.get("MS SKOR","")),
                "Tahmin": "",
            })

        # Tahminleri hesapla (benzer satırları kriter bazlı ölçüyor)
        preds = calculate_predictions(similar_rows, header)

        # Tahminleri 10 satıra paylaştır (v26 tarzı: her satırda 1 tahmin olacak şekilde)
        for i in range(min(len(preds), len(similar_rows))):
            similar_rows[i]["Tahmin"] = preds[i]

        # Gruplamayı kapat
        output_rows.extend(similar_rows)
        output_rows.append({})  # ayraç

    status_placeholder.write(f"Analiz tamamlandı, {len([r for r in output_rows if r])} satır bulundu.")
    return output_rows

# ==============================
# DATAFRAME STYLING
# ==============================
def style_dataframe(df):
    # Grup başlıklarını (Benzerlik boş) farklı renkte gösterelim
    def style_row(row):
        if row["Benzerlik (%)"] == "":
            return ['background-color: #02a7f2'] * len(row)
        return [''] * len(row)

    styler = df.style.apply(style_row, axis=1)

    # Tahmin sütunu: kırmızı + kalın + satır sonlarını koru (çok satır)
    styler = styler.set_properties(
        subset=["Tahmin"],
        **{"color": "#D00000", "font-weight": "700", "white-space": "pre-wrap"}
    )

    return styler


# ==============================
# UI: TIME RANGE
# ==============================
st.subheader("Analiz için Saat Aralığı")
default_start = datetime.now(IST) + timedelta(minutes=5)
st.write(f"Başlangıç Saati: {default_start.strftime('%d.%m.%Y %H:%M')} (Otomatik, şu an + 5 dakika)")

end_date = st.date_input("Bitiş Tarihi", value=datetime.now(IST).date())
end_time = st.time_input("Bitiş Saati", value=None)

# ==============================
# RUN
# ==============================
if st.button("Analize Başla", disabled=st.session_state.analysis_done):
    if end_time is None:
        st.error("Lütfen bitiş saati seçin!")
        st.stop()

    try:
        with st.spinner("Analiz başladı..."):
            # JSON mappings
            status_placeholder.write("Bahis kodları yükleniyor...")
            if not load_json_mappings():
                st.error("JSON mappingler yüklenemedi!")
                st.stop()

            end_dt   = datetime.combine(end_date, end_time).replace(tzinfo=IST)
            start_dt = default_start
            if end_dt <= start_dt:
                st.error("Bitiş saati başlangıç saatinden önce olamaz!")
                st.stop()

            # Excel
            status_placeholder.write("Geçmiş maç verileri indiriliyor...")
            time.sleep(0.05)
            download(f"https://drive.google.com/uc?id={EXCEL_FILE_ID}", "matches.xlsx", quiet=False)

            status_placeholder.write("Benzer oranlı maçlar yükleniyor...")
            time.sleep(0.05)
            data = pd.read_excel("matches.xlsx", sheet_name="Bahisler", dtype=str)

            # Gerekli sütun kontrolü
            required = ["Tarih", "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY SKOR", "MS SKOR"]
            miss = [c for c in required if c not in data.columns]
            if miss:
                st.error(f"Excel dosyasında eksik sütunlar: {', '.join(miss)}")
                st.stop()

            # Oran kolonları: sayıya çevir (1.00 altı -> NaN)
            numeric_candidates = [v.get("column_name") for v in prediction_criteria.values() if v.get("column_name")]
            for col in numeric_candidates:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce')
                    data.loc[:, col] = data[col].where(data[col] > 1.0, np.nan)

            st.session_state.data = data

            # API
            status_placeholder.write("Bülten verisi çekiliyor...")
            time.sleep(0.05)
            match_list, raw = fetch_api_data()
            if not match_list:
                st.error(f"Bülten verisi alınamadı. Hata: {raw.get('error', 'Bilinmeyen hata')}")
                st.stop()

            api_df = process_api_data(match_list, raw, start_dt, end_dt)
            if api_df.empty:
                st.error("Seçilen saat aralığında maç bulunamadı.")
                st.stop()

            st.write(f"Bültenden çekilen maç sayısı: {len(match_list)}")
            st.write(f"İşlenen maçlar: {len(api_df)}")

            # Benzerler + Tahminler
            output_rows = find_similar_matches(api_df, data)
            if not output_rows:
                st.error("Eşleşme bulunamadı. Lütfen verileri kontrol edin.")
                st.stop()

            # İY/MS ve Normal bülten ayrımı (başlık satırındaki İY/MS'e göre)
            iyms_rows, normal_rows = [], []
            group, is_iyms = [], False
            for r in output_rows:
                if not r:
                    if group:
                        (iyms_rows if is_iyms else normal_rows).extend(group + [{}])
                    group = []
                    continue
                if r.get("Benzerlik (%)","") == "":
                    # yeni grup başlığı
                    if group:
                        (iyms_rows if is_iyms else normal_rows).extend(group + [{}])
                    group = [r]
                    is_iyms = (r.get("İY/MS","Yok") == "Var")
                else:
                    group.append(r)
            if group:
                (iyms_rows if is_iyms else normal_rows).extend(group)

            cols = ["Benzerlik (%)","Saat","Tarih","Ev Sahibi Takım","Deplasman Takım","Lig Adı","IY SKOR","MS SKOR","Tahmin"]
            iyms_df  = pd.DataFrame([x for x in iyms_rows if x], columns=cols)
            main_df  = pd.DataFrame([x for x in normal_rows if x], columns=cols)

            st.session_state.iyms_df = iyms_df
            st.session_state.main_df = main_df
            st.session_state.output_rows = output_rows
            st.session_state.analysis_done = True

            st.success("Analiz tamamlandı!")

    except Exception as e:
        st.error(f"Hata oluştu: {str(e)}")
        st.stop()

# ==============================
# SHOW
# ==============================
if st.session_state.analysis_done and st.session_state.iyms_df is not None:
    status_placeholder.empty()
    tab1, tab2 = st.tabs(["İY/MS Bülteni", "Normal Bülten"])
    with tab1:
        st.dataframe(
            style_dataframe(st.session_state.iyms_df),  # <— styler kullan
            use_container_width=True,
            height=620,
            column_config={
                "Tahmin": st.column_config.TextColumn("Tahmin", width="large"),
            }
        )
    with tab2:
        st.dataframe(
            style_dataframe(st.session_state.main_df),  # <— styler kullan
            use_container_width=True,
            height=620,
            column_config={
                "Tahmin": st.column_config.TextColumn("Tahmin", width="large"),
            }
        )

# ============================================================
# LIGE GÖRE ANALIZ  —  EK BÖLÜM (ESKİ KODA DOKUNMA)
# ============================================================
import io
from typing import Dict, Tuple, List

st.markdown("---")
st.header("Lige Göre Analiz")

# ------------------------------
# Yardımcı: Güvenli sabitleri al
# ------------------------------
def _safe_get_constants():
    # Mevcut dosyadaki sabitleri kullan (varsa)
    league_id  = globals().get("LEAGUE_MAPPING_ID", "1L8HA_emD92BJSuCn-P9GJF-hH55nIKE7")
    mtid_id    = globals().get("MTID_MAPPING_ID",   "1N1PjFla683BYTAdzVDaajmcnmMB5wiiO")
    headers    = globals().get("HEADERS", {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nesine.com/",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Connection": "keep-alive",
        "X-Requested-With": "XMLHttpRequest",
    })
    ist       = globals().get("IST", timezone(timedelta(hours=3)))
    return league_id, mtid_id, headers, ist

LEAGUE_MAPPING_ID_SAFE, MTID_MAPPING_ID_SAFE, HEADERS_SAFE, IST_SAFE = _safe_get_constants()

# ------------------------------
# Analiz JSON linkleri (senin verdiğin)
# ------------------------------
_ANALYSIS_JSON_LINKS = {
    "0dan0.json":        "1vjR6tzfnf-Iwd5KetfrvopP9YHvfyW1G",
    "0dan1.json":        "1mRIItyxiAXGrvHXjXahBSzScyKRSQ0cu",
    "0dan2.json":        "1XbjcBWygjkyY_mzkMv74BcUO6L29kN5W",
    "1den0.json":        "1lLWNvAwmwB6_QtmoAk_D4bX6DO_yIaW-",
    "1den2.json":        "12V4EWHQfrfPB0-9D4jyN63wScR57o-FE",
    "2.5_alt.json":      "1q53CchXhowrDR-fBnwbGgUg4a1WJcx_8",
    "2.5_üst.json":      "1dX9VloFS7M84W2ZCV_tPyJ6narfQqtMy",
    "2den0.json":        "1vjlIzjKia0Nu9KchiFN91TWQxxgirPfv",
    "2den1.json":        "1048WEM2tW8tWU1eewQtZQVGlITfNWAxT",
    "handikap-1_0.json": "186WjR3aqdFbrwM26kL5KB71HXx4bKlZS",
    "handikap1_0.json":  "1aqjrRaFx4jPxxEKzQx0rY-Rurn-_7TGx",
    "iy_1-1_ms_+4.json": "1t3N5EnUfeGmQplz7_ayYGTcsNPBOM5dD",
    "iy_1.5_üst.json":   "1bggqLhLqQ4B17QMeEGqU7G7WL3YkVku3",
    "iy_kg_var.json":    "14G-sul2odfWTRW8kkmW1uA7fgUNQcyi_",
    "ms1_2.5_üst.json":  "1jZfMzxIT19dUEbcoerSRR0S5Wgrn8mIK",
    "ms2_2.5_üst.json":  "1XWqVjZpSitlcmalitv8vKfgbCMLfcHwQ",
    "ms_kg_var.json":    "1QHDBqEIYXNsjuwlZNMHgGBcTspiTjF57",
    "ms_kg_yok.json":    "14u3Pz1V5m536ZOn8QHvRatjNLMf1ObgP",
}

# Her JSON için gerekli MTID/SOV/N (senin örneğinle birebir)
_JSON_REQUIREMENTS: Dict[str, Dict] = {
    "0dan0.json":        {"mtid": 5,   "sov": 0.00, "n": 5},
    "0dan1.json":        {"mtid": 5,   "sov": 0.00, "n": 4},
    "0dan2.json":        {"mtid": 5,   "sov": 0.00, "n": 6},
    "1den0.json":        {"mtid": 5,   "sov": 0.00, "n": 2},
    "1den2.json":        {"mtid": 5,   "sov": 0.00, "n": 3},
    "2.5_alt.json":      {"mtid": 12,  "sov": 2.50, "n": 1},
    "2.5_üst.json":      {"mtid": 12,  "sov": 2.50, "n": 2},
    "2den0.json":        {"mtid": 5,   "sov": 0.00, "n": 8},
    "2den1.json":        {"mtid": 5,   "sov": 0.00, "n": 7},
    "handikap-1_0.json": {"mtid": 268, "sov": -1.0, "n": 2},
    "handikap1_0.json":  {"mtid": 268, "sov": 1.0,  "n": 2},
    "iy_1-1_ms_+4.json": {"mtid": 571, "sov": None, "n": 18},
    "iy_1.5_üst.json":   {"mtid": 14,  "sov": 1.50, "n": 2},
    "iy_kg_var.json":    {"mtid": 452, "sov": 0.00, "n": 1},
    "ms1_2.5_üst.json":  {"mtid": 343, "sov": 2.50, "n": 4},
    "ms2_2.5_üst.json":  {"mtid": 343, "sov": 2.50, "n": 6},
    "ms_kg_var.json":    {"mtid": 38,  "sov": 0.00, "n": 1},
    "ms_kg_yok.json":    {"mtid": 38,  "sov": 0.00, "n": 2},
}

# Risk grupları (senin liste)
def _get_risk_groups():
    return {
        "0dan0.json": ["0dan1.json", "0dan2.json", "1den0.json", "1den2.json", "2den0.json", "ms1_2.5_üst.json", "ms2_2.5_üst.json", "handikap1_0.json", "handikap-1_0.json"],
        "0dan1.json": ["0dan0.json", "0dan2.json", "1den0.json", "1den2.json", "2den0.json", "2den1.json", "handikap1_0.json", "ms2_2.5_üst.json"],
        "0dan2.json": ["0dan0.json", "0dan1.json", "1den0.json", "1den2.json", "2den0.json", "2den1.json", "handikap-1_0.json", "ms1_2.5_üst.json"],
        "1den0.json": ["0dan0.json", "0dan1.json", "0dan2.json", "1den2.json", "2den0.json", "2den1.json", "ms1_2.5_üst.json", "ms2_2.5_üst.json", "handikap1_0.json", "handikap-1_0.json", "ms_kg_yok.json", "iy_1-1_ms_+4.json"],
        "1den2.json": ["0dan0.json", "0dan1.json", "0dan2.json", "1den0.json", "2den0.json", "2den1.json", "ms1_2.5_üst.json", "handikap-1_0.json", "ms_kg_yok.json", "2.5_alt.json", "iy_1-1_ms_+4.json"],
        "2.5_alt.json": ["1den2.json", "2.5_üst.json", "2den1.json", "iy_1-1_ms_+4.json", "ms1_2.5_üst.json", "ms2_2.5_üst.json"],
        "2.5_üst.json": ["2.5_alt.json"],
        "2den0.json": ["0dan0.json", "0dan1.json", "0dan2.json", "1den0.json", "1den2.json", "2den1.json", "handikap-1_0.json", "handikap1_0.json", "iy_1-1_ms_+4.json", "ms1_2.5_üst.json", "ms2_2.5_üst.json", "ms_kg_yok.json"],
        "2den1.json": ["0dan0.json", "0dan1.json", "0dan2.json", "1den0.json", "1den2.json", "2.5_alt.json", "2den0.json", "handikap1_0.json", "iy_1-1_ms_+4.json", "ms2_2.5_üst.json", "ms_kg_yok.json"],
        "handikap-1_0.json": ["0dan0.json", "0dan2.json", "1den0.json", "1den2.json", "2den0.json", "handikap1_0.json", "ms2_2.5_üst.json"],
        "handikap1_0.json": ["0dan0.json", "0dan1.json", "1den0.json", "2den0.json", "2den1.json", "handikap-1_0.json", "ms1_2.5_üst.json"],
        "iy_1-1_ms_+4.json": ["0dan0.json", "0dan2.json", "1den0.json", "1den2.json", "2.5_alt.json", "2den0.json", "2den1.json", "ms_kg_yok.json"],
        "iy_kg_var.json": ["ms_kg_yok.json"],
        "ms1_2.5_üst.json": ["0dan0.json", "0dan2.json", "1den0.json", "1den2.json", "2.5_alt.json", "2den0.json", "handikap1_0.json", "ms2_2.5_üst.json"],
        "ms2_2.5_üst.json": ["0dan0.json", "0dan1.json", "1den0.json", "2.5_alt.json", "2den0.json", "2den1.json", "handikap-1_0.json", "ms1_2.5_üst.json"],
        "ms_kg_var.json": ["ms_kg_yok.json"],
        "ms_kg_yok.json": ["1den0.json", "1den2.json", "2den0.json", "2den1.json", "iy_1-1_ms_+4.json", "iy_kg_var.json", "ms_kg_var.json"],
    }

# Sinyal grupları (senin liste)
def _get_signal_groups():
    return {
        "0dan1.json": ["handikap-1_0.json", "ms1_2.5_üst.json"],
        "0dan2.json": ["handikap1_0.json", "ms2_2.5_üst.json"],
        "1den0.json": ["ms_kg_var.json"],
        "2den0.json": ["ms_kg_var.json"],
        "ms_kg_var.json": ["1den2.json", "1den0.json", "2den0.json", "2den1.json", "iy_1-1_ms_+4.json"],
        "2.5_üst.json": ["1den2.json", "2den1.json", "ms2_2.5_üst.json", "ms1_2.5_üst.json"],
    }

# ------------------------------
# JSON ve Mapping'leri yükle
# ------------------------------
def _download_json_to_file(file_id: str, local_name: str) -> bool:
    try:
        download(f"https://drive.google.com/uc?id={file_id}", local_name, quiet=True)
        return True
    except Exception as e:
        st.error(f"{local_name} indirilemedi: {e}")
        return False

def _load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"JSON okunamadı ({path}): {e}")
        return None

def _load_mappings():
    # Eğer mevcut uygulama zaten mappingleri yüklediyse onu kullan
    if st.session_state.get("league_mapping") and st.session_state.get("mtid_mapping"):
        return st.session_state.league_mapping, st.session_state.mtid_mapping

    # Yoksa indir
    _download_json_to_file(LEAGUE_MAPPING_ID_SAFE, "league_mapping.json")
    _download_json_to_file(MTID_MAPPING_ID_SAFE,   "mtid_mapping.json")

    league_data = _load_json("league_mapping.json") or {}
    league_mapping = {int(k): v for k, v in league_data.items()} if league_data else {}

    mtid_raw = _load_json("mtid_mapping.json") or {}
    mtid_mapping = {}
    for key_str, value in mtid_raw.items():
        if key_str.startswith("(") and key_str.endswith(")"):
            parts = key_str[1:-1].split(", ")
            if len(parts) == 2:
                mtid = int(parts[0])
                sov = None if parts[1] == "null" else float(parts[1])
                mtid_mapping[(mtid, sov)] = value

    # cache
    st.session_state.league_mapping = league_mapping
    st.session_state.mtid_mapping = mtid_mapping
    return league_mapping, mtid_mapping

def _load_analysis_jsons() -> Dict[str, dict]:
    out = {}
    for name, fid in _ANALYSIS_JSON_LINKS.items():
        local = f"analysis__{name}"
        if _download_json_to_file(fid, local):
            data = _load_json(local)
            if data is not None:
                out[name] = data
    return out

# ------------------------------
# API
# ------------------------------
def _fetch_api() -> List[dict]:
    # URL senin örnekteki gibi sabit
    url = "https://bulten.nesine.com/api/bulten/getprebultendelta?eventVersion=462376563&marketVersion=462376563&oddVersion=1712799325&_=1743545516827"
    try:
        r = requests.get(url, headers=HEADERS_SAFE, timeout=30)
        r.raise_for_status()
        j = r.json()
        if isinstance(j, dict) and "sg" in j and "EA" in j["sg"]:
            return j["sg"]["EA"]
        return []
    except Exception as e:
        st.error(f"API hatası: {e}")
        return []

def _parse_dt(d: str, t: str) -> datetime:
    try:
        return datetime.strptime(f"{d} {t}", "%d.%m.%Y %H:%M").replace(tzinfo=IST_SAFE)
    except Exception:
        return datetime.min.replace(tzinfo=IST_SAFE)

def _filter_by_window(rows: List[dict], start_dt: datetime, end_dt: datetime) -> List[dict]:
    out = []
    for m in rows:
        md = m.get("D",""); mt = m.get("T","")
        ts = _parse_dt(md, mt)
        if start_dt <= ts <= end_dt:
            out.append(m)
    return out

# ------------------------------
# Maç işleme
# ------------------------------
def _process_match(raw: dict, league_map: Dict[int,str], mtid_map: Dict[Tuple[int,float], List[str]]):
    league_id = raw.get("LC")
    league_name = league_map.get(league_id, str(league_id))

    markets = raw.get("MA", [])
    named_odds = {}             # {market_adı: oran}
    available: Dict[Tuple[int,float], Dict[int,float]] = {}  # {(mtid,sov): {N: oran}}

    for m in markets:
        mtid = m.get("MTID")
        sov  = m.get("SOV")
        try:
            sovf = float(sov) if sov is not None else None
        except Exception:
            sovf = None

        key = (mtid, sovf)
        available[key] = {}

        for oc in m.get("OCA", []):
            n = oc.get("N"); o = oc.get("O")
            try:
                if n is not None and o is not None:
                    available[key][int(n)] = float(o)
            except Exception:
                pass

        # İsme çevir ve sırayla doldur
        # Eğer (mtid, sov) yoksa (mtid, None) dene
        mapping_key = key if key in mtid_map else (mtid, None)
        if mapping_key in mtid_map:
            names = mtid_map[mapping_key]
            for idx, oc in enumerate(m.get("OCA", [])):
                if idx >= len(names): break
                try:
                    o = float(oc.get("O"))
                    named_odds[names[idx]] = o
                except Exception:
                    pass

    return {
        "Tarih": raw.get("D",""),
        "Saat":  raw.get("T",""),
        "Lig":   league_name,
        "Ev":    raw.get("HN",""),
        "Dep":   raw.get("AN",""),
        "Oranlar": named_odds,
        "Avail":   available,
        "DT": _parse_dt(raw.get("D",""), raw.get("T","")),
    }

def _get_specific_odd(match_info, mtid: int, sov, n: int):
    k = (mtid, sov)
    if k in match_info["Avail"] and n in match_info["Avail"][k]:
        return match_info["Avail"][k][n]
    k2 = (mtid, None)
    if k2 in match_info["Avail"] and n in match_info["Avail"][k2]:
        return match_info["Avail"][k2][n]
    return None

def _check_conditions(match_info, conds: dict, json_name: str, req_mtid: int, req_sov, req_n: int):
    odd_needed = _get_specific_odd(match_info, req_mtid, req_sov, req_n)
    if odd_needed is None:
        return False, 0, 0, None

    lig = match_info["Lig"]
    if lig not in conds:
        return False, 0, 0, odd_needed

    rules = conds[lig]
    total = len(rules)
    hit = 0
    for r in rules:
        mk = r.get("market"); mi = r.get("min_odds"); ma = r.get("max_odds")
        val = match_info["Oranlar"].get(mk)
        try:
            if val is not None and mi <= float(val) <= ma:
                hit += 1
        except Exception:
            pass

    if total <= 3: req = total
    elif total <= 6: req = int(total * 0.75)
    else: req = int(total * 0.60)

    return (hit >= req), hit, total, odd_needed

def _risk_status(current_json: str, matched_jsons: List[str], risk_groups: Dict[str, List[str]]):
    lst = risk_groups.get(current_json, [])
    for j in matched_jsons:
        if j in lst:
            return "Riskli"
    return "Güvenli" if current_json in risk_groups else "Bilinmiyor"

def _signal_info(current_json: str, matched_jsons: List[str], signal_groups: Dict[str, List[str]]):
    lst = signal_groups.get(current_json, [])
    cnt = sum(1 for j in matched_jsons if j in lst)
    if cnt >= 2:
        return "Sinyal", cnt, len(lst)
    return None, 0, len(lst)

# ------------------------------
# UI — form
# ------------------------------
with st.container(border=True):
    colA, colB = st.columns(2)

    now_ist = datetime.now(IST_SAFE)
    default_start = now_ist + timedelta(minutes=5)
    default_end   = default_start + timedelta(minutes=180)

    with colA:
        st.subheader("Analiz için Saat Aralığı")
        start_date = st.date_input("Başlangıç Tarihi", value=default_start.date(), format="DD.MM.YYYY")
        start_time = st.time_input("Başlangıç Saati", value=default_start.time())
    with colB:
        st.subheader("Bitiş")
        end_date = st.date_input("Bitiş Tarihi", value=default_end.date(), format="DD.MM.YYYY", key="lge_end_date")
        end_time = st.time_input("Bitiş Saati (HH:mm)", value=default_end.time(), key="lge_end_time")

    run_lga = st.button("Analize Başla (Lige Göre)")

# ------------------------------
# Çalıştır
# ------------------------------
if run_lga:
    status = st.empty()
    status.info("JSON eşleşmeleri ve mappingler yükleniyor...")

    league_map, mtid_map = _load_mappings()
    analysis_jsons = _load_analysis_jsons()
    risk_groups  = _get_risk_groups()
    signal_groups = _get_signal_groups()

    if not analysis_jsons:
        st.warning("Analiz için JSON dosyaları indirilemedi.")
        st.stop()

    status.info("API verisi çekiliyor...")
    api_rows = _fetch_api()
    if not api_rows:
        st.warning("API’den maç verisi alınamadı.")
        st.stop()

    st_dt = datetime.combine(start_date, start_time).replace(tzinfo=IST_SAFE)
    en_dt = datetime.combine(end_date,   end_time).replace(tzinfo=IST_SAFE)

    status.info("Zaman filtresi uygulanıyor...")
    filtered = _filter_by_window(api_rows, st_dt, en_dt)
    if not filtered:
        st.warning("Seçtiğiniz aralıkta maç bulunamadı.")
        st.stop()

    status.info("Maçlar işleniyor...")
    processed = [_process_match(m, league_map, mtid_map) for m in filtered]

    # Her maç için eşleşen JSON listesi
    matches_per_game: Dict[str, List[str]] = {}

    # Tüm sonuçlar: {json_name: [(match_info, hit, total, odd, risk)]}
    all_results: Dict[str, List[Tuple[dict,int,int,float,str]]] = {}

    status.info("Koşullar kontrol ediliyor...")
    for jname, jdata in analysis_jsons.items():
        req = _JSON_REQUIREMENTS.get(jname, {"mtid": None, "sov": None, "n": None})
        req_mtid, req_sov, req_n = req["mtid"], req["sov"], req["n"]
        bucket = []
        for mi in processed:
            ok, hit, total, odd = _check_conditions(mi, jdata, jname, req_mtid, req_sov, req_n)
            if ok:
                key = f"{mi['Ev']} vs {mi['Dep']} - {mi['Tarih']} {mi['Saat']}"
                matches_per_game.setdefault(key, []).append(jname)
                bucket.append((mi, hit, total, odd, ""))  # risk sonra
        all_results[jname] = bucket

    # Risk atamaları
    for jname, rows in all_results.items():
        for idx, (mi, hit, total, odd, _) in enumerate(rows):
            key = f"{mi['Ev']} vs {mi['Dep']} - {mi['Tarih']} {mi['Saat']}"
            others = [j for j in matches_per_game.get(key, []) if j != jname]
            rsk = _risk_status(jname, others, risk_groups)
            rows[idx] = (mi, hit, total, odd, rsk)

    status.success("Analiz tamamlandı. Görselleştiriliyor...")

    # ------------------------------
    # Görselleştirme (Excel GÖSTERME mantığı)
    # ------------------------------
    # 1) GENEL sekmesi
    genel_rows = []
    for jname, rows in all_results.items():
        for (mi, hit, total, odd, rsk) in sorted(rows, key=lambda x: x[0]["DT"]):
            genel_rows.append({
                "Kategori": jname.replace(".json", ""),
                "Tarih": mi["Tarih"],
                "Saat": mi["Saat"],
                "Lig": mi["Lig"],
                "Ev Sahibi": mi["Ev"],
                "Deplasman": mi["Dep"],
                "Eşleşen/Toplam": f"{hit}/{total}",
                "Oran": odd if odd is not None else "",
                "Risk": rsk,
            })
    df_genel = pd.DataFrame(genel_rows)

    # 2) SİNYAL sekmesi
    signal_rows = []
    for jname, rows in all_results.items():
        for (mi, hit, total, odd, rsk) in sorted(rows, key=lambda x: x[0]["DT"]):
            key = f"{mi['Ev']} vs {mi['Dep']} - {mi['Tarih']} {mi['Saat']}"
            others = [j for j in matches_per_game.get(key, []) if j != jname]
            sig, sig_hit, sig_total = _signal_info(jname, others, signal_groups)
            if sig:
                signal_rows.append({
                    "Kategori": jname.replace(".json", ""),
                    "Tarih": mi["Tarih"],
                    "Saat": mi["Saat"],
                    "Lig": mi["Lig"],
                    "Ev Sahibi": mi["Ev"],
                    "Deplasman": mi["Dep"],
                    "Eşleşen/Toplam": f"{hit}/{total}",
                    "Sinyal": f"{sig_hit}/{sig_total}",
                    "Oran": odd if odd is not None else "",
                })
    df_sinyal = pd.DataFrame(signal_rows)

    # 3) Per-JSON sekmeleri
    per_json_tabs = sorted(all_results.keys())

    # Sekmeler
    tabs = st.tabs(["Genel", "Sinyal"] + [n.replace(".json","") for n in per_json_tabs])

    with tabs[0]:
        st.subheader("Genel")
        if df_genel.empty:
            st.info("Genel sayfasında gösterilecek satır bulunamadı.")
        else:
            st.dataframe(df_genel, use_container_width=True, hide_index=True)

    with tabs[1]:
        st.subheader("Sinyal")
        if df_sinyal.empty:
            st.info("Sinyal sayfasında gösterilecek satır bulunamadı.")
        else:
            st.dataframe(df_sinyal, use_container_width=True, hide_index=True)

    for i, jname in enumerate(per_json_tabs, start=2):
        with tabs[i]:
            rows = [{
                "Tarih": mi["Tarih"], "Saat": mi["Saat"], "Lig": mi["Lig"],
                "Ev Sahibi": mi["Ev"], "Deplasman": mi["Dep"],
                "Eşleşen/Toplam": f"{hit}/{total}",
                "Oran": odd if odd is not None else "",
                "Risk": rsk,
            } for (mi, hit, total, odd, rsk) in sorted(all_results[jname], key=lambda x: x[0]["DT"])]
            df = pd.DataFrame(rows)
            st.subheader(jname.replace(".json",""))
            if df.empty:
                st.info("Kayıt bulunamadı.")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
