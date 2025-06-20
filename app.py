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

# Oran sütunları (Excel'e göre)
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

# MTID eşleşmeleri
mtid_mapping = {
    (1, None): ["Maç Sonucu 1", "Maç Sonucu X", "Maç Sonucu 2"],
    (3, None): ["Çifte Şans 1 veya X", "Çifte Şans 1 veya 2", "Çifte Şans X veya 2"],
    (5, None): ["İlk Yarı/Maç Sonucu 1/1", "İlk Yarı/Maç Sonucu 1/X", "İlk Yarı/Maç Sonucu 1/2",
                "İlk Yarı/Maç Sonucu X/1", "İlk Yarı/Maç Sonucu X/X", "İlk Yarı/Maç Sonucu X/2",
                "İlk Yarı/Maç Sonucu 2/1", "İlk Yarı/Maç Sonucu 2/X", "İlk Yarı/Maç Sonucu 2/2"],
    (7, None): ["1. Yarı Sonucu 1", "1. Yarı Sonucu X", "1. Yarı Sonucu 2"],
    (9, None): ["2. Yarı Sonucu 1", "2. Yarı Sonucu X", "2. Yarı Sonucu 2"],
    (12, None): ["2,5 Alt/Üst Alt", "2,5 Alt/Üst Üst"],
    (13, None): ["3,5 Alt/Üst Alt", "3,5 Alt/Üst Üst"],
    (14, 0.5): ["0,5 Alt/Üst Alt", "0,5 Alt/Üst Üst"],
    (14, 1.5): ["1,5 Alt/Üst Alt", "1,5 Alt/Üst Üst"],
    (14, 4.5): ["4,5 Alt/Üst Alt", "4,5 Alt/Üst Üst"],
    (14, 5.5): ["5,5 Alt/Üst Alt", "5,5 Alt/Üst Üst"],
    (14, 6.5): ["6,5 Alt/Üst Alt", "6,5 Alt/Üst Üst"],
    (14, 7.5): ["7,5 Alt/Üst Alt", "7,5 Alt/Üst Üst"],
    (15, 1.5): ["1. Yarı 1,5 Alt/Üst Alt", "1. Yarı 1,5 Alt/Üst Üst"],
    (15, 2.5): ["1. Yarı 2,5 Alt/Üst Alt", "1. Yarı 2,5 Alt/Üst Üst"],
    (15, 3.5): ["1. Yarı Alt/Üst (3,5) Alt", "1. Yarı Alt/Üst (3,5) Üst"],
    (20, 0.5): ["Evsahibi 0,5 Alt/Üst Alt", "Evsahibi 0,5 Alt/Üst Üst"],
    (20, 1.5): ["Evsahibi 1,5 Alt/Üst Alt", "Evsahibi 1,5 Alt/Üst Üst"],
    (20, 2.5): ["Evsahibi 2,5 Alt/Üst Alt", "Evsahibi 2,5 Alt/Üst Üst"],
    (20, 3.5): ["Evsahibi 3,5 Alt/Üst Alt", "Evsahibi 3,5 Alt/Üst Üst"],
    (20, 4.5): ["Evsahibi 4,5 Alt/Üst Alt", "Evsahibi 4,5 Alt/Üst Üst"],
    (20, 5.5): ["Evsahibi 5,5 Alt/Üst Alt", "Evsahibi 5,5 Alt/Üst Üst"],
    (29, 0.5): ["Deplasman 0,5 Alt/Üst Alt", "Deplasman 0,5 Alt/Üst Üst"],
    (29, 1.5): ["Deplasman 1,5 Alt/Üst Alt", "Deplasman 1,5 Alt/Üst Üst"],
    (29, 2.5): ["Deplasman 2,5 Alt/Üst Alt", "Deplasman 2,5 Alt/Üst Üst"],
    (29, 3.5): ["Deplasman 3,5 Alt/Üst Alt", "Deplasman 3,5 Alt/Üst Üst"],
    (29, 4.5): ["Deplasman 4,5 Alt/Üst Alt", "Deplasman 4,5 Alt/Üst Üst"],
    (38, None): ["Karşılıklı Gol Var", "Karşılıklı Gol Yok"],
    (43, None): ["Toplam Gol Aralığı 0-1 Gol", "Toplam Gol Aralığı 2-3 Gol", "Toplam Gol Aralığı 4-5 Gol", "Toplam Gol Aralığı 6+ Gol"],
    (48, None): ["Daha Çok Gol Olacak Yarı 1.Y", "Daha Çok Gol Olacak Yarı Eşit", "Daha Çok Gol Olacak Yarı 2.Y"],
    (155, 0.5): ["1. Yarı 0,5 Alt/Üst Alt", "1. Yarı 0,5 Alt/Üst Üst"],
    (205, None): ["Maç Skoru 1-0", "Maç Skoru 2-0", "Maç Skoru 2-1", "Maç Skoru 3-0", "Maç Skoru 3-1", "Maç Skoru 3-2",
                  "Maç Skoru 4-0", "Maç Skoru 4-1", "Maç Skoru 4-2", "Maç Skoru 5-0", "Maç Skoru 5-1", "Maç Skoru 6-0",
                  "Maç Skoru 0-0", "Maç Skoru 1-1", "Maç Skoru 2-2", "Maç Skoru 3-3", "Maç Skoru 0-1", "Maç Skoru 0-2",
                  "Maç Skoru 1-2", "Maç Skoru 0-3", "Maç Skoru 1-3", "Maç Skoru 2-3", "Maç Skoru 0-4", "Maç Skoru 1-4",
                  "Maç Skoru 2-4", "Maç Skoru 0-5", "Maç Skoru 1-5", "Maç Skoru 0-6", "Maç Skoru Diğer"],
    (216, 6.5): ["(6,5) Korner Alt/Üst Alt", "(6,5) Korner Alt/Üst Üst"],
    (216, 7.5): ["(7,5) Korner Alt/Üst Alt", "(7,5) Korner Alt/Üst Üst"],
    (216, 8.5): ["(8,5) Korner Alt/Üst Alt", "(8,5) Korner Alt/Üst Üst"],
    (216, 9.5): ["(9,5) Korner Alt/Üst Alt", "(9,5) Korner Alt/Üst Üst"],
    (216, 10.5): ["(10,5) Korner Alt/Üst Alt", "(10,5) Korner Alt/Üst Üst"],
    (216, 11.5): ["(11,5) Korner Alt/Üst Alt", "(11,5) Korner Alt/Üst Üst"],
    (216, 12.5): ["(12,5) Korner Alt/Üst Alt", "(12,5) Korner Alt/Üst Üst"],
    (258, None): ["1. Yarı Çifte Şans 1-X", "1. Yarı Çifte Şans 1-2", "1. Yarı Çifte Şans X-2"],
    (268, -5.0): ["Handikaplı Maç Sonucu (-5,0) 1", "Handikaplı Maç Sonucu (-5,0) X", "Handikaplı Maç Sonucu (-5,0) 2"],
    (268, -4.0): ["Handikaplı Maç Sonucu (-4,0) 1", "Handikaplı Maç Sonucu (-4,0) X", "Handikaplı Maç Sonucu (-4,0) 2"],
    (268, -3.0): ["Handikaplı Maç Sonucu (-3,0) 1", "Handikaplı Maç Sonucu (-3,0) X", "Handikaplı Maç Sonucu (-3,0) 2"],
    (268, -2.0): ["Handikaplı Maç Sonucu (-2,0) 1", "Handikaplı Maç Sonucu (-2,0) X", "Handikaplı Maç Sonucu (-2,0) 2"],
    (268, -1.0): ["Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2"],
    (268, 1.0): ["Handikaplı Maç Sonucu (1,0) 1", "Handikaplı Maç Sonucu (1,0) X", "Handikaplı Maç Sonucu (1,0) 2"],
    (268, 2.0): ["Handikaplı Maç Sonucu (2,0) 1", "Handikaplı Maç Sonucu (2,0) X", "Handikaplı Maç Sonucu (2,0) 2"],
    (268, 3.0): ["Handikaplı Maç Sonucu (3,0) 1", "Handikaplı Maç Sonucu (3,0) X", "Handikaplı Maç Sonucu (3,0) 2"],
    (268, 4.0): ["Handikaplı Maç Sonucu (4,0) 1", "Handikaplı Maç Sonucu (4,0) X", "Handikaplı Maç Sonucu (4,0) 2"],
    (272, 3.5): ["Maç Sonucu ve (3,5) Alt/Üst 1 ve Alt", "Maç Sonucu ve (3,5) Alt/Üst X ve Alt", "Maç Sonucu ve (3,5) Alt/Üst 2 ve Alt",
                 "Maç Sonucu ve (3,5) Alt/Üst 1 ve Üst", "Maç Sonucu ve (3,5) Alt/Üst X ve Üst", "Maç Sonucu ve (3,5) Alt/Üst 2 ve Üst"],
    (272, 4.5): ["Maç Sonucu ve (4,5) Alt/Üst 1 ve Alt", "Maç Sonucu ve (4,5) Alt/Üst X ve Alt", "Maç Sonucu ve (4,5) Alt/Üst 2 ve Alt",
                 "Maç Sonucu ve (4,5) Alt/Üst 1 ve Üst", "Maç Sonucu ve (4,5) Alt/Üst X ve Üst", "Maç Sonucu ve (4,5) Alt/Üst 2 ve Üst"],
    (291, None): ["İlk Gol 1", "İlk Gol Olmaz", "İlk Gol 2"],
    (326, None): ["Tek/Çift Tek", "Tek/Çift Çift"],
    (338, None): ["Toplam Korner Aralığı 0-8", "Toplam Korner Aralığı 9-11", "Toplam Korner Aralığı 12+"],
    (342, None): ["Maç Sonucu ve (1,5) Alt/Üst 1 ve Alt", "Maç Sonucu ve (1,5) Alt/Üst X ve Alt", "Maç Sonucu ve (1,5) Alt/Üst 2 ve Alt",
                  "Maç Sonucu ve (1,5) Alt/Üst 1 ve Üst", "Maç Sonucu ve (1,5) Alt/Üst X ve Üst", "Maç Sonucu ve (1,5) Alt/Üst 2 ve Üst"],
    (343, None): ["Maç Sonucu ve (2,5) Alt/Üst 1 ve Alt", "Maç Sonucu ve (2,5) Alt/Üst X ve Alt", "Maç Sonucu ve (2,5) Alt/Üst 2 ve Alt",
                  "Maç Sonucu ve (2,5) Alt/Üst 1 ve Üst", "Maç Sonucu ve (2,5) Alt/Üst X ve Üst", "Maç Sonucu ve (2,5) Alt/Üst 2 ve Üst"],
    (344, None): ["En Çok Korner 1", "En Çok Korner X", "En Çok Korner 2"],
    (345, None): ["1. Yarı En Çok Korner 1", "1. Yarı En Çok Korner X", "1. Yarı En Çok Korner 2"],
    (346, None): ["İlk Korner 1", "İlk Korner Olmaz", "İlk Korner 2"],
    (347, None): ["1. Yarı Korner Aralığı 0-4", "1. Yarı Korner Aralığı 5-6", "1. Yarı Korner Aralığı 7+"],
    (348, None): ["Korner Tek/Çift Tek", "Korner Tek/Çift Çift"],
    (349, 1.5): ["(1,5) Kart Alt/Üst Alt", "(1,5) Kart Alt/Üst Üst"],
    (349, 2.5): ["(2,5) Kart Alt/Üst Alt", "(2,5) Kart Alt/Üst Üst"],
    (349, 3.5): ["(3,5) Kart Alt/Üst Alt", "(3,5) Kart Alt/Üst Üst"],
    (349, 4.5): ["(4,5) Kart Alt/Üst Alt", "(4,5) Kart Alt/Üst Üst"],
    (349, 5.5): ["(5,5) Kart Alt/Üst Alt", "(5,5) Kart Alt/Üst Üst"],
    (349, 6.5): ["(6,5) Kart Alt/Üst Alt", "(6,5) Kart Alt/Üst Üst"],
    (349, 7.5): ["(7,5) Kart Alt/Üst Alt", "(7,5) Kart Alt/Üst Üst"],
    (349, 8.5): ["(8,5) Kart Alt/Üst Alt", "(8,5) Kart Alt/Üst Üst"],
    (349, 9.5): ["(9,5) Kart Alt/Üst Alt", "(9,5) Kart Alt/Üst Üst"],
    (350, None): ["Kırmızı Kart Var", "Kırmızı Kart Yok"],
    (351, None): ["Maç Sonucu (Uzt. Dahil) 1", "Maç Sonucu (Uzt. Dahil) 2"],
    (352, 2.5): ["1.Yarı (2,5) Korner Alt/Üst Alt", "1.Yarı (2,5) Korner Alt/Üst Üst"],
    (352, 3.5): ["1.Yarı (3,5) Korner Alt/Üst Alt", "1.Yarı (3,5) Korner Alt/Üst Üst"],
    (352, 4.5): ["1.Yarı (4,5) Korner Alt/Üst Alt", "1.Yarı (4,5) Korner Alt/Üst Üst"],
    (352, 5.5): ["1.Yarı (5,5) Korner Alt/Üst Alt", "1.Yarı (5,5) Korner Alt/Üst Üst"],
    (352, 6.5): ["1.Yarı (6,5) Korner Alt/Üst Alt", "1.Yarı (6,5) Korner Alt/Üst Üst"],
}

