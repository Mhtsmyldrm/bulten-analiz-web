import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from gdown import download
import time
from datetime import timezone
import difflib
import json
import math
from collections import Counter

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
if "mtid_mapping" not in st.session_state:
    st.session_state.mtid_mapping = {}
if "league_mapping" not in st.session_state:
    st.session_state.league_mapping = {}
if "iyms_df" not in st.session_state:
    st.session_state.iyms_df = None
if "main_df" not in st.session_state:
    st.session_state.main_df = None
if "output_rows" not in st.session_state:
    st.session_state.output_rows = None

# Placeholder for status messages
status_placeholder = st.empty()

# JSON dosya ID'leri
LEAGUE_MAPPING_ID = "1L8HA_emD92BJSuCn-P9GJF-hH55nIKE7"
MTID_MAPPING_ID = "1N1PjFla683BYTAdzVDaajmcnmMB5wiiO"
EXCEL_FILE_ID = "11m7tX2xCavCM_cij69UaSVijFuFQbveM"

# JSON mappingleri yükleme fonksiyonu
def load_json_mappings():
    try:
        # League mapping yükle
        download(f"https://drive.google.com/uc?id={LEAGUE_MAPPING_ID}", "league_mapping.json", quiet=True)
        with open("league_mapping.json", "r", encoding="utf-8") as f:
            league_data = json.load(f)
            league_mapping = {int(k): v for k, v in league_data.items()}
        
        # MTID mapping yükle
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
        
        st.session_state.mtid_mapping = mtid_mapping
        st.session_state.league_mapping = league_mapping
        return True
    except Exception as e:
        st.error(f"JSON mapping yüklenirken hata: {str(e)}")
        return False

# Benzerlik hesaplama fonksiyonu
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

    # Pazar isimleri
    MS1, MSX, MS2 = "Maç Sonucu 1", "Maç Sonucu X", "Maç Sonucu 2"
    KG_V, KG_Y = "Karşılıklı Gol Var", "Karşılıklı Gol Yok"
    O25U, O25A = "2,5 Alt/Üst Üst", "2,5 Alt/Üst Alt"

    # 1) KAPI KONTROLÜ
    trio_api = fair_trio(api_odds.get(MS1), api_odds.get(MSX), api_odds.get(MS2))
    trio_mat = fair_trio(match_odds.get(MS1), match_odds.get(MSX), match_odds.get(MS2))
    if trio_api is None or trio_mat is None:
        return 0.0

    ms_sim = hellinger(trio_api, trio_mat)
    if ms_sim < 0.85:
        return round(ms_sim * 100.0, 2)

    # Her bacakta göreli fark ≤ %12
    per_leg_tol = 0.12
    legs_api = trio_api
    legs_mat = trio_mat
    for i in range(3):
        d = rel_diff(legs_api[i], legs_mat[i])
        if d is None or d > per_leg_tol:
            bad = 0.0 if d is None else max(0.0, 1.0 - d)
            return round(100.0 * min(bad, ms_sim), 2)

    # 2) GRUP BENZERLİKLERİ
    high_list = []
    high_list.append(("__MS__", ms_sim, 1.0))

    # KG
    s = bin_sim(KG_V)
    if s is not None:
        high_list.append((KG_V, s, 1.0))
    s = bin_sim(KG_Y)
    if s is not None:
        high_list.append((KG_Y, s, 1.0))

    # O/U 2.5
    s = bin_sim(O25U)
    if s is not None:
        high_list.append((O25U, s, 1.0))
    s = bin_sim(O25A)
    if s is not None:
        high_list.append((O25A, s, 1.0))

    # Çifte şans
    for k in ("Çifte Şans 1 veya X", "Çifte Şans 1 veya 2", "Çifte Şans X veya 2"):
        s = bin_sim(k)
        if s is not None:
            high_list.append((k, s, 0.5))

    # Handikap
    for k in ("Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2",
              "Handikaplı Maç Sonucu (1,0) 1", "Handikaplı Maç Sonucu (1,0) X", "Handikaplı Maç Sonucu (1,0) 2"):
        s = bin_sim(k)
        if s is not None:
            high_list.append((k, s, 1.0))

    # Med pazarlar
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

    med_list = []
    for k in MED_KEYS:
        s = bin_sim(k)
        if s is not None:
            w = 0.5 if "Alt/Üst" in k else 1.0
            med_list.append((k, s, w))

    # Low pazarlar
    low_list = []
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
        if sw == 0:
            return None, 0
        val = sum(s * w for _, s, w in items) / sw
        return val, len(items)

    high_sim, high_n = weighted_mean(high_list)
    med_sim, med_n = weighted_mean(med_list)
    low_sim, low_n = weighted_mean(low_list)

    # 3) GRUP BAZINDA KAPSAM KÜÇÜLTME
    def shrink(val, n, target):
        if val is None or n <= 0:
            return None
        f = math.sqrt(min(n, target) / float(target))
        return val * f

    high_sim = shrink(high_sim, high_n, 6)
    med_sim = shrink(med_sim, med_n, 6)
    low_sim = shrink(low_sim, low_n, 6)

    # 4) AĞIRLIKLI BİRLEŞTİRME
    W_HIGH, W_MED, W_LOW = 0.65, 0.25, 0.10
    total, wsum = 0.0, 0.0
    for sim, w in ((high_sim, W_HIGH), (med_sim, W_MED), (low_sim, W_LOW)):
        if sim is not None:
            total += sim * w
            wsum += w
    if wsum == 0:
        return 0.0
    score = total / wsum

    # 5) YÜKSEK GRUP "ANKOR" KONTROLÜ
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

