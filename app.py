import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from gdown import download
from collections import Counter
import json
import math
from datetime import timezone

# CSS for mobile optimization and styling
st.markdown("""
<style>
h1 { font-weight: bold; color: #05f705; }
.stButton button { background-color: #4CAF50; color: white; border-radius: 5px; }
.stDataFrame { font-size: 12px; width: 100%; overflow-x: auto; }
th { position: sticky; top: 0; background-color: #f0f0f0; z-index: 1; pointer-events: none; }
.stDataFrame th:hover { cursor: default; }
</style>
""", unsafe_allow_html=True)

# Title
st.title("Bülten Analiz")

# Session state for caching
if "data" not in st.session_state:
    st.session_state.data = None
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False
if "iyms_df" not in st.session_state:
    st.session_state.iyms_df = None
if "main_df" not in st.session_state:
    st.session_state.main_df = None
if "output_rows" not in st.session_state:
    st.session_state.output_rows = None

# Placeholder for status messages
status_placeholder = st.empty()

# Oran sütunları
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

# Tahmin kriterleri ve MTID eşleşmeleri
prediction_criteria = {
    "Ev Sahibi 0,5 Gol Üst": {
        "func": lambda row: int(row["MS SKOR"].split("-")[0]) > 0 if row["MS SKOR"] else False,
        "mtid": 212,
        "sov": 0.50,
        "oca_key": "2",
        "column_name": "Evsahibi 0,5 Alt/Üst Üst"
    },
    "Ev Sahibi 1,5 Gol Alt": {
        "func": lambda row: int(row["MS SKOR"].split("-")[0]) < 2 if row["MS SKOR"] else False,
        "mtid": 20,
        "sov": 1.50,
        "oca_key": "1",
        "column_name": "Evsahibi 1,5 Alt/Üst Alt"
    },
    "Ev Sahibi 1,5 Gol Üst": {
        "func": lambda row: int(row["MS SKOR"].split("-")[0]) > 1 if row["MS SKOR"] else False,
        "mtid": 20,
        "sov": 1.50,
        "oca_key": "2",
        "column_name": "Evsahibi 1,5 Alt/Üst Üst"
    },
    "Ev Sahibi 2,5 Gol Alt": {
        "func": lambda row: int(row["MS SKOR"].split("-")[0]) < 3 if row["MS SKOR"] else False,
        "mtid": 326,
        "sov": 2.50,
        "oca_key": "1",
        "column_name": "Evsahibi 2,5 Alt/Üst Alt"
    },
    "Ev Sahibi 2,5 Gol Üst": {
        "func": lambda row: int(row["MS SKOR"].split("-")[0]) > 2 if row["MS SKOR"] else False,
        "mtid": 326,
        "sov": 2.50,
        "oca_key": "2",
        "column_name": "Evsahibi 2,5 Alt/Üst Üst"
    },
    "Deplasman 0,5 Gol Üst": {
        "func": lambda row: int(row["MS SKOR"].split("-")[1]) > 0 if row["MS SKOR"] else False,
        "mtid": 256,
        "sov": 0.50,
        "oca_key": "2",
        "column_name": "Deplasman 0,5 Alt/Üst Üst"
    },
    "Deplasman 1,5 Gol Alt": {
        "func": lambda row: int(row["MS SKOR"].split("-")[1]) < 2 if row["MS SKOR"] else False,
        "mtid": 29,
        "sov": 1.50,
        "oca_key": "1",
        "column_name": "Deplasman 1,5 Alt/Üst Alt"
    },
    "Deplasman 1,5 Gol Üst": {
        "func": lambda row: int(row["MS SKOR"].split("-")[1]) > 1 if row["MS SKOR"] else False,
        "mtid": 29,
        "sov": 1.50,
        "oca_key": "2",
        "column_name": "Deplasman 1,5 Alt/Üst Üst"
    },
    "Deplasman 2,5 Gol Alt": {
        "func": lambda row: int(row["MS SKOR"].split("-")[1]) < 3 if row["MS SKOR"] else False,
        "mtid": 328,
        "sov": 2.50,
        "oca_key": "1",
        "column_name": "Deplasman 2,5 Alt/Üst Alt"
    },
    "Deplasman 2,5 Gol Üst": {
        "func": lambda row: int(row["MS SKOR"].split("-")[1]) > 2 if row["MS SKOR"] else False,
        "mtid": 328,
        "sov": 2.50,
        "oca_key": "2",
        "column_name": "DeKaren, Deplasman 2,5 Alt/Üst Üst"
    }
}

