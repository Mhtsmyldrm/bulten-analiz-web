import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from gdown import download
from collections import Counter
import time
from datetime import timezone

# CSS for mobile optimization and styling
st.markdown("""
<style>
h1 { font-weight: bold; color: #05f705; }
.stButton button { background-color: #4CAF50; color: white; border-radius: 5px; }
.stDataFrame { font-size: 12px; width: 100%; overflow-x: auto; }
th { position: sticky; top: 0; background-color: #f0f0f0; z-index: 1; }
</style>
""", unsafe_allow_html=True)

# Title
st.title("Bülten Analiz")

# Session state for caching
if "data" not in st.session_state:
    st.session_state.data = None
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False

# Placeholder for status messages
status_placeholder = st.empty()

# Oran sütunları (Excel'e göre)
excel_columns = [
    "Maç Sonucu 1", "Maç Sonucu X", "Maç Sonucu 2",
    "İlk Yarı/Maç Sonucu 1/1", "İlk Yarı/Maç Sonucu 1/X", "İlk Yarı/Maç Sonucu 1/2",
    "İlk Yarı/Maç Sonucu X/1", "İlk Yarı/Maç Sonucu X/X", "İlk Yarı/Maç Sonucu X/2",
    "İlk Yarı/Maç Sonucu 2/1", "İlk Yarı/Maç Sonucu 2/X", "İlk Yarı/Maç Sonucu 2/2",
    "1. Yarı Sonucu 1", "1. Yarı Sonucu X", "1. Yarı Sonucu 2",
    "2. Yarı Sonucu 1", "2. Yarı Sonucu X", "2. Yarı Sonucu 2",
    "2,5 Alt/Üst Alt", "2,5 Alt/Üst Üst", "3,5 Alt/Üst Alt", "3,5 Alt/Üst Üst",
    "1. Yarı 1,5 Alt/Üst Alt", "1. Yarı 1,5 Alt/Üst Üst",
    "Evsahibi 1,5 Alt/Üst Alt", "Evsahibi 1,5 Alt/Üst Üst",
    "Deplasman 1,5 Alt/Üst Alt", "Deplasman 1,5 Alt/Üst Üst",
    "Karşılıklı Gol Var", "Karşılıklı Gol Yok",
    "Toplam Gol Aralığı 0-1 Gol", "Toplam Gol Aralığı 2-3 Gol", "Toplam Gol Aralığı 4-5 Gol", "Toplam Gol Aralığı 6+ Gol",
    "Maç Skoru 0-0", "Maç Skoru 1-0", "Maç Skoru 2-0", "Maç Skoru 2-1", "Maç Skoru 3-0", "Maç Skoru 3-1",
    "Maç Skoru 3-2", "Maç Skoru 4-0", "Maç Skoru 4-1", "Maç Skoru 4-2", "Maç Skoru 5-0", "Maç Skoru 5-1",
    "Maç Skoru 0-1", "Maç Skoru 1-1", "Maç Skoru 2-2", "Maç Skoru 3-3", "Maç Skoru 0-2", "Maç Skoru 1-2",
    "Maç Skoru 0-3", "Maç Skoru 1-3", "Maç Skoru 2-3", "Maç Skoru 0-4", "Maç Skoru 1-4", "Maç Skoru 2-4",
    "Maç Skoru 0-5", "Maç Skoru 1-5", "Maç Skoru Diğer",
    "1. Yarı 0,5 Alt/Üst Alt", "1. Yarı 0,5 Alt/Üst Üst",
    "Evsahibi 0,5 Alt/Üst Alt", "Evsahibi 0,5 Alt/Üst Üst",
    "Deplasman 0,5 Alt/Üst Alt", "Deplasman 0,5 Alt/Üst Üst",
    "Handikaplı Maç Sonucu (1,0) 1", "Handikaplı Maç Sonucu (1,0) X", "Handikaplı Maç Sonucu (1,0) 2",
    "Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2",
    "Maç Sonucu ve (1,5) Alt/Üst 1 ve Alt", "Maç Sonucu ve (1,5) Alt/Üst X ve Alt", "Maç Sonucu ve (1,5) Alt/Üst 2 ve Alt",
    "Maç Sonucu ve (1,5) Alt/Üst 1 ve Üst", "Maç Sonucu ve (1,5) Alt/Üst X ve Üst", "Maç Sonucu ve (1,5) Alt/Üst 2 ve Üst",
    "Maç Sonucu ve (2,5) Alt/Üst 1 ve Alt", "Maç Sonucu ve (2,5) Alt/Üst X ve Alt", "Maç Sonucu ve (2,5) Alt/Üst 2 ve Alt",
    "Maç Sonucu ve (2,5) Alt/Üst 1 ve Üst", "Maç Sonucu ve (2,5) Alt/Üst X ve Üst", "Maç Sonucu ve (2,5) Alt/Üst 2 ve Üst"
]