# Tahmin kriterleri
prediction_criteria = {
    "Maç Sonucu 1": {
        "func": lambda row: int(row["MS SKOR"].split("-")[0]) > int(row["MS SKOR"].split("-")[1]) if row["MS SKOR"] and "-" in row["MS SKOR"] else False,
        "mtid": 1,
        "sov": None,
        "oca_key": "1",
        "column_name": "Maç Sonucu 1"
    },
    "Maç Sonucu X": {
        "func": lambda row: int(row["MS SKOR"].split("-")[0]) == int(row["MS SKOR"].split("-")[1]) if row["MS SKOR"] and "-" in row["MS SKOR"] else False,
        "mtid": 1,
        "sov": None,
        "oca_key": "2",
        "column_name": "Maç Sonucu X"
    },
    "Maç Sonucu 2": {
        "func": lambda row: int(row["MS SKOR"].split("-")[0]) < int(row["MS SKOR"].split("-")[1]) if row["MS SKOR"] and "-" in row["MS SKOR"] else False,
        "mtid": 1,
        "sov": None,
        "oca_key": "3",
        "column_name": "Maç Sonucu 2"
    },
    "İlk Yarı Karşılıklı Gol Var": {
        "func": lambda row: int(row["IY SKOR"].split("-")[0]) > 0 and int(row["IY SKOR"].split("-")[1]) > 0 if row["IY SKOR"] and "-" in row["IY SKOR"] else False,
        "mtid": 452,
        "sov": None,
        "oca_key": "1",
        "column_name": "Karşılıklı Gol Var"
    },
    "İlk Yarı 0,5 Gol Üst": {
        "func": lambda row: sum(map(int, row["IY SKOR"].split("-"))) > 0 if row["IY SKOR"] and "-" in row["IY SKOR"] else False,
        "mtid": 209,
        "sov": 0.50,
        "oca_key": "2",
        "column_name": "1. Yarı 0,5 Alt/Üst Üst"
    },
    "İlk Yarı 1,5 Gol Üst": {
        "func": lambda row: sum(map(int, row["IY SKOR"].split("-"))) > 1 if row["IY SKOR"] and "-" in row["IY SKOR"] else False,
        "mtid": 14,
        "sov": 1.50,
        "oca_key": "2",
        "column_name": "1. Yarı 1,5 Alt/Üst Üst"
    },
    "Toplam Gol 2,5 Gol Üst": {
        "func": lambda row: sum(map(int, row["MS SKOR"].split("-"))) > 2 if row["MS SKOR"] and "-" in row["MS SKOR"] else False,
        "mtid": 12,
        "sov": 2.50,
        "oca_key": "2",
        "column_name": "2,5 Alt/Üst Üst"
    },
    "Toplam Gol 2,5 Gol Alt": {
        "func": lambda row: sum(map(int, row["MS SKOR"].split("-"))) < 3 if row["MS SKOR"] and "-" in row["MS SKOR"] else False,
        "mtid": 12,
        "sov": 2.50,
        "oca_key": "1",
        "column_name": "2,5 Alt/Üst Alt"
    },
    "1. Yarı Sonucu 1": {
        "func": lambda row: int(row["IY SKOR"].split("-")[0]) > int(row["IY SKOR"].split("-")[1]) if row["IY SKOR"] and "-" in row["IY SKOR"] else False,
        "mtid": 7,
        "sov": None,
        "oca_key": "1",
        "column_name": "1. Yarı Sonucu 1"
    },
    "1. Yarı Sonucu X": {
        "func": lambda row: int(row["IY SKOR"].split("-")[0]) == int(row["IY SKOR"].split("-")[1]) if row["IY SKOR"] and "-" in row["IY SKOR"] else False,
        "mtid": 7,
        "sov": None,
        "oca_key": "2",
        "column_name": "1. Yarı Sonucu X"
    },
    "1. Yarı Sonucu 2": {
        "func": lambda row: int(row["IY SKOR"].split("-")[0]) < int(row["IY SKOR"].split("-")[1]) if row["IY SKOR"] and "-" in row["IY SKOR"] else False,
        "mtid": 7,
        "sov": None,
        "oca_key": "3",
        "column_name": "1. Yarı Sonucu 2"
    }
}