# JSON dosyalarını yükle
def load_json_mappings():
    status_placeholder.write("JSON eşleşmeleri yükleniyor...")
    mtid_file_id = "1N1PjFla683BYTAdzVDaajmcnmMB5wiiO"
    league_file_id = "1L8HA_emD92BJSuCn-P9GJF-hH55nIKE7"
    
    # Download JSON files
    download(f"https://drive.google.com/uc?id={mtid_file_id}", "mtid_mapping.json", quiet=True)
    download(f"https://drive.google.com/uc?id={league_file_id}", "league_mapping.json", quiet=True)
    
    # Load mtid_mapping
    try:
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
        status_placeholder.write(f"Yüklenen MTID eşleşmeleri: {len(mtid_mapping)} adet")
    except Exception as e:
        status_placeholder.error(f"mtid_mapping.json yüklenirken hata: {str(e)}")
        mtid_mapping = {}

    # Load league_mapping
    try:
        with open("league_mapping.json", "r", encoding="utf-8") as f:
            league_data = json.load(f)
            league_mapping = {int(k): v for k, v in league_data.items()}
        status_placeholder.write(f"Yüklenen lig eşleşmeleri: {len(league_mapping)} adet")
    except Exception as e:
        status_placeholder.error(f"league_mapping.json yüklenirken hata: {str(e)}")
        league_mapping = {}

    return mtid_mapping, league_mapping

# API verisi çekme
def fetch_api_data():
    try:
        url = "https://api.iddaa.com.tr/sportsprogram/program?sportId=1&market Ascending"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("data", {}).get("matchList", []), data
    except requests.RequestException as e:
        return [], {"error": str(e)}

# API verisini işleme
def process_api_data(match_list, raw_data, start_datetime, end_datetime):
    rows = []
    league_mapping = load_json_mappings()[1]
    
    for match in match_list:
        match_time_str = match.get("MTS")
        try:
            match_time = datetime.strptime(match_time_str, "%Y-%m-%dT%H:%M:%S%z")
            if not (start_datetime <= match_time <= end_datetime):
                continue
        except (ValueError, TypeError):
            continue
        
        league_id = match.get("LI")
        league_name = league_mapping.get(league_id, str(league_id))
        
        odds_data = {}
        mtids = set()
        for market in match.get("MA", []):
            mtid = market.get("MTID")
            sov = market.get("SOV")
            key = (mtid, sov if sov is not None else None)
            if key in mtid_mapping:
                for outcome in market.get("OCA", []):
                    outcome_name = outcome.get("N")
                    odds = outcome.get("O")
                    for mapping in mtid_mapping[key]:
                        if mapping.endswith(f" {outcome_name}"):
                            odds_data[mapping] = odds
                mtids.add(mtid)
        
        row = {
            "Saat": match_time.strftime("%H:%M"),
            "Tarih": match_time.strftime("%d.%m.%Y"),
            "Ev Sahibi Takım": match.get("HTN", ""),
            "Deplasman Takım": match.get("ATN", ""),
            "Lig Adı": league_name,
            "MTIDs": mtids,
            "MA": match.get("MA", []),
            "İY/MS": "Var" if any(m.get("MTID") == 38 for m in match.get("MA", [])) else "",
        }
        row.update(odds_data)
        rows.append(row)
    
    api_df = pd.DataFrame(rows)
    for col in excel_columns:
        if col in api_df.columns:
            api_df[col] = pd.to_numeric(api_df[col], errors='coerce')
            api_df.loc[:, col] = api_df[col].where(api_df[col] > 1.0, np.nan)
    
    status_placeholder.write(f"Bültenden {len(api_df)} maç işlendi.")
    return api_df

