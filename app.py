import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, timezone
from gdown import download
from collections import Counter
import json
import math
import time

# --- Sabitler ---
IST = timezone(timedelta(hours=3))
LEAGUE_MAPPING_ID = "1L8HA_emD92BJSuCn-P9GJF-hH55nIKE7"
MTID_MAPPING_ID    = "1N1PjFla683BYTAdzVDaajmcnmMB5wiiO"
EXCEL_FILE_ID      = "11m7tX2xCavCM_cij69UaSVijFuFQbveM"

NESINE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nesine.com/",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Connection": "keep-alive",
    "X-Requested-With": "XMLHttpRequest",
}

# --- Görsel ayarlar ---
st.markdown("""
<style>
h1 { font-weight: bold; color: #05f705; }
.stDataFrame { font-size: 12px; width: 100%; overflow-x: auto; }
th { position: sticky; top: 0; background-color: #f0f0f0; z-index: 1; pointer-events: none; }
.stDataFrame th:hover { cursor: default; }
</style>
""", unsafe_allow_html=True)

st.title("Bülten Analiz")

# --- Session State ---
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

# --- Excel (oran) sütunları ---
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

# --- Tahmin kriterleri (v26 mantığına uygun temel set) ---
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
    "Toplam Gol 2,5 Gol Üst": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and (int(r["MS SKOR"].split("-")[0])+int(r["MS SKOR"].split("-")[1])) > 2,
        "mtid": 12, "sov": 2.50, "oca_key": "2", "column_name": "2,5 Alt/Üst Üst",
    },
    "Toplam Gol 2,5 Gol Alt": {
        "func": lambda r: r.get("MS SKOR") and "-" in r["MS SKOR"] and (int(r["MS SKOR"].split("-")[0])+int(r["MS SKOR"].split("-")[1])) < 3,
        "mtid": 12, "sov": 2.50, "oca_key": "1", "column_name": "2,5 Alt/Üst Alt",
    },
}

# --- JSON mappingleri yükle ---
def load_json_mappings() -> bool:
    try:
        download(f"https://drive.google.com/uc?id={LEAGUE_MAPPING_ID}", "league_mapping.json", quiet=True)
        with open("league_mapping.json", "r", encoding="utf-8") as f:
            league_data = json.load(f)
            st.session_state.league_mapping = {int(k): v for k, v in league_data.items()}

        download(f"https://drive.google.com/uc?id={MTID_MAPPING_ID}", "mtid_mapping.json", quiet=True)
        with open("mtid_mapping.json", "r", encoding="utf-8") as f:
            raw = json.load(f)
            m = {}
            for key_str, cols in raw.items():
                if key_str.startswith("(") and key_str.endswith(")"):
                    a, b = key_str[1:-1].split(", ")
                    mtid = int(a)
                    sov = None if b == "null" else float(b)
                    m[(mtid, sov)] = cols
            st.session_state.mtid_mapping = m
        return True
    except Exception as e:
        st.error(f"JSON mapping yüklenemedi: {e}")
        return False

# --- Nesine API ---
def fetch_api_data():
    url = "https://bulten.nesine.com/api/bulten/getprebultendelta?marketVersion=1716908400&eventVersion=1716908400"
    try:
        r = requests.get(url, headers=NESINE_HEADERS, timeout=30)
        r.raise_for_status()
        j = r.json()
        if isinstance(j, dict) and "sg" in j and "EA" in j["sg"]:
            return j["sg"]["EA"], j
        return [], {"error": "EA alanı bulunamadı"}
    except Exception as e:
        return [], {"error": str(e)}