# Function to calculate predictions
def calculate_predictions(group_rows, api_row):
    predictions = []
    match_rows = [r for r in group_rows if r and r.get("Benzerlik (%)", "") != "" and r.get("MS SKOR", "") != ""]

    if not match_rows:
        return predictions

    # Skor Tahminleri
    ms_scores = [r.get("MS SKOR", "") for r in match_rows if r.get("MS SKOR", "")]
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

        # MTID kontrolü
        if "MTIDs" not in api_row or required_mtid not in api_row["MTIDs"]:
            continue

        # SOV kontrolü
        if required_sov is not None and "MA" in api_row:
            sov_found = False
            for market in api_row["MA"]:
                if market.get("MTID") == required_mtid:
                    try:
                        if float(market.get("SOV", 0)) == float(required_sov):
                            sov_found = True
                            break
                    except (ValueError, TypeError):
                        continue
            if not sov_found:
                continue

        # Tahmin yüzdesini hesapla
        count = sum(1 for row in match_rows if pred_info["func"](row))
        percentage = count / len(match_rows) * 100
        if percentage < 80:
            continue

        # Oranı bul
        odds = None
        if "MA" in api_row:
            for market in api_row["MA"]:
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

        # Tahmini formatla
        pred_text = f"{pred_name}: {percentage:.1f}%"
        if odds is not None:
            try:
                pred_text += f" (Oran {float(odds):.2f})"
            except (ValueError, TypeError):
                pass

        predictions.append(pred_text)

    return predictions[:5]

# Function to fetch API data from Nesine
def fetch_api_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nesine.com/",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Connection": "keep-alive",
        "X-Requested-With": "XMLHttpRequest",
    }
    url = "https://bulten.nesine.com/api/bulten/getprebultendelta?marketVersion=1716908400&eventVersion=1716908400"
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        match_data = response.json()
        
        if isinstance(match_data, dict) and "sg" in match_data and "EA" in match_data["sg"]:
            return match_data["sg"]["EA"], match_data
        else:
            return [], {"error": "No EA data"}
    except Exception as e:
        return [], {"error": str(e)}

