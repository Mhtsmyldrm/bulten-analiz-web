import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from gdown import download
import numpy as np
from collections import Counter
import requests

# CSS for mobile optimization and styling
st.markdown("""
<style>
h1 { font-weight: bold; color: #333; }
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

# Function to style DataFrame
def style_dataframe(df):
    def highlight_rows(row):
        if row["Benzerlik (%)"] == "":
            return ['background-color: #FFFF99'] * len(row)
        return [''] * len(row)
    
    def highlight_scores(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        groups = [group for group in output_rows]  # Assuming output_rows from analysis
        for group in groups:
            iy_scores = Counter([r["IY SKOR"] for r in group if r["Benzerlik (%)"] != ""])
            ms_scores = Counter([r["MS SKOR"] for r in group if r["Benzerlik (%)"] != ""])
            for idx, row in df.iterrows():
                if row["IY SKOR"] in iy_scores and iy_scores[row["IY SKOR"]] >= 5:
                    styles.at[idx, "IY SKOR"] = 'background-color: #90EE90'
                if row["MS SKOR"] in ms_scores and ms_scores[row["MS SKOR"]] >= 5:
                    styles.at[idx, "MS SKOR"] = 'background-color: #90EE90'
        return styles
    
    styled_df = df.style.apply(highlight_rows, axis=1).set_table_styles(
        [{'selector': 'th', 'props': [('position', 'sticky'), ('top', '0'), ('background-color', '#f0f0f0')]}]
    )
    styled_df = styled_df.apply(highlight_scores, axis=None)
    return styled_df

# Function to fetch API data (placeholder, adjust as needed)
def fetch_api_data():
    # Replace with actual API call
    # Example: response = requests.get("API_URL", headers={"Authorization": "Bearer API_KEY"})
    # return response.json()
    return []  # Placeholder, replace with actual data

# Function to find similar matches (placeholder, adjust as needed)
def find_similar_matches(api_data, excel_data):
    # Replace with actual logic
    # Example: Compare api_data with excel_data, return matches
    return []  # Placeholder, replace with output_rows

# Analyze button
if st.button("Analize Başla", disabled=st.session_state.analysis_done):
    try:
        with status_placeholder.container():
            st.spinner("Excel yükleniyor...")
            # Download Excel from Google Drive
            file_id = "11m7tX2xCavCM_cij69UaSVijFuFQbveM"
            download(f"https://drive.google.com/uc?id={file_id}", "matches.xlsx", quiet=False)
            
            # Read Excel
            excel_columns = ["Unnamed: 0", "Tarih", "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY SKOR", "MS SKOR"]  # Adjust as needed
            data = pd.read_excel("matches.xlsx", sheet_name="Bahisler", usecols=excel_columns)
            st.session_state.data = data
            
            st.spinner("API verisi çekiliyor...")
            api_data = fetch_api_data()
            if not api_data:
                st.error("API verisi alınamadı. Lütfen daha sonra tekrar deneyin.")
                st.stop()
            
            st.spinner("Analiz ediliyor...")
            # Dynamic time (+2 hours)
            current_time = datetime.now() + timedelta(hours=2)
            output_rows = find_similar_matches(api_data, data)
            
            if not output_rows:
                st.error("Eşleşme bulunamadı. Lütfen verileri kontrol edin.")
                st.stop()
            
            # Convert output_rows to DataFrames
            iyms_df = pd.DataFrame([r for r in output_rows if r["İY/MS Bültende Var mı"] == "Evet"])
            main_df = pd.DataFrame([r for r in output_rows if r["İY/MS Bültende Var mı"] == "Hayır"])
            
            # Ensure all required columns
            columns = ["Benzerlik (%)", "İY/MS Bültende Var mı", "Oran Sayısı", "Unnamed: 0", "Tarih", 
                       "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY SKOR", "MS SKOR"]
            iyms_df = iyms_df.reindex(columns=columns, fill_value="")
            main_df = main_df.reindex(columns=columns, fill_value="")
            
            st.session_state.iyms_df = iyms_df
            st.session_state.main_df = main_df
            st.session_state.analysis_done = True
            
            st.success("Analiz tamamlandı!")
    
    except Exception as e:
        st.error(f"Hata oluştu: {str(e)}")
        st.stop()

# Display results if analysis is done
if st.session_state.analysis_done and st.session_state.iyms_df is not None:
    tab1, tab2 = st.tabs(["İY/MS Bülteni", "Normal Bülten"])
    with tab1:
        st.dataframe(style_dataframe(st.session_state.iyms_df), height=600)
    with tab2:
        st.dataframe(style_dataframe(st.session_state.main_df), height=600)
