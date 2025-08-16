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
import os

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

# Oran sütunları (analiz için gerekli, sadeleştirilebilir)
excel_columns = [
    "Maç Sonucu 1", "Maç Sonucu X", "Maç Sonucu 2",
    "Çifte Şans 1 veya X", "Çifte Şans 1 veya 2", "Çifte Şans X veya 2",
    "1. Yarı Sonucu 1", "1. Yarı Sonucu X", "1. Yarı Sonucu 2",
    "2,5 Alt/Üst Alt", "2,5 Alt/Üst Üst",
    "3,5 Alt/Üst Alt", "3,5 Alt/Üst Üst",
    "Karşılıklı Gol Var", "Karşılıklı Gol Yok",
    "İlk Yarı/Maç Sonucu 1/1", "İlk Yarı/Maç Sonucu 1/X", "İlk Yarı/Maç Sonucu 1/2",
    "İlk Yarı/Maç Sonucu X/1", "İlk Yarı/Maç Sonucu X/X", "İlk Yarı/Maç Sonucu X/2",
    "İlk Yarı/Maç Sonucu 2/1", "İlk Yarı/Maç Sonucu 2/X", "İlk Yarı/Maç Sonucu 2/2",
    "Toplam Gol Aralığı 0-1 Gol", "Toplam Gol Aralığı 2-3 Gol", "Toplam Gol Aralığı 4-5 Gol", "Toplam Gol Aralığı 6+ Gol",
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
    "Evsahibi 0,5 Alt/Üst Alt", "Evsahibi 0,5 Alt/Üst Üst",
    "Evsahibi 1,5 Alt/Üst Alt", "Evsahibi 1,5 Alt/Üst Üst",
    "Evsahibi 2,5 Alt/Üst Alt", "Evsahibi 2,5 Alt/Üst Üst",
    "Deplasman 0,5 Alt/Üst Alt", "Deplasman 0,5 Alt/Üst Üst",
    "Deplasman 1,5 Alt/Üst Alt", "Deplasman 1,5 Alt/Üst Üst",
    "Deplasman 2,5 Alt/Üst Alt", "Deplasman 2,5 Alt/Üst Üst",
    "Daha Çok Gol Olacak Yarı 1.Y", "Daha Çok Gol Olacak Yarı Eşit", "Daha Çok Gol Olacak Yarı 2.Y",
    "Maç Skoru 1-0", "Maç Skoru 2-0", "Maç Skoru 2-1", "Maç Skoru 3-0", "Maç Skoru 3-1", "Maç Skoru 3-2",
    "Maç Skoru 4-0", "Maç Skoru 4-1", "Maç Skoru 4-2", "Maç Skoru 5-0", "Maç Skoru 5-1", "Maç Skoru 6-0",
    "Maç Skoru 0-0", "Maç Skoru 1-1", "Maç Skoru 2-2", "Maç Skoru 3-3", "Maç Skoru 0-1", "Maç Skoru 0-2",
    "Maç Skoru 1-2", "Maç Skoru 0-3", "Maç Skoru 1-3", "Maç Skoru 2-3", "Maç Skoru 0-4", "Maç Skoru 1-4",
    "Maç Skoru 2-4", "Maç Skoru 0-5", "Maç Skoru 1-5", "Maç Skoru 0-6", "Maç Skoru Diğer",
    "Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2",
    "Handikaplı Maç Sonucu (1,0) 1", "Handikaplı Maç Sonucu (1,0) X", "Handikaplı Maç Sonucu (1,0) 2",
]

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
            
            # League mapping JSON indirme
            download("https://drive.google.com/uc?id=1L8HA_emD92BJSuCn-P9GJF-hH55nIKE7", "league_mapping.json", quiet=False)
            with open("league_mapping.json", "r", encoding="utf-8") as f:
                league_mapping = json.load(f)
                league_mapping = {int(k): v for k, v in league_mapping.items()}
            status_placeholder.write(f"Yüklenen lig eşleşmeleri: {len(league_mapping)} adet")
            
            status_placeholder.write("Geçmiş maç verileri indiriliyor...")
            # Parquet indirme
            download("https://drive.google.com/uc?id=1GyrtGqC3SgcXun9X6oVoEQ0_JskLMF68", "matches.parquet", quiet=False)
            
            status_placeholder.write("Bahisler kontrol ediliyor...")
            time.sleep(0.1)
            excel_columns_basic = [
                "Tarih", "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY SKOR", "MS SKOR"
                # Korner sütunları kaldırıldı
            ] + excel_columns
            data = pd.read_parquet("matches.parquet", engine="pyarrow", columns=excel_columns_basic)
            
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
                    data[col] = pd.to_numeric(data[col], errors='coerce')
                    data.loc[:, col] = data[col].where(data[col] > 1.0, np.nan)
            st.session_state.data = data
            
            status_placeholder.write("Bülten verisi çekiliyor...")
            time.sleep(0.1)
            match_list, raw_data = fetch_api_data()  # Varsayalım aynı
            if not match_list:
                st.error(f"Bülten verisi alınamadı. Hata: {raw_data.get('error', 'Bilinmeyen hata')}")
                st.stop()
            
            api_df = process_api_data(match_list, raw_data, start_datetime, end_datetime, mtid_mapping, league_mapping)  # Mapping'leri geçir
            
            # Debug logları
            st.write(f"Bültenden çekilen maç sayısı: {len(match_list)}")
            st.write(f"İşlenen maçlar: {len(api_df)}")
            if not api_df.empty:
                output_rows = find_similar_matches(api_df, data, mtid_mapping, league_mapping)  # Mapping'leri geçir
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
            
            columns = ["Benzerlik (%)", "İY/MS", "Oran Sayısı", "Saat", "Tarih", "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY KG ORAN", "IY SKOR", "MS SKOR"]  # Korner Ort. kaldırıldı
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