# Function to process API data into DataFrame
def process_api_data(match_list, raw_data, start_datetime, end_datetime):
    with status_placeholder.container():
        status_placeholder.write("Bültendeki maçlar işleniyor...")
        time.sleep(0.1)

    api_matches = []
    skipped_matches = []
    
    for match in match_list:
        if not isinstance(match, dict):
            skipped_matches.append({"reason": "Not a dict", "data": str(match)[:50]})
            continue
        
        match_date = match.get("D", "")
        match_time = match.get("T", "")
        
        try:
            if not match_date or not match_time:
                raise ValueError("Missing date or time")
            match_datetime = datetime.strptime(f"{match_date} {match_time}", "%d.%m.%Y %H:%M").replace(tzinfo=timezone(timedelta(hours=3)))
        except ValueError as e:
            skipped_matches.append({"reason": f"Date parse error: {str(e)}", "date": match_date, "time": match_time})
            continue
        
        if not (start_datetime <= match_datetime <= end_datetime):
            skipped_matches.append({"reason": "Outside time range", "date": match_date, "time": match_time})
            continue
        
        league_code = match.get("LC", None)
        league_name = st.session_state.league_mapping.get(league_code, str(league_code))

        match_info = {
            "Saat": match_time,
            "Tarih": match_date,
            "Ev Sahibi Takım": match.get("HN", ""),
            "Deplasman Takım": match.get("AN", ""),
            "Lig Adı": league_name,
            "İY/MS": "Var" if any(m.get("MTID") == 5 for m in match.get("MA", [])) else "Yok",
            "match_datetime": match_datetime,
            "MTIDs": [m.get("MTID") for m in match.get("MA", [])],
            "MA": match.get("MA", [])
        }
        
        filled_columns = []
        for market in match.get("MA", []):
            mtid = market.get("MTID")
            sov = market.get("SOV")
            key = (mtid, float(sov) if sov is not None else None) if mtid in [14, 15, 20, 29, 155, 268, 272, 349, 352] else (mtid, None)
            if key not in st.session_state.mtid_mapping:
                continue
            column_names = st.session_state.mtid_mapping[key]
            oca_list = market.get("OCA", [])
            
            for idx, outcome in enumerate(oca_list):
                odds = outcome.get("O")
                if odds is None or not isinstance(odds, (int, float)):
                    continue
                if idx >= len(column_names):
                    continue
                matched_column = column_names[idx]
                match_info[matched_column] = float(odds)
                filled_columns.append(matched_column)
        
        match_info["Oran Sayısı"] = f"{len(filled_columns)}"
        api_matches.append(match_info)
    
    api_df = pd.DataFrame(api_matches)
    if api_df.empty:
        with status_placeholder.container():
            status_placeholder.write(f"Uyarı: Seçilen saat aralığında maç bulunamadı.")
        return api_df

    api_df = api_df.sort_values(by="match_datetime", ascending=True).reset_index(drop=True)
    api_df = api_df.drop(columns=["match_datetime"])
    
    with status_placeholder.container():
        status_placeholder.write(f"Bültenden {len(api_df)} maç işlendi.")
        time.sleep(0.1)
    return api_df