# Benzerlik hesaplama
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
    KG_V, KG_Y = "Karşılıklı Gol Var", "Karşılıklı Gol Yok"
    O25U, O25A = "2,5 Alt/Üst Üst", "2,5 Alt/Üst Alt"

    trio_api = fair_trio(api_odds.get(MS1), api_odds.get(MSX), api_odds.get(MS2))
    trio_mat = fair_trio(match_odds.get(MS1), match_odds.get(MSX), match_odds.get(MS2))
    if trio_api is None or trio_mat is None:
        return 0.0

    ms_sim = hellinger(trio_api, trio_mat)
    if ms_sim < 0.85:
        return round(ms_sim * 100.0, 2)

    per_leg_tol = 0.12
    legs_api = trio_api
    legs_mat = trio_mat
    for i in range(3):
        d = rel_diff(legs_api[i], legs_mat[i])
        if d is None or d > per_leg_tol:
            bad = 0.0 if d is None else max(0.0, 1.0 - d)
            return round(bad * 100.0, 2)

    high_list = []
    high_list.append(("__MS__", ms_sim, 1.0))

    s = bin_sim(KG_V)
    if s is not None:
        high_list.append((KG_V, s, 1.0))
    s = bin_sim(KG_Y)
    if s is not None:
        high_list.append((KG_Y, s, 1.0))

    s = bin_sim(O25U)
    if s is not None:
        high_list.append((O25U, s, 1.0))
    s = bin_sim(O25A)
    if s is not None:
        high_list.append((O25A, s, 1.0))

    for k in ("Çifte Şans 1 veya X", "Çifte Şans 1 veya 2", "Çifte Şans X veya 2"):
        s = bin_sim(k)
        if s is not None:
            high_list.append((k, s, 0.5))

    for k in ("Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2",
              "Handikaplı Maç Sonucu (1,0) 1", "Handikaplı Maç Sonucu (1,0) X", "Handikaplı Maç Sonucu (1,0) 2"):
        s = bin_sim(k)
        if s is not None:
            high_list.append((k, s, 1.0))

    med_list = []
    for k in [
        "1. Yarı Sonucu 1", "1. Yarı Sonucu X", "1. Yarı Sonucu 2",
        "0,5 Alt/Üst Alt", "0,5 Alt/Üst Üst",
        "1,5 Alt/Üst Alt", "1,5 Alt/Üst Üst",
        "3,5 Alt/Üst Alt", "3,5 Alt/Üst Üst",
        "4,5 Alt/Üst Alt", "4,5 Alt/Üst Üst",
        "2. Yarı Sonucu 1", "2. Yarı Sonucu X", "2. Yarı Sonucu 2",
        "Toplam Gol Aralığı 0-1 Gol", "Toplam Gol Aralığı 2-3 Gol",
        "Toplam Gol Aralığı 4-5 Gol", "Toplam Gol Aralığı 6+ Gol",
        "Handikaplı Maç Sonucu (-2,0) 1", "Handikaplı Maç Sonucu (-2,0) X", "Handikaplı Maç Sonucu (-2,0) 2",
        "Handikaplı Maç Sonucu (2,0) 1", "Handikaplı Maç Sonucu (2,0) X", "Handikaplı Maç Sonucu (2,0) 2",
    ]:
        s = bin_sim(k)
        if s is not None:
            med_list.append((k, s, 1.0))

    high_keys = {name for (name, _, _) in high_list}
    low_list = []
    for k in match_odds.keys():
        if k in (MS1, MSX, MS2) or k in high_keys or k in med_list:
            continue
        if ("Korner" in k) or ("Kart" in k):
            continue
        s = bin_sim(k)
        if s is not None:
            low_list.append((k, s, 1.0))

    def weighted_mean(items):
        sw = sum(w for _, _, w in items)
        if sw == 0:
            return None, 0
        val = sum(s * w for _, s, w in items) / sw
        return val, len(items)

    high_sim, high_n = weighted_mean(high_list)
    med_sim, med_n = weighted_mean(med_list)
    low_sim, low_n = weighted_mean(low_list)

    def shrink(val, n, target):
        if val is None or n <= 0:
            return None
        f = math.sqrt(min(n, target) / float(target))
        return val * f

    high_sim = shrink(high_sim, high_n, 6)
    med_sim = shrink(med_sim, med_n, 6)
    low_sim = shrink(low_sim, low_n, 6)

    W_HIGH, W_MED, W_LOW = 0.65, 0.25, 0.10
    total, wsum = 0.0, 0.0
    for sim, w in ((high_sim, W_HIGH), (med_sim, W_MED), (low_sim, W_LOW)):
        if sim is not None:
            total += sim * w
            wsum += w
    if wsum == 0:
        return 0.0
    score = total / wsum

    anchors = 0
    if have(MS1, MSX, MS2):
        anchors += 1
    if have(KG_V, KG_Y):
        anchors += 1
    if have(O25U, O25A):
        anchors += 1
    ah_has = any(k in match_odds for k in (
        "Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2",
        "Handikaplı Maç Sonucu (1,0) 1", "Handikaplı Maç Sonucu (1,0) X", "Handikaplı Maç Sonucu (1,0) 2"))
    if ah_has:
        anchors += 1

    if anchors < 2:
        score = min(score, 0.85)

    return round(score * 100.0, 2)