# MTID eşleşmeleri
mtid_mapping = {
    (1, None): ["Maç Sonucu 1", "Maç Sonucu X", "Maç Sonucu 2"],
    (5, None): ["İlk Yarı/Maç Sonucu 1/1", "İlk Yarı/Maç Sonucu 1/X", "İlk Yarı/Maç Sonucu 1/2",
                "İlk Yarı/Maç Sonucu X/1", "İlk Yarı/Maç Sonucu X/X", "İlk Yarı/Maç Sonucu X/2",
                "İlk Yarı/Maç Sonucu 2/1", "İlk Yarı/Maç Sonucu 2/X", "İlk Yarı/Maç Sonucu 2/2"],
    (7, None): ["1. Yarı Sonucu 1", "1. Yarı Sonucu X", "1. Yarı Sonucu 2"],
    (9, None): ["2. Yarı Sonucu 1", "2. Yarı Sonucu X", "2. Yarı Sonucu 2"],
    (12, None): ["2,5 Alt/Üst Alt", "2,5 Alt/Üst Üst"],
    (13, None): ["3,5 Alt/Üst Alt", "3,5 Alt/Üst Üst"],
    (14, 1.5): ["1. Yarı 1,5 Alt/Üst Alt", "1. Yarı 1,5 Alt/Üst Üst"],
    (20, 1.5): ["Evsahibi 1,5 Alt/Üst Alt", "Evsahibi 1,5 Alt/Üst Üst"],
    (29, 1.5): ["Deplasman 1,5 Alt/Üst Alt", "Deplasman 1,5 Alt/Üst Üst"],
    (38, None): ["Karşılıklı Gol Var", "Karşılıklı Gol Yok"],
    (43, None): ["Toplam Gol Aralığı 0-1 Gol", "Toplam Gol Aralığı 2-3 Gol", "Toplam Gol Aralığı 4-5 Gol", "Toplam Gol Aralığı 6+ Gol"],
    (205, None): ["Maç Skoru 0-0", "Maç Skoru 1-0", "Maç Skoru 2-0", "Maç Skoru 2-1", "Maç Skoru 3-0", "Maç Skoru 3-1",
                  "Maç Skoru 3-2", "Maç Skoru 4-0", "Maç Skoru 4-1", "Maç Skoru 4-2", "Maç Skoru 5-0", "Maç Skoru 5-1",
                  "Maç Skoru 0-1", "Maç Skoru 1-1", "Maç Skoru 2-2", "Maç Skoru 3-3", "Maç Skoru 0-2", "Maç Skoru 1-2",
                  "Maç Skoru 0-3", "Maç Skoru 1-3", "Maç Skoru 2-3", "Maç Skoru 0-4", "Maç Skoru 1-4", "Maç Skoru 2-4",
                  "Maç Skoru 0-5", "Maç Skoru 1-5", "Maç Skoru Diğer"],
    (209, 0.5): ["1. Yarı 0,5 Alt/Üst Alt", "1. Yarı 0,5 Alt/Üst Üst"],
    (212, None): ["Evsahibi 0,5 Alt/Üst Alt", "Evsahibi 0,5 Alt/Üst Üst"],
    (256, None): ["Deplasman 0,5 Alt/Üst Alt", "Deplasman 0,5 Alt/Üst Üst"],
    (268, 1): ["Handikaplı Maç Sonucu (1,0) 1", "Handikaplı Maç Sonucu (1,0) X", "Handikaplı Maç Sonucu (1,0) 2"],
    (268, -1): ["Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2"],
    (342, None): ["Maç Sonucu ve (1,5) Alt/Üst 1 ve Alt", "Maç Sonucu ve (1,5) Alt/Üst X ve Alt", "Maç Sonucu ve (1,5) Alt/Üst 2 ve Alt",
                  "Maç Sonucu ve (1,5) Alt/Üst 1 ve Üst", "Maç Sonucu ve (1,5) Alt/Üst X ve Üst", "Maç Sonucu ve (1,5) Alt/Üst 2 ve Üst"],
    (343, None): ["Maç Sonucu ve (2,5) Alt/Üst 1 ve Alt", "Maç Sonucu ve (2,5) Alt/Üst X ve Alt", "Maç Sonucu ve (2,5) Alt/Üst 2 ve Alt",
                  "Maç Sonucu ve (2,5) Alt/Üst 1 ve Üst", "Maç Sonucu ve (2,5) Alt/Üst X ve Üst", "Maç Sonucu ve (2,5) Alt/Üst 2 ve Üst"]
}