# Function to find similar matches
def find_similar_matches(api_df, data):
    with status_placeholder.container():
        status_placeholder.write("Maçlar analiz ediliyor...")
        time.sleep(0.1)
    
    output_rows = []
    min_columns = 5
    league_keys = set(st.session_state.league_mapping.values())
    
    for idx, row in api_df.iterrows():
        api_odds = {col: row[col] for col in data.columns if col in row and pd.notna(row[col]) and col not in ["Saat", "Tarih", "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY SKOR", "MS SKOR"]}
        if len(api_odds) < min_columns:
            continue
        
        api_league = row["Lig Adı"]
        data_filtered = data[data["Lig Adı"] == api_league] if api_league in league_keys else data
        if data_filtered.empty:
            continue
        
        common_columns = [col for col in api_odds if col in data_filtered.columns]
        if len(common_columns) < min_columns:
            continue
        
        match_info = {
            "Benzerlik (%)": "",
            "Saat": row["Saat"],
            "Tarih": row["Tarih"],
            "Ev Sahibi Takım": row["Ev Sahibi Takım"],
            "Deplasman Takım": row["Deplasman Takım"],
            "Lig Adı": row["Lig Adı"],
            "IY SKOR": "",
            "MS SKOR": "",
            "Tahmin": f"{row['Ev Sahibi Takım']} - {row['Deplasman Takım']}",
            "MTIDs": row["MTIDs"],
            "MA": row.get("MA", [])
        }
        predictions = calculate_predictions([], row)
        if predictions:
            match_info["Tahmin"] = "\n".join(predictions)
        output_rows.append(match_info)
        
        similarities = []
        for i, data_row in data_filtered.iterrows():
            data_odds = {col: data_row[col] for col in common_columns if pd.notna(data_row[col])}
            
            if len(data_odds) < min_columns:
                continue
                
            similarity_percent = calculate_similarity(api_odds, data_odds)
            
            if similarity_percent < 70:
                continue
                
            try:
                match_date = pd.to_datetime(data_row.get("Tarih", "01.01.2000") + ' ' + data_row.get("Saat", "00:00"), format='%d.%m.%Y %H:%M')
            except:
                match_date = pd.to_datetime("01.01.2000 00:00")
                
            similarities.append({
                "similarity_percent": similarity_percent,
                "match_date": match_date,
                "data_row": data_row
            })
        
        # Benzerlik sıralaması
        similarities.sort(key=lambda x: (-x["similarity_percent"], -x["match_date"].timestamp()))
        top_matches = similarities[:5]
        
        for match in top_matches:
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
            output_rows.append(match_info)
        
        # Global maçlar
        if api_league in league_keys:
            data_global = data[data["Lig Adı"] != api_league]
            similarities_global = []
            
            for i, data_row in data_global.iterrows():
                data_odds = {col: data_row[col] for col in common_columns if pd.notna(data_row[col])}
                
                if len(data_odds) < min_columns:
                    continue
                    
                similarity_percent = calculate_similarity(api_odds, data_odds)
                
                if similarity_percent < 70:
                    continue
                    
                try:
                    match_date = pd.to_datetime(data_row.get("Tarih", "01.01.2000") + ' ' + data_row.get("Saat", "00:00"), format='%d.%m.%Y %H:%M')
                except:
                    match_date = pd.to_datetime("01.01.2000 00:00")
                    
                similarities_global.append({
                    "similarity_percent": similarity_percent,
                    "match_date": match_date,
                    "data_row": data_row
                })
            
            similarities_global.sort(key=lambda x: (-x["similarity_percent"], -x["match_date"].timestamp()))
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
                output_rows.append(match_info)
        
        output_rows.append({})
    
    with status_placeholder.container():
        status_placeholder.write(f"Analiz tamamlandı, {len([r for r in output_rows if r])} satır bulundu.")
        time.sleep(0.1)
    return output_rows