# Tahmin hesaplama
def calculate_predictions(group_rows, api_row):
    predictions = []
    match_rows = [r for r in group_rows if r and r.get("Benzerlik (%)", "") != "" and r.get("MS SKOR", "") != ""]

    if not match_rows:
        return predictions

    # Skor Tahminleri
    ms_scores = [r.get("MS SKOR", "") for r in match_rows if r.get("MS SKOR", "") != ""]
    if ms_scores:
        ms_score_counts = Counter(ms_scores)
        for score, count in ms_score_counts.items():
            if count / len(match_rows) >= 0.65:
                predictions.append(f"Maç Skoru {score}: {count / len(match_rows) * 100:.1f}%")

    # Diğer Tahminler
    for pred_name, pred_info in prediction_criteria.items():
        required_mtid = pred_info["mtid"]
        required_sov = pred_info["sov"]
        required_oca_key = str(pred_info["oca_key"])

        if required_mtid not in api_row.get("MTIDs", []):
            continue

        sov_found = False
        if required_sov is not None:
            for market in api_row.get("MA", []):
                if market.get("MTID") == required_mtid:
                    try:
                        if float(market.get("SOV", 0)) == float(required_sov):
                            sov_found = True
                            break
                    except (ValueError, TypeError):
                        continue
            if not sov_found:
                continue

        count = sum(1 for row in match_rows if pred_info["func"](row))
        percentage = count / len(match_rows) * 100
        if percentage < 80:
            continue

        odds = None
        for market in api_row.get("MA", []):
            if market.get("MTID") != required_mtid:
                continue
            if required_sov is not None:
                try:
                    if float(market.get("SOV", 0)) != float(required_sov):
                        continue
                except (ValueError, TypeError):
                    continue
            for oca in market.get("OCA", []):
                if str(oca.get("N", "")) == required_oca_key:
                    odds = oca.get("O")
                    break
            if odds:
                break

        display_name = pred_info.get("display_name", pred_name)
        pred_text = f"{display_name}: {percentage:.1f}%"
        if odds is not None:
            try:
                pred_text += f" (Oran {float(odds):.2f})"
            except (ValueError, TypeError):
                pass

        predictions.append(pred_text)

    return predictions[:5]