# Lig kodları eşleştirmesi
league_mapping = {
    15: "ABD", 354: "ÇİNSL", 347: "AL1", 62: "RUS1", 19843: "İKP", 19829: "İKP", 132: "AL2", 161: "AL3",
    47154: "ARJ", 598: "AU2", 1209: "AVU", 1208: "AVUS", 1220: "BEL", 10276: "BR1", 21: "BR2", 1262: "DAN",
    567: "AVUS", 628: "FİN", 381: "FR1", 614: "FR2", 1809: "GKOR2", 636: "GKOR", 681: "HOL2", 322: "HOL",
    24: "İN1", 12: "İN2", 52: "İNCL", 152: "İNLK", 43: "İNP", 129: "İS1", 1951: "İS2", 1975: "İSV", 51: "İSÇ",
    579: "İTA", 1774: "İTB", 10096: "İTC", 642: "JAP", 1873: "NOR", 202: "POL", 1897: "POR2", 566: "POR",
    1980: "T1L", 584: "TSL", 20152: "BEL", 45056: "BEL", 205: "İRL", 349: "İSÇ2", 143: "İTA", 623: "NOR3", 1259: "ÇEK",
    35072: "HİNSL", 1238: "ÇİN2", 1894: "POL2", 1913: "ROM", 45: "AL1", 573: "NOR", 10074: "İS3"
}