# Lig kodları eşleştirmesi
league_mapping = {
    15: "ABD", 354: "ÇİNSL", 347: "AL1", 62: "RUS1", 19843: "İKP", 19829: "İKP", 132: "AL2", 161: "AL3",
    47154: "ARJ", 598: "AU2", 1209: "AVU", 1208: "AVUS", 1220: "BEL", 10276: "BR1", 21: "BR2", 1262: "DAN",
    567: "AVUS", 628: "FİN", 381: "FR1", 614: "FR2", 1809: "GKOR2", 636: "GKOR", 681: "HOL2", 322: "HOL",
    24: "İN1", 12: "İN2", 52: "İNCL", 152: "İNLK", 43: "İNP", 129: "İS1", 1951: "İS2", 1975: "İSV", 51: "İSÇ",
    579: "İTA", 1774: "İTB", 10096: "İTC", 642: "JAP", 1873: "NOR", 202: "POL", 1897: "POR2", 566: "POR",
    1980: "T1L", 584: "TSL", 20152: "BEL", 45056: "BEL", 205: "İRL", 349: "İSÇ2", 143: "İTA", 623: "NOR3", 1259: "ÇEK",
    35072: "HİNSL", 1238: "ÇİN2", 1894: "POL2", 1913: "ROM", 45: "AL1", 573: "NOR", 10074: "İS3", 45269: "MEK",
    16324: "BOSN", 47754: "MLTP", 47754: "MALTP", 630: "İZL", 1881: "PER", 1878: "PAR", 1797: "JAP2", 1297: "İCON",
    1298: "İCON", 1232: "BRK", 1814: "LET", 20401: "GUAT", 23482: "ETH", 16161: "AVNPL", 16332: "İSÇ4", 16336: "İSÇ4",
    47754: "MALTP", 974: "ENDL1", 2001: "BAE", 10196: "SUUD", 16184: "IRAN", 5610: "BAH", 47539: "MSR", 1242: "KOL",
    22348: "KAPL", 5161: "EKV1", 1858: "FAS", 970: "USLP", 49: "EKV1", 5571: "ELSAL", 45236: "VEN", 5569: "KOSTA",
    2841: "ARJPBN", 49: "ŞİL", 2007: "URU", 16338: "USL1", 20546: "BOLİ", 5575: "HON", 5564: "AVNPL", 16331: "GK3L",
    5562: "AVSQ", 1326: "HK1", 986: "ÇEK2", 16461: "SLVK2", 10063: "İS4", 1995: "UKR", 16340: "VİET", 1215: "BLR",
    22377: "LET1", 22353: "KEN", 10070: "NOR4", 16336: "İSÇ4", 15822: "EST1", 576: "MAC", 33402: "HIR2", 4: "KAZP",
    1975: "İSV2", 997: "POL1", 1894: "POL2", 571: "NOR1", 35791: "BUL1", 1817: "LITA", 22365: "LIT1", 25886: "SIRP",
    742: "GAFPSL", 2701: "GAF1", 33585: "İTAPŞ1", 2935: "İSV1Y", 14408: "FAROEM", 1978: "TUN1", 37159: "MSR2", 20146: "DAN1",
    10156: "POR3", 1213: "AZERS", 22625: "BAE2", 2702: "MAC2", 2018: "GALWK", 1000: "SLVN", 19: "FİN2", 31578: "MOLD",
    5441: "YUN", 624: "NOR3", 25909: "ÇEK", 20904: "İSÇ4", 606: "İSÇ3", 16337: "İSÇ4", 620: "İSÇ3", 207: "HIR", 33592: "İNKPL",
    25887: "SIRP", 23287: "GANA", 19021: "CAFU20", 35789: "BUL1", 1780: "İTC", 44389: "POR3", 1942: "SLVK", 1940: "SLVK", 
    22378: "SLVN2", 1258: "ÇEK", 2783: "ARJPB", 10093: "NİK", 35126: "MEK2", 45240: "İSV", 45241: "İSV", 701: "BEL", 5576: "SUUD1",
    33101: "KUV", 352: "ROM", 19013: "CAFU20", 33362: "INGPDL", 20063: "DAN", 16328: "JAP3", 47573: "MSR", 35790: "BUL1",
    1907: "KATEK", 33740: "KUV", 33266: "IRAK", 19022: "CAFU20", 1927: "İK2", 1926: "İK1", 1925: "İKCL", 10014: "ŞMP", 1821: "LITK",
    2014: "ABDK", 10057: "CSA", 10008: "LKU", 16326: "GUR", 1217: "BLRK", 10326: "ŞİLİK", 1269: "DAK", 1866: "KİRL", 1826: "MEK", 
    1877: "NOK", 15881: "SIRBK", 23986: "AVKL", 588: "AVL", 1276: "İNCL", 18221: "BOSK", 1986: "T2L-P", 20523: "ELSAL", 5567: "AVNPL",
    5563: "AVNPL", 5566: "AVNPL", 2006: "BAECK", 34834: "DAN2", 957: "ALMBÖL", 47856: "İSÇD4", 1268: "DAN2", 33631: "HOLTW", 
    1310: "FR3", 1329: "İZL1", 350: "İR1", 48011: "MLTP", 48011: "MALTP", 17261: "İZL2", 1918: "RUS1", 26582: "DAN3", 26581: "DAN3",
    45325: "İTC", 1928: "İKCK", 1199: "CZYR", 1211: "AVU", 36123: "İS4", 45245: "VEN", 16341: "AVNPL", 36161: "İS4", 20166: "DAN1",
    1310: "FR3", 1277: "İN1", 15921: "YUN", 47667: "YUN", 47988: "ARJ", 1278: "İN2", 45231: "BEL2", 10301: "ALU19", 1947: "GAFK", 47912: "İSÇD4",
    1783: "İTC", 33637: "İTKSA", 22369: "HK2", 33339: "NPL2", 22622: "İSKPR", 985: "SİNP", 33609: "İTKSA", 45135: "FİN3", 19114: "TANZ",
    2016: "GAL", 1207: "ARJK", 45329: "FRK1", 15981: "KOSTA", 26050: "USL2", 35955: "INGPDL", 45274: "INGPL2-1",
    1813: "GKOR", 987: "ÇEK", 1916: "ROM", 1945: "SLVN", 1861: "HOL2", 26102: "AVUS", 2000: "UKR", 10069: "RUS", 1983: "TÜK", 1279: "İBSL",
    605: "İTK", 19161: "CAFU20", 47034: "ÜRDK", 21755: "KAZP", 1308: "FR2", 1981: "T1L", 16061: "ESTK", 1331: "İZK", 44465: "LUBN",
    1257: "HIRK", 24424: "MLTAK", 1328: "MACK", 3921: "YUK", 25833: "MOLDK", 1775: "İTB", 1776: "İTB", 1667: "U17", 48203: "MISLK",
    1941: "SLVK", 20742: "SLVK", 48201: "BOLPLK", 1241: "ÇİNK", 47665: "AFCŞLK", 1805: "JLK", 3886: "SİNK", 1859: "FASK", 33805: "BULK",
    1309: "FR2", 1860: "HOL", 1311: "AL1P", 48206: "UKŞK", 36617: "İTAPŞ1", 10134: "ŞMP-K", 36621: "POR2", 1914: "ROM2", 26901: "KOSTA",
    1312: "AL2", 599: "İKK", 130: "AFK", 20743: "POR", 343: "FRK", 1904: "POK", 36864: "BUL1", 10223: "AVKUL", 48231: "FAS", 1924: "SAKK",
    1531: "HAZ", 36644: "HOLTW", 16335: "İSÇ4", 36915: "BUL1", 20705: "BAH", 26374: "İS3", 1998: "UKR", 1261: "ÇEK", 10082: "CON", 1484: "HAZ",
    1976: "İSV", 1917: "RUS", 48232: "KDK", 36219: "RUK", 1210: "AVU", 10026: "CAFŞL", 10285: "DKE", 10287: "VENK", 10343: "KOLK", 10253: "DKE",
    10007: "U21", 1757: "HAZ", 1275: "MSRK", 10050: "DKE", 1407: "AVUL", 1349: "DKE", 1758: "HAZ", 10104: "ASKE", 1755: "HU23", 1304: "FİK",
    1243: "KOL", 1244: "KOL", 16463: "POL2", 10051: "U21", 1952: "İS2", 1692: "U19", 1458: "GK", 10345: "KDK", 1455: "GK", 958: "HAZ", 1800: "JPK",
    26803: "U19K", 26788: "U19K", 1691: "U21", 1456: "GK", 19666: "AVNPL", 1946: "GAFPSL", 17682: "MOLD", 1457: "GK", 1708: "U21"

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
    
        df_index = 0
        for group in groups:
            match_rows = [r for r in group if r.get("Benzerlik (%)", "") != ""]
            group_size = len(group)
            if len(match_rows) < 5:
                df_index += group_size
                continue
            # IY SKOR ve MS SKOR için ayrı ayrı kontrol
            iy_scores = Counter([r.get("IY SKOR", "") for r in match_rows if r.get("IY SKOR", "") != ""])
            ms_scores = Counter([r.get("MS SKOR", "") for r in match_rows if r.get("MS SKOR", "") != ""])
            for i in range(df_index, df_index + group_size):
                if i >= len(df):
                    break
                row = df.iloc[i]
                if row["IY SKOR"] in iy_scores and iy_scores[row["IY SKOR"]] >= 5:
                    styles.at[i, "IY SKOR"] = 'background-color: #0000FF'
                if row["MS SKOR"] in ms_scores and ms_scores[row["MS SKOR"]] >= 5:
                    styles.at[i, "MS SKOR"] = 'background-color: #0000FF'
            df_index += group_size
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

    with status_placeholder.container():
        status_placeholder.write(f"Analiz aralığı: {start_datetime.strftime('%d.%m.%Y %H:%M')} - {end_datetime.strftime('%d.%m.%Y %H:%M')}")
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
            match_datetime = datetime.strptime(f"{match_date} {match_time}", "%d.%m.%Y %H:%M").replace(tzinfo=timezone(timedelta(hours=3)))  # TR saati
        except ValueError as e:
            skipped_matches.append({"reason": f"Date parse error: {str(e)}", "date": match_date, "time": match_time})
            continue
        
        if not (start_datetime <= match_datetime <= end_datetime):
            skipped_matches.append({"reason": "Outside time range", "date": match_date, "time": match_time})
            continue
        
        league_code = match.get("LC", None)
        league_name = league_mapping.get(league_code, str(league_code))

        iy_kg_oran = np.nan
        for market in match.get("MA", []):
            if market.get("MTID") == 452:
                oca_list = market.get("OCA", [])
                for outcome in oca_list:
                    if outcome.get("N") == 1:
                        odds = outcome.get("O")
                        if odds is not None and isinstance(odds, (int, float)):
                            iy_kg_oran = float(odds)
                        break
                break
                
        match_info = {
            "Saat": match_time,
            "Tarih": match_date,
            "Ev Sahibi Takım": match.get("HN", ""),
            "Deplasman Takım": match.get("AN", ""),
            "IY KG ORAN": iy_kg_oran,
            "Lig Adı": league_name,
            "İY/MS": "Var" if any(m.get("MTID") == 5 for m in match.get("MA", [])) else "Yok",
            "match_datetime": match_datetime,
            "MTIDs": [m.get("MTID") for m in match.get("MA", [])]  # Korner kontrolü için
        }
        
        filled_columns = []
        for market in match.get("MA", []):
            mtid = market.get("MTID")
            sov = market.get("SOV")
            key = (mtid, float(sov) if sov is not None else None) if mtid in [14, 15, 20, 29, 155, 268, 272, 349, 352] else (mtid, None)
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
                if key == (268, -1.0) and len(handicap_samples) < 5:
                    handicap_samples.append(f"{matched_column}: {odds}")
        
        match_info["Oran Sayısı"] = f"{len(filled_columns)}/{len(excel_columns)}"
        skipped_matches.append({
            "reason": "Match included",
            "date": match_date,
            "time": match_time,
            "match_datetime": match_datetime.strftime("%d.%m.%Y %H:%M"),
            "home_team": match.get("HN", ""),
            "away_team": match.get("AN", "")
        })
        api_matches.append(match_info)
    
    api_df = pd.DataFrame(api_matches)
    if api_df.empty:
        with status_placeholder.container():
            status_placeholder.write(f"Uyarı: Seçilen saat aralığında maç bulunamadı. Bülten verisi: {len(match_list)} maç, atlanan: {len(skipped_matches)}")
            status_placeholder.write(f"Atlanma nedenleri (ilk 5): {[{k: v for k, v in s.items() if k != 'data'} for s in skipped_matches[:5]]}")
            status_placeholder.write(f"Çekilen maçlar (ilk 5): {[dict((k, v) for k, v in s.items() if k != 'data') for s in [s for s in skipped_matches if s['reason'] == 'Match included'][:5]]}")
        return api_df

    api_df = api_df.sort_values(by="match_datetime", ascending=True).reset_index(drop=True)
    api_df = api_df.drop(columns=["match_datetime"])
    
    if 'Maç Sonucu 1' not in api_df.columns:
        api_df['Maç Sonucu 1'] = 2.0
    if 'Maç Sonucu X' not in api_df.columns:
        api_df['Maç Sonucu X'] = 3.5
    if 'Maç Sonucu 2' not in api_df.columns:
        api_df['Maç Sonucu 2'] = 3.0
    
    for col in excel_columns:
        if col in api_df.columns:
            api_df[col] = pd.to_numeric(api_df[col], errors='coerce')
            api_df.loc[:, col] = api_df[col].where(api_df[col] > 1.0, np.nan)
    
    with status_placeholder.container():
        status_placeholder.write(f"Bültenden {len(api_df)} maç işlendi.")
        status_placeholder.write(f"Bülten maçlarının Tarih örnekleri: {tarih_samples}")
        status_placeholder.write(f"Handikaplı Maç Sonucu (-1,0) örnekleri: {handicap_samples}")
        time.sleep(0.1)
    return api_df

# Function to calculate corner average
def calculate_corner_average(data, home_team, away_team, league_name, current_date):
    if league_name not in data["Lig Adı"].values:
        return np.nan
    
    # Lig bazlı filtreleme
    league_data = data[data["Lig Adı"] == league_name].copy()
    
    # Takım isimlerini normalize et ve eşleştir
    league_teams = set(league_data["Ev Sahibi Takım"].unique()).union(set(league_data["Deplasman Takım"].unique()))
    home_team_match = difflib.get_close_matches(home_team, league_teams, n=1, cutoff=0.6)
    away_team_match = difflib.get_close_matches(away_team, league_teams, n=1, cutoff=0.6)
    
    if not home_team_match or not away_team_match:
        return np.nan
    
    home_team = home_team_match[0]
    away_team = away_team_match[0]
    
    # Tarihleri datetime'a çevir
    league_data["Tarih"] = pd.to_datetime(league_data["Tarih"], errors="coerce", dayfirst=True)
    league_data = league_data.dropna(subset=["Tarih"]).sort_values(by="Tarih", ascending=False)
    
    # Ev sahibi takımın son 5 maçı
    home_matches = league_data[
        (league_data["Ev Sahibi Takım"] == home_team) | (league_data["Deplasman Takım"] == home_team)
    ].head(5)
    
    home_corners = []
    for _, row in home_matches.iterrows():
        if row["Ev Sahibi Takım"] == home_team:
            corner = row["EV KORNER"] if pd.notna(row["EV KORNER"]) else 0
        else:
            corner = row["DEP KORNER"] if pd.notna(row["DEP KORNER"]) else 0
        home_corners.append(corner)
    
    # Deplasman takımın son 5 maçı
    away_matches = league_data[
        (league_data["Ev Sahibi Takım"] == away_team) | (league_data["Deplasman Takım"] == away_team)
    ].head(5)
    
    away_corners = []
    for _, row in away_matches.iterrows():
        if row["Ev Sahibi Takım"] == away_team:
            corner = row["EV KORNER"] if pd.notna(row["EV KORNER"]) else 0
        else:
            corner = row["DEP KORNER"] if pd.notna(row["DEP KORNER"]) else 0
        away_corners.append(corner)
    
    # Ortalama hesaplama
    home_avg = np.mean(home_corners) if home_corners else 0
    away_avg = np.mean(away_corners) if away_corners else 0
    total_avg = home_avg + away_avg
    
    return round(total_avg, 2) if total_avg > 0 else np.nan

# Function to find similar matches
def find_similar_matches(api_df, data):
    with status_placeholder.container():
        status_placeholder.write("Maçlar analiz ediliyor...")
        time.sleep(0.1)
    
    output_rows = []
    min_columns = int(len(excel_columns) * 0.15)
    league_keys = set(league_mapping.values())
    
    current_date = datetime.now(timezone(timedelta(hours=3)))
    
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
        
        # Korner ortalaması hesaplama
        corner_avg = np.nan
        if (338 in row["MTIDs"] or 216 in row["MTIDs"]) and api_league in league_keys:
            corner_avg = calculate_corner_average(
                data, row["Ev Sahibi Takım"], row["Deplasman Takım"], api_league, current_date
            )
        
        api_odds_array = np.array([
            float(api_odds.get(col)) if api_odds.get(col) not in ["", None] else np.nan
            for col in common_columns
        ])
        data_odds_array = data_filtered[common_columns].to_numpy(dtype=float, na_value=np.nan)
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
            "Korner Ort.": corner_avg if pd.notna(corner_avg) else "",
            "Saat": row["Saat"],
            "Tarih": row["Tarih"],
            "Ev Sahibi Takım": row["Ev Sahibi Takım"],
            "Deplasman Takım": row["Deplasman Takım"],
            "Lig Adı": row["Lig Adı"],
            "IY KG ORAN": "" if pd.isna(row.get("IY KG ORAN")) else row.get("IY KG ORAN"),
            "IY SKOR": "",
            "MS SKOR": ""
        }
        for col in data.columns:
            if col in excel_columns:
                match_info[col] = row.get(col, np.nan)
            elif col not in match_info:
                match_info[col] = ""
        output_rows.append(match_info)
        
        for match in top_league_matches:
            data_row = match["data_row"]
            match_odds_count = sum(1 for col in excel_columns if col in data_row and pd.notna(data_row[col]))
            match_info = {
                "Benzerlik (%)": f"{match['similarity_percent']:.2f}%",
                "İY/MS": "",
                "Oran Sayısı": f"{match_odds_count}/{len(excel_columns)}",
                "Korner Ort.": "",
                "Saat": "",
                "Tarih": str(data_row.get("Tarih", "")),
                "Ev Sahibi Takım": str(data_row.get("Ev Sahibi Takım", "")),
                "Deplasman Takım": str(data_row.get("Deplasman Takım", "")),
                "Lig Adı": str(data_row.get("Lig Adı", "")),
                "IY KG ORAN": "",
                "IY SKOR": str(data_row.get("IY SKOR", "")),
                "MS SKOR": str(data_row.get("MS SKOR", ""))
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
            
            api_odds_array_global = np.array([api_odds.get(col, np.nan) for col in common_columns_global])
            data_odds_array_global = data_global[common_columns_global].to_numpy()
            diff_sums_global = np.nansum(np.abs(data_odds_array_global - api_odds_array_global) / np.maximum(np.abs(data_odds_array_global), np.abs(api_odds_array_global)), axis=1)
            similarity_percents_global = (1 - diff_sums_global / len(common_columns_global)) * 100
            
            similarities_global = []
            min_odds_count = len(api_odds) * 0.5 if row["İY/MS"] == "Var" else 0
            for i, sim_percent in enumerate(similarity_percents_global):
                if np.isnan(sim_percent):
                    continue
                data_row = data_global.iloc[i]
                if data_row["Lig Adı"] == api_league:
                    continue
                match_odds_count = sum(1 for col in excel_columns if col in data_row and pd.notna(data_row[col]))
                if row["İY/MS"] == "Var" and match_odds_count < min_odds_count:
                    continue
                similarities_global.append({
                    "similarity_diff": diff_sums_global[i],
                    "similarity_percent": sim_percent,
                    "data_row": data_row,
                    "odds_count": match_odds_count
                })
            
            similarities_global.sort(key=lambda x: x["similarity_diff"])
            top_global_matches = similarities_global[:5]
            
            for match in top_global_matches:
                data_row = match["data_row"]
                match_info = {
                    "Benzerlik (%)": f"{match['similarity_percent']:.2f}%",
                    "İY/MS": "",
                    "Oran Sayısı": f"{match['odds_count']}/{len(excel_columns)}",
                    "Korner Ort.": "",
                    "Saat": "",
                    "Tarih": str(data_row.get("Tarih", "")),
                    "Ev Sahibi Takım": str(data_row.get("Ev Sahibi Takım", "")),
                    "Deplasman Takım": str(data_row.get("Deplasman Takım", "")),
                    "Lig Adı": str(data_row.get("Lig Adı", "")),
                    "IY KG ORAN": "",
                    "IY SKOR": str(data_row.get("IY SKOR", "")),
                    "MS SKOR": str(data_row.get("MS SKOR", ""))
                }
                for col in data.columns:
                    if col not in match_info:
                        match_info[col] = str(data_row.get(col, ""))
                output_rows.append(match_info)
        
        output_rows.append({})
    
    with status_placeholder.container():
        status_placeholder.write(f"Analiz tamamlandı, {len([r for r in output_rows if r])} satır bulundu.")
        time.sleep(0.1)
    return output_rows

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
            
            status_placeholder.write("Geçmiş maç verileri indiriliyor...")
            time.sleep(0.1)
            file_id = "11m7tX2xCavCM_cij69UaSVijFuFQbveM"
            download(f"https://drive.google.com/uc?id={file_id}", "matches.xlsx", quiet=False)
            
            status_placeholder.write("Bahisler kontrol ediliyor...")
            time.sleep(0.1)
            excel_columns_basic = [
                "Tarih", "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY SKOR", "MS SKOR",
                "EV KORNER", "DEP KORNER"
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
            time.sleep(0.1)
            data = pd.read_excel("matches.xlsx", sheet_name="Bahisler", usecols=available_columns, dtype=str)
            
            if "Tarih" not in data.columns:
                st.error("Hata: 'Tarih' sütunu bulunamadı. Lütfen matches.xlsx dosyasını kontrol edin.")
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
            for col in ["EV KORNER", "DEP KORNER"]:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce')
            st.session_state.data = data
            
            status_placeholder.write("Bülten verisi çekiliyor...")
            time.sleep(0.1)
            match_list, raw_data = fetch_api_data()
            if not match_list:
                st.error(f"Bülten verisi alınamadı. Hata: {raw_data.get('error', 'Bilinmeyen hata')}")
                st.stop()
            
            api_df = process_api_data(match_list, raw_data, start_datetime, end_datetime)
            
            # Debug logları
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
            
            columns = ["Benzerlik (%)", "İY/MS", "Oran Sayısı", "Korner Ort.", "Saat", "Tarih", "Lig Adı", "Ev Sahibi Takım", "Deplasman Takım", "IY KG ORAN", "IY SKOR", "MS SKOR"]
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
