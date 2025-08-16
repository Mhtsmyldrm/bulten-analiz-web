import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from gdown import download
from collections import Counter
import time
from datetime import timezone
import difflib
import json

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

# Placeholder for status messages
status_placeholder = st.empty()

# Sadeleştirilmiş oran sütunları
excel_columns = [
    "Maç Sonucu 1", "Maç Sonucu X", "Maç Sonucu 2",
    "Çifte Şans 1 veya X", "Çifte Şans 1 veya 2", "Çifte Şans X veya 2",
    "2,5 Alt/Üst Alt", "2,5 Alt/Üst Üst",
    "3,5 Alt/Üst Alt", "3,5 Alt/Üst Üst",
    "Karşılıklı Gol Var", "Karşılıklı Gol Yok",
    "İlk Yarı/Maç Sonucu 1/1", "İlk Yarı/Maç Sonucu X/X", "İlk Yarı/Maç Sonucu 2/2",
    "1. Yarı Sonucu 1", "1. Yarı Sonucu X", "1. Yarı Sonucu 2",
    "2. Yarı Sonucu 1", "2. Yarı Sonucu X", "2. Yarı Sonucu 2",
]

# API'den veri çekme
def fetch_api_data():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.nesine.com/",
            "Accept-Language": "tr-TR,tr;q=0.9",
            "Connection": "keep-alive",
            "X-Requested-With": "XMLHttpRequest",
        }
        url = "https://bulten.nesine.com/api/bulten/getprebultendelta?eventVersion=462376563&marketVersion=462376563&oddVersion=1712799325&_=1743545516827"
        response = requests.get(url, timeout=30, headers=headers)
        response.raise_for_status()
        match_data = response.json()
        if isinstance(match_data, dict) and "sg" in match_data and "EA" in match_data["sg"]:
            return match_data["sg"]["EA"], match_data
        else:
            return [], {"error": "API yanıtında maç verisi bulunamadı"}
    except Exception as e:
        st.error(f"API hatası: {str(e)}")
        return [], {"error": str(e)}

# API verisini DataFrame'e çevirme
def process_api_data(match_list, start_datetime, end_datetime, mtid_mapping, league_mapping):
    api_matches = []
    filtered_count = 0
    total_matches = 0
    
    st.write(f"Toplam API maçı: {len(match_list)}")
    for match in match_list:
        if not isinstance(match, dict):
            st.write(f"Geçersiz maç verisi: {type(match)}")
            continue
        
        total_matches += 1
        markets = match.get("MA", [])
        mbs = next((m.get("MBS", 0) for m in markets if m.get("MTID") == 1), 0)
        
        if mbs not in [1, 2]:
            filtered_count += 1
            continue
        
        match_date = match.get("D", "")
        match_time = match.get("T", "")
        try:
            match_datetime = datetime.strptime(f"{match_date} {match_time}", "%d.%m.%Y %H:%M").replace(tzinfo=timezone(timedelta(hours=3)))
        except ValueError:
            st.write(f"Geçersiz tarih-saat: {match_date} {match_time}")
            filtered_count += 1
            continue
        
        if not (start_datetime <= match_datetime <= end_datetime):
            filtered_count += 1
            continue
        
        match_info = {
            "Tarih": match_date,
            "Saat": match_time,
            "Ev Sahibi Takım": match.get("HN", ""),
            "Deplasman Takım": match.get("AN", ""),
            "Lig Adı": league_mapping.get(match.get("LC"), str(match.get("LC"))),
            "İY/MS": "Var" if any(m.get("MTID") == 5 for m in markets) else "Yok",
            "match_datetime": match_datetime,
            "MA": markets,
            "MTIDs": [m.get("MTID") for m in markets]
        }
        
        filled_columns = []
        for market in markets:
            mtid = market.get("MTID")
            sov = market.get("SOV")
            key = (mtid, float(sov) if sov is not None else None) if mtid in [11, 12, 13, 14, 15, 20, 29, 155, 207, 209, 212, 216, 218, 256, 268, 272, 301, 326, 328] else (mtid, None)
            
            if key not in mtid_mapping:
                continue
                
            for idx, outcome in enumerate(market.get("OCA", [])):
                if idx >= len(mtid_mapping[key]):
                    break
                odds = outcome.get("O")
                if odds is None:
                    continue
                match_info[mtid_mapping[key][idx]] = float(odds)
                filled_columns.append(mtid_mapping[key][idx])
        
        match_info["Oran Sayısı"] = f"{len(filled_columns)}/{len(excel_columns)}"
        api_matches.append(match_info)
    
    st.write(f"Filtrelenen maçlar: {filtered_count}, İşlenen maçlar: {len(api_matches)}")
    api_df = pd.DataFrame(api_matches)
    if api_df.empty:
        st.error("Seçilen aralıkta maç bulunamadı!")
        st.stop()
    
    return api_df.sort_values(by="match_datetime").drop(columns=["match_datetime", "MA", "MTIDs"])