# --- API verisini dataframe'e dönüştür ---
def process_api_data(match_list, start_dt, end_dt) -> pd.DataFrame:
    rows = []
    for m in match_list:
        if not isinstance(m, dict):
            continue
        d = m.get("D", ""); t = m.get("T", "")
        if not d or not t:
            continue
        try:
            mts = datetime.strptime(f"{d} {t}", "%d.%m.%Y %H:%M").replace(tzinfo=IST)
        except:
            continue
        if not (start_dt <= mts <= end_dt):
            continue

        league_code = m.get("LC")
        league_name = st.session_state.league_mapping.get(league_code, str(league_code))

        info = {
            "Saat": t,
            "Tarih": d,
            "Ev Sahibi Takım": m.get("HN",""),
            "Deplasman Takım": m.get("AN",""),
            "Lig Adı": league_name,
            # İY/MS MTID=5 var mı? (gruplama için kritik)
            "İY/MS": "Var" if any(mm.get("MTID")==5 for mm in m.get("MA", [])) else "Yok",
            "MTIDs": [mm.get("MTID") for mm in m.get("MA", [])],
            "MA": m.get("MA", []),
        }

        # Oranlara kolon eşle
        filled = 0
        for market in m.get("MA", []):
            mtid = market.get("MTID")
            sov  = market.get("SOV")
            key  = (mtid, float(sov) if sov is not None else None) if mtid in [11,12,13,14,15,20,29,155,268,272,326,328] else (mtid, None)
            if key not in st.session_state.mtid_mapping:
                continue
            cols = st.session_state.mtid_mapping[key]
            for i, outc in enumerate(market.get("OCA", [])):
                if i >= len(cols):
                    break
                odds = outc.get("O")
                if odds is None or not isinstance(odds, (int,float)):
                    continue
                info[cols[i]] = float(odds)
                filled += 1

        info["Oran Sayısı"] = str(filled)
        rows.append(info)

    api_df = pd.DataFrame(rows)
    if api_df.empty:
        return api_df

    # Eksik MS üçlüsü varsa default ver (benzerlik kapısına takılmasın)
    for col, val in [("Maç Sonucu 1", 2.0), ("Maç Sonucu X", 3.5), ("Maç Sonucu 2", 3.0)]:
        if col not in api_df.columns:
            api_df[col] = val

    # Sayısal dönüştürme
    for c in excel_columns:
        if c in api_df.columns:
            api_df[c] = pd.to_numeric(api_df[c], errors="coerce")
            api_df[c] = api_df[c].where(api_df[c] > 1.0, np.nan)

    return api_df