# Function to style DataFrame
def style_dataframe(df, output_rows):
    def highlight_rows(row):
        if row["Benzerlik (%)"] == "":
            return ['background-color: #f70511'] * len(row)
        return [''] * len(row)
    
    def highlight_scores(df, output_rows):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        groups = []
        current_group = []
        for row in output_rows:
            if not row:
                if current_group:
                    groups.append(current_group)
                current_group = []
                continue
            current_group.append(row)
        if current_group:
            groups.append(current_group)
        
        for group in groups:
            match_rows = [r for r in group if r.get("Benzerlik (%)", "") != ""]
            if len(match_rows) < 5:
                continue
            iy_scores = Counter([r.get("IY SKOR", "") for r in match_rows if r.get("IY SKOR", "") != ""])
            ms_scores = Counter([r.get("MS SKOR", "") for r in match_rows if r.get("MS SKOR", "") != ""])
            for idx, row in df.iterrows():
                if row["IY SKOR"] in iy_scores and iy_scores[row["IY SKOR"]] >= 5:
                    styles.at[idx, "IY SKOR"] = 'background-color: #0000FF'
                if row["MS SKOR"] in ms_scores and ms_scores[row["MS SKOR"]] >= 5:
                    styles.at[idx, "MS SKOR"] = 'background-color: #0000FF'
        return styles
    
    styled_df = df.style.apply(highlight_rows, axis=1).set_table_styles(
        [{'selector': 'th', 'props': [('position', 'sticky'), ('top', '0'), ('background-color', '#f0f0f0')]}]
    )
    styled_df = styled_df.apply(highlight_scores, output_rows=output_rows, axis=None)
    return styled_df

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
    url = "https://bulten.nesine.com/api/bulten/getprebultendelta?marketVersion=1716908400&eventVersion=1716908400"  # marketVersion kaldırıldı
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
def process_api_data(match_list, raw_data):
    with status_placeholder.container():
        status_placeholder.write("Bültendeki maçlar işleniyor...")
        time.sleep(0.1)
    
    START_DATETIME = datetime.now(timezone.utc)  # API zaten TR saatinde
    END_DATETIME = START_DATETIME + timedelta(hours=24)  # 2 saatlik aralık
    with status_placeholder.container():
        status_placeholder.write(f"Analiz aralığı: {START_DATETIME.strftime('%d.%m.%Y %H:%M')} - {END_DATETIME.strftime('%d.%m.%Y %H:%M')}")
        time.sleep(0.1)
    
    api_matches = []
    tarih_samples = []
    handicap_samples = []
    skipped_matches = []
    
    for match in match_list:
        if not isinstance(match, dict):
            skipped_matches.append({"reason": "Not a dict", "data": str(match)[:50]})
            continue
        
        match_date = match.get("D", "")
        match_time = match.get("T", "")
        if match_date and len(tarih_samples) < 5:
            tarih_samples.append(f"{match_date} {match_time}")
        
        try:
            if not match_date or not match_time:
                raise ValueError("Missing date or time")
            match_datetime = datetime.strptime(f"{match_date} {match_time}", "%d.%m.%Y %H:%M").replace(tzinfo=timezone.utc)
        except ValueError as e:
            skipped_matches.append({"reason": f"Date parse error: {str(e)}", "date": match_date, "time": match_time})
            continue
        
        if not (START_DATETIME <= match_datetime <= END_DATETIME):
            skipped_matches.append({"reason": "Outside time range", "date": match_date, "time": match_time})
            continue
        
        league_code = match.get("LC", None)
        league_name = league_mapping.get(league_code, str(league_code))
        
        match_info = {
            "Saat": match_time,
            "Tarih": match_date,
            "Ev Sahibi Takım": match.get("HN", ""),
            "Deplasman Takım": match.get("AN", ""),
            "Lig Adı": league_name,
            "İY/MS": "Var" if any(m.get("MTID") == 5 for m in match.get("MA", [])) else "Yok",
            "match_datetime": match_datetime
        }
        
        filled_columns = []
        for market in match.get("MA", []):
            mtid = market.get("MTID")
            sov = market.get("SOV")
            key = (mtid, str(sov) if sov is not None else None) if mtid in [14, 20, 29, 155, 209, 268] else (mtid, None)
            if key not in mtid_mapping:
                continue
            column_names = mtid_mapping[key]
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
                if key == (268, '-1') and len(handicap_samples) < 5:
                    handicap_samples.append(f"{matched_column}: {odds}")
        
        match_info["Oran Sayısı"] = f"{len(filled_columns)}/{len(excel_columns)}"
        api_matches.append(match_info)
    
    api_df = pd.DataFrame(api_matches)
    if api_df.empty:
        with status_placeholder.container():
            status_placeholder.write(f"Uyarı: 2 saatlik aralıkta maç bulunamadı. Bülten verisi: {len(match_list)} maç, atlanan: {len(skipped_matches)}")
            status_placeholder.write(f"Atlanma nedenleri: {[{k: v for k, v in s.items() if k != 'data'} for s in skipped_matches[:5]]}")
            status_placeholder.write(f"Raw API: {str(raw_data)[:500]}")
        return api_df  # Boş DataFrame döndür ama hata fırlatma

    # Maçları başlama saatine göre sırala
    api_df = api_df.sort_values(by="match_datetime", ascending=True).reset_index(drop=True)
    api_df = api_df.drop(columns=["match_datetime"])  # Geçici sütunu kaldır
    
    if 'Maç Sonucu 1' not in api_df.columns:
        api_df['Maç Sonucu 1'] = 2.0
    if 'Maç Sonucu X' not in api_df.columns:
        api_df['Maç Sonucu X'] = 3.5
    if 'Maç Sonucu 2' not in api_df.columns:
        api_df['Maç Sonucu 2'] = 3.0
    
    for col in excel_columns:
        if col in api_df.columns:
            api_df[col] = pd.to_numeric(api_df[col], errors='coerce')
            api_df[col] = api_df[col].where((api_df[col] > 1.0) & (api_df[col] < 100.0), np.nan)
    
    with status_placeholder.container():
        status_placeholder.write(f"Bültenden {len(api_df)} maç işlendi.")
        status_placeholder.write(f"Bülten maçlarının Tarih örnekleri: {tarih_samples}")
        status_placeholder.write(f"Handikaplı Maç Sonucu (-1,0) örnekleri: {handicap_samples}")
        time.sleep(0.1)
    return api_df