# Function to style DataFrame
def style_dataframe(df):
    def highlight_rows(row):
        if row["Benzerlik (%)"] == "":
            return ['background-color: #f70511'] * len(row)
        return [''] * len(row)
    
    def highlight_scores(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        
        iy_scores = Counter(df[df["IY SKOR"] != ""]["IY SKOR"])
        ms_scores = Counter(df[df["MS SKOR"] != ""]["MS SKOR"])
        
        for idx, row in df.iterrows():
            if row["IY SKOR"] in iy_scores and iy_scores[row["IY SKOR"]] >= 5:
                styles.at[idx, "IY SKOR"] = 'background-color: #0000FF'
            if row["MS SKOR"] in ms_scores and ms_scores[row["MS SKOR"]] >= 5:
                styles.at[idx, "MS SKOR"] = 'background-color: #0000FF'
        
        return styles
    
    styled_df = df.style.apply(highlight_rows, axis=1)
    styled_df = styled_df.apply(highlight_scores, axis=None)
    return styled_df

# Zaman aralığı seçimi
st.subheader("Analiz için Saat Aralığı")
default_start = datetime.now(timezone(timedelta(hours=3))) + timedelta(minutes=5)
st.write(f"Başlangıç Saati: {default_start.strftime('%d.%m.%Y %H:%M')} (Otomatik, şu an + 5 dakika)")

end_date = st.date_input("Bitiş Tarihi", value=datetime.now().date())
end_time = st.time_input("Bitiş Saati", value=None)

# Analize başla butonu
if st.button("Analize Başla", disabled=st.session_state.analysis_done):
    if end_time is None:
        st.error("Lütfen bitiş saati seçin!")
        st.stop()
    
    try:
        with st.spinner("Analiz başladı..."):
            # JSON mappingleri yükle
            if not load_json_mappings():
                st.error("JSON mappingler yüklenemedi!")
                st.stop()
            
            # Bitiş zamanını oluştur
            end_datetime = datetime.combine(end_date, end_time).replace(tzinfo=timezone(timedelta(hours=3)))
            start_datetime = default_start
            
            if end_datetime <= start_datetime:
                st.error("Bitiş saati başlangıç saatinden önce olamaz!")
                st.stop()
            
            status_placeholder.write("Geçmiş maç verileri indiriliyor...")
            time.sleep(0.1)
            download(f"https://drive.google.com/uc?id={EXCEL_FILE_ID}", "matches.xlsx", quiet=False)
            
            status_placeholder.write("Excel verisi yükleniyor...")
            time.sleep(0.1)
            data = pd.read_excel("matches.xlsx", sheet_name="Bahisler", dtype=str)
            
            # Gerekli sütunları kontrol et
            required_columns = ["Tarih", "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY SKOR", "MS SKOR"]
            missing_columns = [col for col in required_columns if col not in data.columns]
            if missing_columns:
                st.error(f"Excel dosyasında eksik sütunlar: {', '.join(missing_columns)}")
                st.stop()
            
            # Oran sütunlarını temizle
            odds_columns = [pred["column_name"] for pred in prediction_criteria.values()]
            for col in odds_columns:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce')
                    data.loc[:, col] = data[col].where(data[col] > 1.0, np.nan)
            
            st.session_state.data = data
            
            status_placeholder.write("Bülten verisi çekiliyor...")
            time.sleep(0.1)
            match_list, raw_data = fetch_api_data()
            if not match_list:
                st.error(f"Bülten verisi alınamadı. Hata: {raw_data.get('error', 'Bilinmeyen hata')}")
                st.stop()
            
            api_df = process_api_data(match_list, raw_data, start_datetime, end_datetime)
            if api_df.empty:
                st.error("Seçilen saat aralığında maç bulunamadı.")
                st.stop()
            
            st.write(f"Bültenden çekilen maç sayısı: {len(match_list)}")
            st.write(f"İşlenen maçlar: {len(api_df)}")
            
            output_rows = find_similar_matches(api_df, data)
            if not output_rows:
                st.error("Eşleşme bulunamadı. Lütfen verileri kontrol edin.")
                st.stop()
            
            # İY/MS ve normal bültenleri ayır
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
            style_dataframe(st.session_state.iyms_df),
            height=600,
            use_container_width=True,
        )
    with tab2:
        st.dataframe(
            style_dataframe(st.session_state.main_df),
            height=600,
            use_container_width=True,
        )