# --- Benzerlik (v26) ---
def calculate_similarity(api_odds: dict, match_odds: dict) -> float:
    def to_float(x):
        try:
            return float(x)
        except:
            return None

    def prob(o):
        o = to_float(o)
        if o is None or o <= 0: return None
        return 1.0 / o

    def fair_trio(a,b,c):
        pa,pb,pc = prob(a),prob(b),prob(c)
        if None in (pa,pb,pc) or min(pa,pb,pc) <= 0: return None
        s = pa+pb+pc
        return (pa/s, pb/s, pc/s)

    def hellinger(p,q):
        return max(0.0, 1.0 - (math.sqrt((math.sqrt(p[0])-math.sqrt(q[0]))**2 +
                                         (math.sqrt(p[1])-math.sqrt(q[1]))**2 +
                                         (math.sqrt(p[2])-math.sqrt(q[2]))**2) / math.sqrt(2.0)))

    def rel_diff(pa,pb):
        if pa is None or pb is None or pa<=0 or pb<=0: return None
        return abs(pa-pb)/((pa+pb)/2.0)

    def bin_sim(key):
        if key not in api_odds or key not in match_odds: return None
        pa,pb = prob(api_odds[key]), prob(match_odds[key])
        d = rel_diff(pa,pb)
        if d is None: return None
        C = 3.5
        return math.exp(-C*d)

    def have(*keys):
        return all(k in api_odds and k in match_odds and to_float(api_odds[k]) and to_float(match_odds[k]) for k in keys)

    MS1,MSX,MS2 = "Maç Sonucu 1","Maç Sonucu X","Maç Sonucu 2"
    KG_V,KG_Y   = "Karşılıklı Gol Var","Karşılıklı Gol Yok"
    O25U,O25A   = "2,5 Alt/Üst Üst","2,5 Alt/Üst Alt"

    # Kapı: MS üçlüsü
    trio_api = fair_trio(api_odds.get(MS1), api_odds.get(MSX), api_odds.get(MS2))
    trio_mat = fair_trio(match_odds.get(MS1), match_odds.get(MSX), match_odds.get(MS2))
    if trio_api is None or trio_mat is None:
        return 0.0

    ms_sim = hellinger(trio_api, trio_mat)
    if ms_sim < 0.85:
        return round(ms_sim*100.0, 2)

    # Bacak fark sınırı
    per_leg_tol = 0.12
    for i in range(3):
        d = rel_diff(trio_api[i], trio_mat[i])
        if d is None or d > per_leg_tol:
            bad = 0.0 if d is None else max(0.0, 1.0 - d)
            return round(bad*100.0, 2)

    # Grup benzerlikleri
    high_list = [("__MS__", ms_sim, 1.0)]

    s = bin_sim(KG_V);  high_list += [(KG_V, s, 1.0)] if s is not None else []
    s = bin_sim(KG_Y);  high_list += [(KG_Y, s, 1.0)] if s is not None else []
    s = bin_sim(O25U);  high_list += [(O25U, s, 1.0)] if s is not None else []
    s = bin_sim(O25A);  high_list += [(O25A, s, 1.0)] if s is not None else []

    for k in ("Çifte Şans 1 veya X","Çifte Şans 1 veya 2","Çifte Şans X veya 2"):
        s = bin_sim(k)
        if s is not None: high_list.append((k, s, 0.5))

    for k in ("Handikaplı Maç Sonucu (-1,0) 1","Handikaplı Maç Sonucu (-1,0) X","Handikaplı Maç Sonucu (-1,0) 2",
              "Handikaplı Maç Sonucu (1,0) 1","Handikaplı Maç Sonucu (1,0) X","Handikaplı Maç Sonucu (1,0) 2"):
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
    med_list = []
    for k in MED_KEYS:
        s = bin_sim(k)
        if s is not None:
            w = 0.5 if "Alt/Üst" in k else 1.0
            med_list.append((k, s, w))

    high_keys = {n for (n,_,_) in high_list}
    low_list = []
    for k in match_odds.keys():
        if k in (MS1,MSX,MS2) or k in high_keys or k in MED_KEYS: continue
        if ("Korner" in k) or ("Kart" in k): continue
        s = bin_sim(k)
        if s is not None: low_list.append((k, s, 1.0))

    def wmean(items):
        sw = sum(w for _,_,w in items)
        if sw == 0: return None, 0
        return sum(s*w for _,s,w in items)/sw, len(items)

    high_sim, hn = wmean(high_list)
    med_sim, mn = wmean(med_list)
    low_sim, ln = wmean(low_list)

    def shrink(val, n, tgt):
        if val is None or n<=0: return None
        f = math.sqrt(min(n,tgt)/float(tgt))
        return val*f

    high_sim = shrink(high_sim, hn, 6)
    med_sim  = shrink(med_sim,  mn, 6)
    low_sim  = shrink(low_sim,  ln, 6)

    W_HIGH, W_MED, W_LOW = 0.65, 0.25, 0.10
    total, wsum = 0.0, 0.0
    for sim,w in ((high_sim,W_HIGH),(med_sim,W_MED),(low_sim,W_LOW)):
        if sim is not None:
            total += sim*w; wsum += w
    if wsum == 0: return 0.0
    score = total/wsum

    anchors = 0
    if have(MS1,MSX,MS2): anchors += 1
    if have(KG_V,KG_Y):   anchors += 1
    if have(O25U,O25A):   anchors += 1
    if any(k in match_odds for k in (
        "Handikaplı Maç Sonucu (-1,0) 1","Handikaplı Maç Sonucu (-1,0) X","Handikaplı Maç Sonucu (-1,0) 2",
        "Handikaplı Maç Sonucu (1,0) 1","Handikaplı Maç Sonucu (1,0) X","Handikaplı Maç Sonucu (1,0) 2")):
        anchors += 1
    if anchors < 2:
        score = min(score, 0.85)

    return round(score*100.0, 2)

# --- Tahmin hesapla (benzer maçlara göre) ---
def calculate_predictions(group_rows, api_row):
    # group_rows: geçmişten benzer maçların satırları (dict)
    preds = []
    match_rows = [r for r in group_rows if r.get("MS SKOR")]
    if not match_rows:
        return preds

    # Skor istatistiği (çoğunluk)
    ms_list = [r["MS SKOR"] for r in match_rows if r.get("MS SKOR")]
    if ms_list:
        c = Counter(ms_list)
        for score, cnt in c.items():
            if cnt / len(match_rows) >= 0.65:
                preds.append(f"Maç Skoru {score}: {cnt/len(match_rows)*100:.1f}%")

    # Diğer pazarlar
    for name, cfg in prediction_criteria.items():
        mtid, sov, oca_key = cfg["mtid"], cfg["sov"], str(cfg["oca_key"])

        # API maçında pazar var mı?
        if mtid not in api_row.get("MTIDs", []):
            continue

        if sov is not None:
            ok = False
            for m in api_row.get("MA", []):
                if m.get("MTID")==mtid:
                    try:
                        if float(m.get("SOV", 0)) == float(sov):
                            ok=True; break
                    except: pass
            if not ok: 
                continue

        # Yüzde hesabı
        cnt = sum(1 for r in match_rows if cfg["func"](r))
        pct = cnt/len(match_rows)*100
        if pct < 80:
            continue

        # Oran bul
        odds = None
        for m in api_row.get("MA", []):
            if m.get("MTID") != mtid: 
                continue
            if sov is not None:
                try:
                    if float(m.get("SOV", 0)) != float(sov):
                        continue
                except: 
                    continue
            for oca in m.get("OCA", []):
                if str(oca.get("N","")) == oca_key:
                    odds = oca.get("O"); break
            if odds: break

        text = f"{name}: {pct:.1f}%"
        if odds is not None:
            try: text += f" (Oran {float(odds):.2f})"
            except: pass
        preds.append(text)

    return preds[:5]