# Benzer maçları bulma (v17_lig.py'den uyarlandı)
def find_similar_matches(api_df, data, mtid_mapping, league_mapping):
    def process_match(idx, row, data, excel_columns, league_mapping, threshold_columns, min_columns, league_keys, current_date, include_global_matches):
        output_rows = []
        api_row = row.copy()
        api_row["Benzerlik (%)"] = ""
        api_row["İY KG ORAN"] = api_row.get("Karşılıklı Gol Var", "")
        output_rows.append(api_row)
        
        # Lig bazlı ve global maçları filtrele
        league_id = next((k for k, v in league_mapping.items() if v == row["Lig Adı"]), None)
        league_data = data[data["Lig Adı"] == row["Lig Adı"]] if league_id else data
        global_data = data if include_global_matches else pd.DataFrame()
        
        # Benzerlik hesaplama
        for _, hist_row in league_data.iterrows():
            similarity = calculate_similarity(row, hist_row, excel_columns)
            if similarity >= 0:  # Eşik değer
                hist_row_copy = hist_row.copy()
                hist_row_copy["Benzerlik (%)"] = f"{similarity:.1f}%"
                hist_row_copy["İY/MS"] = row["İY/MS"]
                hist_row_copy["Oran Sayısı"] = row["Oran Sayısı"]
                hist_row_copy["Saat"] = row["Saat"]
                output_rows.append(hist_row_copy)
        
        if include_global_matches:
            for _, hist_row in global_data.iterrows():
                if hist_row["Lig Adı"] != row["Lig Adı"]:
                    similarity = calculate_similarity(row, hist_row, excel_columns)
                    if similarity >= 0:
                        hist_row_copy = hist_row.copy()
                        hist_row_copy["Benzerlik (%)"] = f"{similarity:.1f}%"
                        hist_row_copy["İY/MS"] = row["İY/MS"]
                        hist_row_copy["Oran Sayısı"] = row["Oran Sayısı"]
                        hist_row_copy["Saat"] = row["Saat"]
                        output_rows.append(hist_row_copy)
        
        output_rows.append({})
        return output_rows
    
    def calculate_similarity(api_row, hist_row, columns):
        differences = []
        weights = {
            "Maç Sonucu 1": 2.0, "Maç Sonucu X": 2.0, "Maç Sonucu 2": 2.0,
            "2,5 Alt/Üst Alt": 1.5, "2,5 Alt/Üst Üst": 1.5,
            "Karşılıklı Gol Var": 1.5, "Karşılıklı Gol Yok": 1.5,
            # Diğer sütunlar için varsayılan ağırlık
        }
        for col in columns:
            if col in api_row and col in hist_row and pd.notna(api_row[col]) and pd.notna(hist_row[col]):
                try:
                    diff = abs(float(api_row[col]) - float(hist_row[col]))
                    weight = weights.get(col, 1.0)
                    differences.append(weight * (diff ** 2))
                except (ValueError, TypeError):
                    continue
        if not differences:
            return 0
        mse = np.mean(differences)
        similarity = max(0, 100 - np.sqrt(mse) * 10)
        return similarity
    
    st.write("Benzerlik hesaplanıyor...")
    output_rows = []
    for idx, row in api_df.iterrows():
        output_rows.extend(process_match(idx, row, data, excel_columns, league_mapping, [], 0, [], datetime.now(), True))
    st.write("Benzerlik hesaplama tamamlandı")
    return output_rows

# Tahmin hesaplama (v17_lig.py'den uyarlandı)
def calculate_predictions(matches, api_row):
    if not matches:
        return []
    
    predictions = []
    score_counts = Counter()
    for match in matches:
        if pd.notna(match.get("MS SKOR")):
            score_counts[match["MS SKOR"]] += 1
    
    total_matches = sum(score_counts.values())
    if total_matches == 0:
        return []
    
    for score, count in score_counts.most_common():
        percentage = (count / total_matches) * 100
        if percentage >= 65:  # v17_lig.py'deki eşik
            odds = api_row.get(score, "")
            pred_str = f"Maç Skoru {score}: {percentage:.1f}%"
            if pd.notna(odds):
                pred_str += f" Oran ({odds})"
            predictions.append(pred_str)
    
    return predictions