# Function to find similar matches
def find_similar_matches(api_df, data):
    with status_placeholder.container():
        status_placeholder.write("Maçlar analiz ediliyor...")
        time.sleep(0.1)
    
    output_rows = []
    min_columns = int(len(excel_columns) * 0.3)
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
        
        api_odds_array = np.array([api_odds.get(col, np.nan) for col in common_columns])
        data_odds_array = data_filtered[common_columns].to_numpy()
        diff_sums = np.nansum(np.abs(data_odds_array - api_odds_array) / np.maximum(np.abs(data_odds_array), np.abs(api_odds_array)), axis=1)
        similarity_percents = (1 - diff_sums / len(common_columns)) * 100
        
        similarities = []
        for i, sim_percent in enumerate(similarity_percents):
            if np.isnan(sim_percent):
                continue
            data_row = data_filtered.iloc[i]
            similarities.append({
                "similarity_diff": diff_sums[i],
                "similarity_percent": sim_percent,
                "data_row": data_row
            })
        
        similarities.sort(key=lambda x: x["similarity_diff"])
        top_league_matches = similarities[:5]
        
        match_info = {
            "Benzerlik (%)": "",
            "İY/MS": row["İY/MS"],
            "Oran Sayısı": row["Oran Sayısı"],
            "Saat": row["Saat"],
            "Tarih": row["Tarih"],
            "Ev Sahibi Takım": row["Ev Sahibi Takım"],
            "Deplasman Takım": row["Deplasman Takım"],
            "Lig Adı": row["Lig Adı"]
        }
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
                "İY/MS": "",
                "Oran Sayısı": ""
            }
            for col in data.columns:
                match_info[col] = str(data_row.get(col, ""))  # Ham string olarak
            output_rows.append(match_info)
        
        if include_global_matches:
            data_global = data.copy()
            if len(data_global) > 2000:
                data_global = data_global.sample(n=2000, random_state=0)
            
            common_columns_global = [col for col in api_odds if col in data_global.columns]
            if len(common_columns_global) < min_columns:
                continue
            
            api_odds_array_global = np.array([api_odds.get(col, np.nan) for col in common_columns_global])
            data_odds_array_global = data_global[common_columns_global].to_numpy()
            diff_sums_global = np.nansum(np.abs(data_odds_array_global - api_odds_array_global) / np.maximum(np.abs(data_odds_array_global), np.abs(api_odds_array_global)), axis=1)
            similarity_percents_global = (1 - diff_sums_global / len(common_columns_global)) * 100
            
            similarities_global = []
            for i, sim_percent in enumerate(similarity_percents_global):
                if np.isnan(sim_percent):
                    continue
                data_row = data_global.iloc[i]
                if data_row["Lig Adı"] == api_league:
                    continue
                similarities_global.append({
                    "similarity_diff": diff_sums_global[i],
                    "similarity_percent": sim_percent,
                    "data_row": data_row
                })
            
            similarities_global.sort(key=lambda x: x["similarity_diff"])
            top_global_matches = similarities_global[:5]
            
            for match in top_global_matches:
                data_row = match["data_row"]
                match_info = {
                    "Benzerlik (%)": f"{match['similarity_percent']:.2f}%",
                    "İY/MS": "",
                    "Oran Sayısı": ""
                }
                for col in data.columns:
                    match_info[col] = str(data_row.get(col, ""))  # Ham string olarak
                output_rows.append(match_info)
        
        output_rows.append({})
    
    with status_placeholder.container():
        status_placeholder.write(f"Analiz tamamlandı, {len([r for r in output_rows if r])} satır bulundu.")
        time.sleep(0.1)
    return output_rows