# Benzer maçları bulma
def find_similar_matches(api_df, data):
    status_placeholder.write("Maçlar analiz ediliyor...")
    output_rows = []
    min_columns = int(len(excel_columns) * 0.15)
    league_keys = set(league_mapping.values())
    
    for idx, row in api_df.iterrows():
        api_odds = {col: row[col] for col in excel_columns if col in row and pd.notna(row[col])}
        if len(api_odds) < min_columns:
            continue
        
        api_league = row["Lig Adı"]
        include_global_matches = api_league in league_keys
        data_filtered = data[data["Lig Adı"] == api_league] if api_league in league_keys else data
        if data_filtered.empty:
            continue
        
        if len(data_filtered) > 2000:
            data_filtered = data_filtered.sample(n=2000, random_state=0)
        
        common_columns = [col for col in api_odds if col in data_filtered.columns]
        if len(common_columns) < min_columns:
            continue
        
        similarities = []
        for i, data_row in data_filtered.iterrows():
            match_odds = {col: data_row[col] for col in excel_columns if col in data_row and pd.notna(data_row[col])}
            similarity = calculate_similarity(api_odds, match_odds)
            if np.isnan(similarity):
                continue
            similarities.append({
                "similarity_percent": similarity,
                "data_row": data_row
            })
        
        similarities.sort(key=lambda x: x["similarity_percent"], reverse=True)
        top_league_matches = similarities[:5]
        
        match_info = {
            "Benzerlik (%)": "",
            "Saat": row["Saat"],
            "Tarih": row["Tarih"],
            "Ev Sahibi Takım": row["Ev Sahibi Takım"],
            "Deplasman Takım": row["Deplasman Takım"],
            "Lig Adı": row["Lig Adı"],
            "IY SKOR": "",
            "MS SKOR": "",
            "Tahmin": f"{row['Ev Sahibi Takım']} - {row['Deplasman Takım']}"
        }
        predictions = calculate_predictions(top_league_matches, row)
        if predictions:
            match_info["Tahmin"] = "\n".join(predictions)
        
        for col in data.columns:
            if col in excel_columns:
                match_info[col] = row.get(col, np.nan)
            elif col not in match_info:
                match_info[col] = ""
        output_rows.append(match_info)
        
        for match in top_league_matches:
            data_row = match["data_row"]
            match_info = {
                "Benzerlik (%)": f"{match['similarity_percent']:.2f}%",
                "Saat": "",
                "Tarih": str(data_row.get("Tarih", "")),
                "Ev Sahibi Takım": str(data_row.get("Ev Sahibi Takım", "")),
                "Deplasman Takım": str(data_row.get("Deplasman Takım", "")),
                "Lig Adı": str(data_row.get("Lig Adı", "")),
                "IY SKOR": str(data_row.get("IY SKOR", "")),
                "MS SKOR": str(data_row.get("MS SKOR", "")),
                "Tahmin": ""
            }
            for col in data.columns:
                if col not in match_info:
                    match_info[col] = str(data_row.get(col, ""))
            output_rows.append(match_info)
        
        if include_global_matches:
            data_global = data.copy()
            if len(data_global) > 2000:
                data_global = data_global.sample(n=2000, random_state=0)
            
            common_columns_global = [col for col in api_odds if col in data_global.columns]
            if len(common_columns_global) < min_columns:
                continue
            
            similarities_global = []
            min_odds_count = len(api_odds) * 0.5 if row["İY/MS"] == "Var" else 0
            for i, data_row in data_global.iterrows():
                match_odds = {col: data_row[col] for col in excel_columns if col in data_row and pd.notna(data_row[col])}
                if data_row["Lig Adı"] == api_league:
                    continue
                match_odds_count = sum(1 for col in excel_columns if col in data_row and pd.notna(data_row[col]))
                if row["İY/MS"] == "Var" and match_odds_count < min_odds_count:
                    continue
                similarity = calculate_similarity(api_odds, match_odds)
                if np.isnan(similarity):
                    continue
                similarities_global.append({
                    "similarity_percent": similarity,
                    "data_row": data_row,
                    "odds_count": match_odds_count
                })
            
            similarities_global.sort(key=lambda x: x["similarity_percent"], reverse=True)
            top_global_matches = similarities_global[:5]
            
            for match in top_global_matches:
                data_row = match["data_row"]
                match_info = {
                    "Benzerlik (%)": f"{match['similarity_percent']:.2f}%",
                    "Saat": "",
                    "Tarih": str(data_row.get("Tarih", "")),
                    "Ev Sahibi Takım": str(data_row.get("Ev Sahibi Takım", "")),
                    "Deplasman Takım": str(data_row.get("Deplasman Takım", "")),
                    "Lig Adı": str(data_row.get("Lig Adı", "")),
                    "IY SKOR": str(data_row.get("IY SKOR", "")),
                    "MS SKOR": str(data_row.get("MS SKOR", "")),
                    "Tahmin": ""
                }
                for col in data.columns:
                    if col not in match_info:
                        match_info[col] = str(data_row.get(col, ""))
                output_rows.append(match_info)
        
        output_rows.append({})
    
    status_placeholder.write(f"Analiz tamamlandı, {len([r for r in output_rows if r])} satır bulundu.")
    return output_rows