# Stil fonksiyonu (v17_lig.py'deki apply_score_fill'den uyarlandı)
def style_dataframe(df, output_rows):
    def highlight_rows(row):
        if row["Benzerlik (%)"] == "":
            return ['background-color: lightblue'] * len(row)
        similarity = float(row["Benzerlik (%)"].strip("%")) if row["Benzerlik (%)"] else 0
        if similarity >= 65:
            return ['background-color: lightgreen; color: red; font-weight: bold'] * len(row)
        return ['background-color: lightyellow'] * len(row)
    return df.style.apply(highlight_rows, axis=1)

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
            # Bitiş zamanını oluştur
            end_datetime = datetime.combine(end_date, end_time).replace(tzinfo=timezone(timedelta(hours=3)))
            start_datetime = default_start
            
            if end_datetime <= start_datetime:
                st.error("Bitiş saati başlangıç saatinden önce olamaz!")
                st.stop()
            
            status_placeholder.write("JSON mapping'ler Drive'dan indiriliyor...")
            # MTID mapping JSON indirme
            try:
                download("https://drive.google.com/uc?id=1N1PjFla683BYTAdzVDaajmcnmMB5wiiO", "mtid_mapping.json", quiet=False)
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
                        else:
                            mtid_mapping[key_str] = value
                status_placeholder.write(f"Yüklenen MTID eşleşmeleri: {len(mtid_mapping)} adet")
            except Exception as e:
                st.error(f"MTID mapping indirme hatası: {str(e)}")
                st.stop()
            
            # League mapping JSON indirme
            try:
                download("https://drive.google.com/uc?id=1L8HA_emD92BJSuCn-P9GJF-hH55nIKE7", "league_mapping.json", quiet=False)
                with open("league_mapping.json", "r", encoding="utf-8") as f:
                    league_mapping = json.load(f)
                    league_mapping = {int(k): v for k, v in league_mapping.items()}
                status_placeholder.write(f"Yüklenen lig eşleşmeleri: {len(league_mapping)} adet")
            except Exception as e:
                st.error(f"League mapping indirme hatası: {str(e)}")
                st.stop()
            
            status_placeholder.write("Geçmiş maç verileri indiriliyor...")
            # Parquet indirme
            try:
                download("https://drive.google.com/uc?id=1GyrtGqC3SgcXun9X6oVoEQ0_JskLMF68", "matches.parquet", quiet=False)
            except Exception as e:
                st.error(f"Parquet indirme hatası: {str(e)}")
                st.stop()
            
            status_placeholder.write("Bahisler kontrol ediliyor...")
            time.sleep(0.1)
            excel_columns_basic = [
                "Tarih", "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY SKOR", "MS SKOR"
            ] + excel_columns
            try:
                data = pd.read_parquet("matches.parquet", engine="pyarrow", columns=excel_columns_basic)
            except Exception as e:
                st.error(f"Parquet okuma hatası: {str(e)}")
                st.stop()
            
            data_columns_lower = [col.lower().strip() for col in data.columns]
            excel_columns_lower = [col.lower().strip() for col in excel_columns_basic]
            available_columns = [data.columns[i] for i, col in enumerate(data_columns_lower) if col in excel_columns_lower]
            missing_columns = [col for col in excel_columns_basic if col.lower().strip() not in data_columns_lower]
            
            status_placeholder.write(f"Bahis isimleri: {', '.join(data.columns)}")
            if missing_columns:
                st.warning(f"Eksik sütunlar: {', '.join(missing_columns)}. Mevcut sütunlarla devam ediliyor.")
            
            if "Tarih" not in data.columns:
                st.error("Hata: 'Tarih' sütunu bulunamadı. Lütfen matches.parquet dosyasını kontrol edin.")
                st.stop()
            
            if "Tarih" in data.columns:
                tarih_samples = data["Tarih"].head(5).tolist()
                status_placeholder.write(f"İlk 5 Tarih örneği: {tarih_samples}")
                time.sleep(0.1)
            
            status_placeholder.write("Tarih string olarak alındı...")
            time.sleep(0.1)
            
            for col in excel_columns:
                if col in data.columns:
                    try:
                        data[col] = pd.to_numeric(data[col], errors='coerce')
                        data.loc[:, col] = data[col].where(data[col] > 1.0, np.nan)
                    except Exception as e:
                        st.warning(f"Sütun {col} temizlenirken hata: {str(e)}")
            st.session_state.data = data
            
            status_placeholder.write("Bülten verisi çekiliyor...")
            time.sleep(0.1)
            match_list, raw_data = fetch_api_data()
            if not match_list:
                st.error(f"Bülten verisi alınamadı. Hata: {raw_data.get('error', 'Bilinmeyen hata')}")
                st.stop()
            
            api_df = process_api_data(match_list, start_datetime, end_datetime, mtid_mapping, league_mapping)
            
            # Debug logları
            st.write(f"Bültenden çekilen maç sayısı: {len(match_list)}")
            st.write(f"İşlenen maçlar: {len(api_df)}")
            if not api_df.empty:
                output_rows = find_similar_matches(api_df, data, mtid_mapping, league_mapping)
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
            
            columns = ["Benzerlik (%)", "İY/MS", "Oran Sayısı", "Saat", "Tarih", "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY KG ORAN", "IY SKOR", "MS SKOR"]
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