# --- Benzer maçları bul ---
def find_similar_matches(api_df, data):
    out = []
    min_cols = int(len(excel_columns) * 0.15)

    for _, row in api_df.iterrows():
        api_odds = {c: row[c] for c in excel_columns if c in api_df.columns and pd.notna(row.get(c))}
        if len(api_odds) < min_cols:
            continue

        # Lig içi filtresi (hız/kalite)
        league = row["Lig Adı"]
        df_league = data[data["Lig Adı"] == league] if "Lig Adı" in data.columns else data
        if df_league.empty:
            continue

        # Ortak kolonlar
        common = [c for c in excel_columns if c in df_league.columns and c in api_odds]
        if len(common) < min_cols:
            continue

        # BENZERLİK HESABI
        sims = []
        for i, drow in df_league.iterrows():
            match_odds = {c: drow[c] for c in common if pd.notna(drow[c])}
            if len(match_odds) < min_cols:
                continue
            sim = calculate_similarity(api_odds, match_odds)
            if np.isnan(sim) or sim < 70:
                continue
            # tarih sıralama için
            try:
                dtime = pd.to_datetime(str(drow.get("Tarih","01.01.2000"))+" "+str(drow.get("Saat","00:00")),
                                       format="%d.%m.%Y %H:%M", errors="coerce")
            except:
                dtime = pd.NaT
            sims.append({"similarity_percent": sim, "date": dtime, "row": drow})

        sims.sort(key=lambda x: (-(x["similarity_percent"]), x["date"] if pd.notna(x["date"]) else pd.Timestamp.min))
        top_matches = sims[:5]

        # HEADER (bu satır grubu İY/MS mi?)
        header = {
            "Benzerlik (%)": "",
            "Saat": row["Saat"],
            "Tarih": row["Tarih"],
            "Ev Sahibi Takım": row["Ev Sahibi Takım"],
            "Deplasman Takım": row["Deplasman Takım"],
            "Lig Adı": row["Lig Adı"],
            "IY SKOR": "",
            "MS SKOR": "",
            "Tahmin": f"{row['Ev Sahibi Takım']} - {row['Deplasman Takım']}",
            "İY/MS": row.get("İY/MS","Yok"),  # <<< gruplama için geri eklendi
            "MTIDs": row.get("MTIDs", []),
            "MA": row.get("MA", []),
        }

        # Tahminleri, TOP benzer maçlardan üret
        group_rows = []
        for m in top_matches:
            d = m["row"]
            group_rows.append({
                "Benzerlik (%)": f"{m['similarity_percent']:.2f}%",
                "IY SKOR": str(d.get("IY SKOR","")),
                "MS SKOR": str(d.get("MS SKOR","")),
            })
        preds = calculate_predictions(group_rows, header)
        if preds:
            header["Tahmin"] = "\n".join(preds)

        out.append(header)

        # Benzer maçları ekle
        for m in top_matches:
            d = m["row"]
            out.append({
                "Benzerlik (%)": f"{m['similarity_percent']:.2f}%",
                "Saat": "",
                "Tarih": str(d.get("Tarih","")),
                "Ev Sahibi Takım": str(d.get("Ev Sahibi Takım","")),
                "Deplasman Takım": str(d.get("Deplasman Takım","")),
                "Lig Adı": str(d.get("Lig Adı","")),
                "IY SKOR": str(d.get("IY SKOR","")),
                "MS SKOR": str(d.get("MS SKOR","")),
                "Tahmin": "",
            })

        out.append({})  # grup ayırıcı

    return out

# --- Basit (renksiz) DataFrame stili ---
def style_dataframe(df):
    # Sadece sticky header’ı CSS ile verdik; burada ek renklendirme yapmıyoruz.
    return df

# --- UI: Zaman aralığı ---
st.subheader("Analiz için Saat Aralığı")
default_start = datetime.now(IST) + timedelta(minutes=5)
st.write(f"Başlangıç Saati: {default_start.strftime('%d.%m.%Y %H:%M')} (Otomatik, şu an + 5 dakika)")