# DataFrame stil fonksiyonu
def style_dataframe(df, output_rows):
    def style_row(row):
        if row["Benzerlik (%)"] == "":
            return ['background-color: #b3e5fc' for _ in row]
        elif row["Lig Adı"] == df.iloc[output_rows.index(row) - 1]["Lig Adı"] if output_rows.index(row) > 0 else False:
            return ['background-color: #e6f3fa' for _ in row]
        else:
            return ['background-color: #fff3cd' for _ in row]
    return df.style.apply(style_row, axis=1)

# Zaman aralığı seçimi
st.subheader("Analiz için Saat Aralığı")
default_start = datetime.now(timezone(timedelta(hours=3))) + timedelta(minutes=5)
st.write(f"Başlangıç Saati: {default_start.strftime('%d.%m.%Y %H:%M')} (Otomatik, şu an + 5 dakika)")

end_date = st.date_input("Bitiş Tarihi", value=datetime.now().date())
end_time = st.time_input("Bitiş Saati", value=None)

# JSON eşleşmelerini yükle
mtid_mapping, league_mapping = load_json_mappings()

# Analize başla butonu
if st.button("Analize Başla", disabled=st.session_state.analysis_done):
    if end_time is None:
        st.error("Lütfen bitiş saati seçin!")
        st.stop()
    
    try:
        with st.spinner("Analiz başladı..."):
            end_datetime = datetime.combine(end_date, end_time).replace(tzinfo=timezone(timedelta(hours=3)))
            start_datetime = default_start
            
            if end_datetime <= start_datetime:
                st.error("Bitiş saati başlangıç saatinden önce olamaz!")
                st.stop()
            
            status_placeholder.write("Geçmiş maç verileri indiriliyor...")
            file_id = "11m7tX2xCavCM_cij69UaSVijFuFQbveM"
            download(f"https://drive.google.com/uc?id={file_id}", "matches.xlsx", quiet=False)
            
            status_placeholder.write("Bahisler kontrol ediliyor...")
            excel_columns_basic = [
                "Tarih", "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY SKOR", "MS SKOR"
            ] + excel_columns
            data = pd.read_excel("matches.xlsx", sheet_name="Bahisler", dtype=str)
            
            data_columns_lower = [col.lower().strip() for col in data.columns]
            excel_columns_lower = [col.lower().strip() for col in excel_columns_basic]
            available_columns = [data.columns[i] for i, col in enumerate(data_columns_lower) if col in excel_columns_lower]
            missing_columns = [col for col in excel_columns_basic if col.lower().strip() not in data_columns_lower]
            
            status_placeholder.write(f"Bahis isimleri: {', '.join(data.columns)}")
            if missing_columns:
                st.warning(f"Eksik sütunlar: {', '.join(missing_columns)}. Mevcut sütunlarla devam ediliyor.")
            
            status_placeholder.write("Maç verileri yükleniyor...")
            data = pd.read_excel("matches.xlsx", sheet_name="Bahisler", usecols=available_columns, dtype=str)
            
            if "Tarih" not in data.columns:
                st.error("Hata: 'Tarih' sütunu bulunamadı. Lütfen matches.xlsx dosyasını kontrol edin.")
                st.stop()
            
            if "Tarih" in data.columns:
                tarih_samples = data["Tarih"].head(5).tolist()
                status_placeholder.write(f"İlk 5 Tarih örneği: {tarih_samples}")
            
            status_placeholder.write("Tarih string olarak alındı...")
            
            for col in excel_columns:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce')
                    data.loc[:, col] = data[col].where(data[col] > 1.0, np.nan)
            st.session_state.data = data
            
            status_placeholder.write("Bülten verisi çekiliyor...")
            match_list, raw_data = fetch_api_data()
            if not match_list:
                st.error(f"Bülten verisi alınamadı. Hata: {raw_data.get('error', 'Bilinmeyen hata')}")
                st.stop()
            
            api_df = process_api_data(match_list, raw_data, start_datetime, end_datetime)
            
            st.write(f"Bültenden çekilen maç sayısı: {len(match_list)}")
            st.write(f"İşlenen maçlar: {len(api_df)}")
            if not api_df.empty:
                output_rows = find_similar_matches(api_df, data)
            if not output_rows:
                st.error("Eşleşme bulunamadı. Lütfen verileri kontrol edin.")
                st.stop()
            
            iyms_rows = []
            main_rows = []
            current_group = []
            is_iyms = False
            for row in output_rows:
                if not row:
                    if current_group:
                        if is_iyms:
                            iyms_rows.extend(current_group)
                            iyms_rows.append({})
                        else:
                            main_rows.extend(current_group)
                            main_rows.append({})
                    current_group = []
                    continue
                if row.get("Benzerlik (%)") == "":
                    if current_group:
                        if is_iyms:
                            iyms_rows.extend(current_group)
                        else:
                            main_rows.extend(current_group)
                    current_group = [row]
                    is_iyms = row.get("İY/MS") == "Var"
                else:
                    current_group.append(row)
            if current_group:
                if is_iyms:
                    iyms_rows.extend(current_group)
                else:
                    main_rows.extend(current_group)
            
            columns = ["Benzerlik (%)", "Saat", "Tarih", "Ev Sahibi Takım", "Deplasman Takım", "Lig Adı", "IY SKOR", "MS SKOR", "Tahmin"]
            iyms_df = pd.DataFrame([r for r in iyms_rows if r], columns=columns)
            main_df = pd.DataFrame([r for r in main_rows if r], columns=columns)
            
            st.session_state.iyms_df = iyms_df
            st.session_state.main_df = main_df
            st.session_state.output_rows = output_rows
            st.session_state.analysis_done = True
            
            st.success("Analiz tamamlandı!")
    
    except Exception as e:
        st.error(f"Hata oluştu: {str(e)}")
        st.stop()

# Sonuçları göster
if st.session_state.analysis_done and st.session_state.iyms_df is not None:
    status_placeholder.empty()
    tab1, tab2 = st.tabs(["İY/MS Bülteni", "Normal Bülten"])
    with tab1:
        st.dataframe(
            style_dataframe(st.session_state.iyms_df, st.session_state.output_rows),
            height=600,
            use_container_width=True,
        )
    with tab2:
        st.dataframe(
            style_dataframe(st.session_state.main_df, st.session_state.output_rows),
            height=600,
            use_container_width=True,
        )