# Analyze button
if st.button("Analize Başla", disabled=st.session_state.analysis_done):
    try:
        with st.spinner("Analiz başladı..."):
            status_placeholder.write("Geçmiş maç verileri indiriliyor...")
            time.sleep(0.1)
            file_id = "11m7tX2xCavCM_cij69UaSVijFuFQbveM"
            download(f"https://drive.google.com/uc?id={file_id}", "matches.xlsx", quiet=False)
            
            status_placeholder.write("Bahisler kontrol ediliyor...")
            time.sleep(0.1)
            excel_columns_basic = ["Tarih", "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY SKOR", "MS SKOR"] + excel_columns
            data = pd.read_excel("matches.xlsx", sheet_name="Bahisler", dtype=str)  # Tüm sütunlar string
            
            # Sütun isimlerini büyük-küçük harf duyarsız kontrol et
            data_columns_lower = [col.lower().strip() for col in data.columns]
            excel_columns_lower = [col.lower().strip() for col in excel_columns_basic]
            available_columns = [data.columns[i] for i, col in enumerate(data_columns_lower) if col in excel_columns_lower]
            missing_columns = [col for col in excel_columns_basic if col.lower().strip() not in data_columns_lower]
            
            status_placeholder.write(f"Bahis isimleri: {', '.join(data.columns)}")
            if missing_columns:
                st.warning(f"Eksik sütunlar: {', '.join(missing_columns)}. Mevcut sütunlarla devam ediliyor.")
            
            status_placeholder.write("Maç verileri yükleniyor...")
            time.sleep(0.1)
            data = pd.read_excel("matches.xlsx", sheet_name="Bahisler", usecols=available_columns, dtype=str)
            
            if "Tarih" not in data.columns:
                st.error("Hata: 'Tarih' sütunu bulunamadı. Lütfen matches.xlsx dosyasını kontrol edin.")
                st.stop()
            
            # Tarih örnekleri
            if "Tarih" in data.columns:
                tarih_samples = data["Tarih"].head(5).tolist()
                status_placeholder.write(f"İlk 5 Tarih örneği: {tarih_samples}")
                time.sleep(0.1)
            
            status_placeholder.write("Tarih string olarak alındı...")
            time.sleep(0.1)
            
            for col in excel_columns:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce')
                    data[col] = data[col].where((data[col] > 1.0) & (data[col] < 100.0), np.nan)
            st.session_state.data = data
            
            status_placeholder.write("Bülten verisi çekiliyor...")
            time.sleep(0.1)
            match_list, raw_data = fetch_api_data()
            if not match_list:
                st.error(f"Bülten verisi alınamadı. Hata: {raw_data.get('error', 'Bilinmeyen hata')}")
                st.stop()
            
            api_df = process_api_data(match_list, raw_data)
            
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
            
            columns = ["Benzerlik (%)", "İY/MS", "Oran Sayısı", "Saat", "Tarih", 
                       "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY SKOR", "MS SKOR"]
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

# Display results if analysis is done
if st.session_state.analysis_done and st.session_state.iyms_df is not None:
    status_placeholder.empty()
    tab1, tab2 = st.tabs(["İY/MS Bülteni", "Normal Bülten"])
    with tab1:
        st.dataframe(style_dataframe(st.session_state.iyms_df, st.session_state.output_rows), height=600)
    with tab2:
        st.dataframe(style_dataframe(st.session_state.main_df, st.session_state.output_rows), height=600)