end_date = st.date_input("Bitiş Tarihi", value=datetime.now(IST).date())
end_time = st.time_input("Bitiş Saati", value=None)

# --- Analiz butonu ---
if st.button("Analize Başla", disabled=st.session_state.analysis_done):
    if end_time is None:
        st.error("Lütfen bitiş saati seçin!")
        st.stop()

    try:
        with st.spinner("Analiz başladı..."):
            # JSON eşleşmeleri
            status_placeholder.write("JSON eşleşmeleri yükleniyor...")
            if not load_json_mappings():
                st.stop()

            # Tarihler
            start_dt = default_start
            end_dt = datetime.combine(end_date, end_time).replace(tzinfo=IST)
            if end_dt <= start_dt:
                st.error("Bitiş saati başlangıç saatinden önce olamaz!")
                st.stop()

            # Excel verisi
            status_placeholder.write("Geçmiş maç verileri indiriliyor...")
            download(f"https://drive.google.com/uc?id={EXCEL_FILE_ID}", "matches.xlsx", quiet=True)
            status_placeholder.write("Excel verisi yükleniyor...")
            data = pd.read_excel("matches.xlsx", sheet_name="Bahisler", dtype=str)

            # Gerekli kolonlar
            required = ["Tarih","Lig Adı","Ev Sahibi Takım","Deplasman Takım","IY SKOR","MS SKOR"]
            miss = [c for c in required if c not in data.columns]
            if miss:
                st.error(f"Excel dosyasında eksik sütunlar var: {', '.join(miss)}")
                st.stop()

            # Oran sütunlarını sayısal yap
            for c in excel_columns:
                if c in data.columns:
                    data[c] = pd.to_numeric(data[c], errors="coerce")
                    data[c] = data[c].where(data[c] > 1.0, np.nan)

            st.session_state.data = data

            # Bülten
            status_placeholder.write("Bülten verisi çekiliyor...")
            match_list, raw = fetch_api_data()
            if not match_list:
                st.error(f"Bülten verisi alınamadı. Hata: {raw.get('error', 'Bilinmeyen hata')}")
                st.stop()

            api_df = process_api_data(match_list, start_dt, end_dt)
            if api_df.empty:
                st.error("Seçilen saat aralığında maç bulunamadı.")
                st.stop()

            # Benzer maçlar
            status_placeholder.write("Maçlar analiz ediliyor...")
            output_rows = find_similar_matches(api_df, data)
            if not output_rows:
                st.error("Eşleşme bulunamadı.")
                st.stop()

            # İY/MS gruplama – MTID=5 olanlar İY/MS Bülteni’ne
            iyms_rows, main_rows = [], []
            current_group, is_iyms = [], False
            for r in output_rows:
                if not r:
                    if current_group:
                        (iyms_rows if is_iyms else main_rows).extend(current_group + [{}])
                    current_group = []
                    continue
                if r.get("Benzerlik (%)","") == "":
                    if current_group:
                        (iyms_rows if is_iyms else main_rows).extend(current_group)
                    current_group = [r]
                    is_iyms = (r.get("İY/MS") == "Var")
                else:
                    current_group.append(r)
            if current_group:
                (iyms_rows if is_iyms else main_rows).extend(current_group)

            cols = ["Benzerlik (%)","Saat","Tarih","Ev Sahibi Takım","Deplasman Takım","Lig Adı","IY SKOR","MS SKOR","Tahmin"]
            iyms_df = pd.DataFrame([r for r in iyms_rows if r], columns=cols)
            main_df = pd.DataFrame([r for r in main_rows if r], columns=cols)

            st.session_state.iyms_df = iyms_df
            st.session_state.main_df = main_df
            st.session_state.output_rows = output_rows
            st.session_state.analysis_done = True

            st.success("Analiz tamamlandı!")

    except Exception as e:
        st.error(f"Hata oluştu: {e}")
        st.stop()

# --- Sonuçlar ---
if st.session_state.analysis_done and st.session_state.iyms_df is not None:
    status_placeholder.empty()
    tab1, tab2 = st.tabs(["İY/MS Bülteni", "Normal Bülten"])
    with tab1:
        st.dataframe(style_dataframe(st.session_state.iyms_df), height=600, use_container_width=True)
    with tab2:
        st.dataframe(style_dataframe(st.session_state.main_df), height=600, use_container_width=True)
