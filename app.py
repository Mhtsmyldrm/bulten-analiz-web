import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime, timedelta, timezone
import math
from collections import Counter

# ============================================
# CONFIG - Varsayılan Drive Linkleri (kullanıcı değiştirilebilir)
# ============================================
DEFAULT_LEAGUE_JSON_URL = "https://drive.google.com/file/d/1L8HA_emD92BJSuCn-P9GJF-hH55nIKE7/view?usp=drive_link"
DEFAULT_MTID_JSON_URL   = "https://drive.google.com/file/d/1N1PjFla683BYTAdzVDaajmcnmMB5wiiO/view?usp=drive_link"
DEFAULT_MATCHES_XLSX_URL = "https://docs.google.com/spreadsheets/d/11m7tX2xCavCM_cij69UaSVijFuFQbveM/edit?usp=drive_link&ouid=115238146617756521388&rtpof=true&sd=true"

IST = timezone(timedelta(hours=3))  # Europe/Istanbul sabit ofset (DST olmayan basit yaklaşım)

# ============================================
# Yardımcılar - Google Drive/Sheets indirme
# ============================================
def _extract_drive_id(url: str) -> str:
    """
    Google Drive veya Sheets URL'inden dosya id'sini çıkartır.
    """
    if not isinstance(url, str):
        return ""
    # Drive dosyası: https://drive.google.com/file/d/<ID>/view
    if "drive.google.com/file/d/" in url:
        try:
            return url.split("/file/d/")[1].split("/")[0]
        except Exception:
            return ""
    # Sheets: https://docs.google.com/spreadsheets/d/<ID>/edit
    if "docs.google.com/spreadsheets/d/" in url:
        try:
            return url.split("/spreadsheets/d/")[1].split("/")[0]
        except Exception:
            return ""
    return ""

def _download_json_from_drive(url: str) -> dict:
    """
    Paylaşımlı Google Drive (veya docs) linkinden JSON döndürür.
    """
    file_id = _extract_drive_id(url)
    if not file_id:
        raise ValueError("Geçersiz JSON linki veya ID bulunamadı.")
    # Drive raw indir
    raw = f"https://drive.google.com/uc?id={file_id}"
    r = requests.get(raw, timeout=30)
    r.raise_for_status()
    return r.json()

def _download_sheet_as_excel_df(url: str) -> pd.DataFrame:
    """
    Google Sheets linkini .xlsx olarak export edip DataFrame döndürür.
    """
    file_id = _extract_drive_id(url)
    if not file_id:
        raise ValueError("Geçersiz Sheets/Excel linki veya ID bulunamadı.")
    export = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    r = requests.get(export, timeout=60)
    r.raise_for_status()
    bio = BytesIO(r.content)
    df = pd.read_excel(bio)
    return df

# ============================================
# JSON Mapping'leri yükle ve ters mapping kur
# ============================================
@st.cache_data(show_spinner=False)
def load_mappings(league_url: str, mtid_url: str):
    league_data = _download_json_from_drive(league_url)
    # keys int olabilir
    league_mapping = {}
    for k, v in league_data.items():
        try:
            league_mapping[int(k)] = v
        except Exception:
            pass

    mtid_data = _download_json_from_drive(mtid_url)
    mtid_mapping = {}
    reverse_mapping = {}  # "Maç Sonucu 1" -> {"mtid": 1, "sov": None, "oca_key": "1"}
    for key_str, value in mtid_data.items():
        # key_str "(268, -1.0)" veya "(1, null)" formatında bekleniyor
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
        # value beklenen: OCA sırasına göre kolon adları listesi
        if not isinstance(value, list):
            continue
        mtid_mapping[(mtid, sov)] = value
        # reverse map
        for i, col_name in enumerate(value, start=1):
            if isinstance(col_name, str):
                reverse_mapping[col_name] = {"mtid": mtid, "sov": sov, "oca_key": str(i)}
    return league_mapping, mtid_mapping, reverse_mapping

# ============================================
# Oran Sütunları (v26 ile aynı set)
# ============================================
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
    "1. Yarı Sonucu 1", "1. Yarı Sonucu X", "1. Yarı Sonucu 2"
}

IMPORTANT_MARKETS = {
    "0,5 Alt/Üst Alt", "0,5 Alt/Üst Üst",
    "1,5 Alt/Üst Alt", "1,5 Alt/Üst Üst", 
    "3,5 Alt/Üst Alt", "3,5 Alt/Üst Üst",
    "Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2"
}

OTHER_MARKETS = set(excel_columns) - CRITICAL_MARKETS - IMPORTANT_MARKETS

# ============================================
# Benzerlik hesaplama (v26 mantığı)
# ============================================
def calculate_similarity(api_odds: dict, match_odds: dict) -> float:
    """
    API maç oran profili ile arşiv maç oran profili arasındaki benzerlik (0-100).
    - Oranlar olasılığa çevrilir (p=1/odd), 1X2 fair normalize edilir.
    - Kapı: 1X2 benzerlik ≥ 0.85 ve her bacakta (1/X/2) göreli fark ≤ %12.
    - Grup ağırlıkları: High 0.65 / Med 0.25 / Low 0.10.
    - Grup başına kapsam küçültme (shrink): az ölçümle skor şişmesin.
    - Çifte Şans ve O/U merdivenindeki ikiz pazarlar yarım ağırlık (double-count freni).
    - İkili pazarlarda ceza: sim = exp(-C*rel_diff)  (C≈3.5).
    """
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

    def fair_pair(pa, pb):
        if pa is None or pb is None:
            return (None, None)
        s = pa + pb
        if s <= 0:
            return (None, None)
        return (pa / s, pb / s)

    def fair_trio_from_odds(odds_dict, k1, kx, k2):
        p1, px, p2 = prob(odds_dict.get(k1)), prob(odds_dict.get(kx)), prob(odds_dict.get(k2))
        if None in (p1, px, p2):
            return None
        s = p1 + px + p2
        if s <= 0:
            return None
        return (p1 / s, px / s, p2 / s)

    def hellinger(p, q):
        # 3-bacak için Hellinger benzerliği
        return max(0.0, 1.0 - (math.sqrt(
            (math.sqrt(p[0]) - math.sqrt(q[0]))**2 +
            (math.sqrt(p[1]) - math.sqrt(q[1]))**2 +
            (math.sqrt(p[2]) - math.sqrt(q[2]))**2
        ) / math.sqrt(2.0)))

    def rel_diff(pa, pb):
        # |a-b| / mean(a,b)
        if pa is None or pb is None or pa <= 0 or pb <= 0:
            return None
        return abs(pa - pb) / ((pa + pb) / 2.0)

    def bin_sim(key):
        # ikili pazar: olasılıklarda göreli farkı cezalandır
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
    O25U, O25A = "2,5 Alt/Üst Alt", "2,5 Alt/Üst Üst"

    # 1) 1X2 fair normalize & gate
    api_ms   = fair_trio_from_odds(api_odds, MS1, MSX, MS2)
    match_ms = fair_trio_from_odds(match_odds, MS1, MSX, MS2)
    if not api_ms or not match_ms:
        return 0.0

    base_sim = hellinger(api_ms, match_ms)
    if base_sim < 0.85:
        return base_sim * 100.0  # erken düşük skor

    # bacak başı göreli fark şartı
    diffs_ok = True
    for a, b in zip(api_ms, match_ms):
        d = rel_diff(a, b)
        if d is None or d > 0.12:
            diffs_ok = False
            break
    if not diffs_ok:
        return base_sim * 100.0

    # 2) Gruplar
    high_list = []
    # 1X2 üçlü
    high_list.append(("1X2", base_sim, 1.0))
    # KG (tam)
    s = bin_sim(KG_V)
    if s is not None: high_list.append((KG_V, s, 1.0))
    s = bin_sim(KG_Y)
    if s is not None: high_list.append((KG_Y, s, 1.0))
    # O25 (tam)
    s = bin_sim(O25U)
    if s is not None: high_list.append((O25U, s, 1.0))
    s = bin_sim(O25A)
    if s is not None: high_list.append((O25A, s, 1.0))
    # Çifte Şans (yarım)
    for k in ("Çifte Şans 1 veya X", "Çifte Şans 1 veya 2", "Çifte Şans X veya 2"):
        s = bin_sim(k)
        if s is not None:
            high_list.append((k, s, 0.5))

    # AH (-1,0) ve (1,0)
    for k in ("Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2",
              "Handikaplı Maç Sonucu (1,0) 1",  "Handikaplı Maç Sonucu (1,0) X",  "Handikaplı Maç Sonucu (1,0) 2"):
        s = bin_sim(k)
        if s is not None:
            high_list.append((k, s, 1.0))

    # Medium: 1. yarı 1X2 + O/U merdiven temsilcileri + 2. yarı 1X2 + gol aralıkları
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
    ]
    med_list = []
    for k in MED_KEYS:
        s = bin_sim(k)
        if s is not None:
            # O/U merdiveninde ikizleri yarım ağırlık say (yakın eş pazarlar)
            w = 0.5 if "Alt/Üst" in k else 1.0
            med_list.append((k, s, w))

    # Low: kalan pazarlar
    low_list = []
    for k in OTHER_MARKETS:
        s = bin_sim(k)
        if s is not None:
            low_list.append((k, s, 1.0))

    # 3) Grup skorları (shrink)
    def group_score(items):
        if not items:
            return None
        sims = [s for _, s, _ in items]
        ws   = [w for _, _, w in items]
        # shrink: az öğede 1.0'a şişmesin
        shrink = min(1.0, (sum(ws) / (len(items) + 2.0)))
        return (sum(s*w for s,w in zip(sims, ws)) / sum(ws)) * shrink

    high_sim = group_score(high_list)
    med_sim  = group_score(med_list)
    low_sim  = group_score(low_list)

    # 4) Ağırlıklı birleşim
    W_HIGH, W_MED, W_LOW = 0.65, 0.25, 0.10
    total, wsum = 0.0, 0.0
    for sim, w in ((high_sim, W_HIGH), (med_sim, W_MED), (low_sim, W_LOW)):
        if sim is not None:
            total += sim * w
            wsum  += w
    if wsum == 0:
        return base_sim * 100.0
    score = total / wsum

    # 5) Anchor kontrolü
    anchors = 0
    if have(MS1, MSX, MS2): anchors += 1
    if have(KG_V, KG_Y):    anchors += 1
    if have(O25U, O25A):    anchors += 1
    ah_has = any(k in match_odds for k in (
        "Handikaplı Maç Sonucu (-1,0) 1", "Handikaplı Maç Sonucu (-1,0) X", "Handikaplı Maç Sonucu (-1,0) 2",
        "Handikaplı Maç Sonucu (1,0) 1",  "Handikaplı Maç Sonucu (1,0) X",  "Handikaplı Maç Sonucu (1,0) 2",
    ))
    if ah_has:
        anchors += 1
    if anchors < 2:
        score = min(score, 0.85)

    return float(score * 100.0)

# ============================================
# Kalite filtresi (v26)
# ============================================
def quality_filter(api_odds: dict, data_odds: dict) -> bool:
    api_cnt  = sum(1 for col in excel_columns if col in api_odds and pd.notna(api_odds[col]))
    data_cnt = sum(1 for col in excel_columns if col in data_odds and pd.notna(data_odds[col]))
    if data_cnt < api_cnt * 0.7:
        return False
    critical_count = sum(1 for m in CRITICAL_MARKETS if m in data_odds and pd.notna(data_odds[m]))
    if critical_count < max(1, int(len(CRITICAL_MARKETS) * 0.5)):  # en az yarısı
        return False
    return True

# ============================================
# V26 tarzı Prediction kuralları (MTID/SOV/oca_key ters mapping ile)
# ============================================
def _parse_score(score_text: str):
    try:
        a, b = score_text.strip().split("-")
        return int(a), int(b)
    except Exception:
        return None, None

def build_prediction_rules():
    """
    Her kural sadece 'column_name' ve 'func' taşır.
    MTID/SOV/oca_key bilgisi JSON reverse_mapping'den bulunur.
    """
    rules = {
        "Maç Sonucu 1": {"func": lambda row: (lambda h,a: h>a)(*_parse_score(row.get("MS SKOR","")) )},
        "Maç Sonucu X": {"func": lambda row: (lambda h,a: h==a)(*_parse_score(row.get("MS SKOR","")) )},
        "Maç Sonucu 2": {"func": lambda row: (lambda h,a: h<a)(*_parse_score(row.get("MS SKOR","")) )},

        "1. Yarı Sonucu 1": {"func": lambda row: (lambda h,a: h>a)(*_parse_score(row.get("IY SKOR","")) )},
        "1. Yarı Sonucu X": {"func": lambda row: (lambda h,a: h==a)(*_parse_score(row.get("IY SKOR","")) )},
        "1. Yarı Sonucu 2": {"func": lambda row: (lambda h,a: h<a)(*_parse_score(row.get("IY SKOR","")) )},

        "2,5 Alt/Üst Alt": {"func": lambda row: (lambda h,a: (h+a) <= 2)(*_parse_score(row.get("MS SKOR","")) )},
        "2,5 Alt/Üst Üst": {"func": lambda row: (lambda h,a: (h+a) >= 3)(*_parse_score(row.get("MS SKOR","")) )},

        "Karşılıklı Gol Var": {"func": lambda row: (lambda h,a: (h>0 and a>0))(*_parse_score(row.get("MS SKOR","")) )},
        "Karşılıklı Gol Yok": {"func": lambda row: (lambda h,a: (h==0 or a==0))(*_parse_score(row.get("MS SKOR","")) )},

        # Çifte Şans örnekleri
        "Çifte Şans 1 veya X": {"func": lambda row: (lambda h,a: h>=a)(*_parse_score(row.get("MS SKOR","")) )},
        "Çifte Şans 1 veya 2": {"func": lambda row: (lambda h,a: h!=a)(*_parse_score(row.get("MS SKOR","")) )},
        "Çifte Şans X veya 2": {"func": lambda row: (lambda h,a: h<=a)(*_parse_score(row.get("MS SKOR","")) )},

        # Handikap (-1,0): ev sahibi 1 gol eksik başlar
        "Handikaplı Maç Sonucu (-1,0) 1": {"func": lambda row: (lambda h,a: (h - 1) > a)(*_parse_score(row.get("MS SKOR","")) )},
        "Handikaplı Maç Sonucu (-1,0) X": {"func": lambda row: (lambda h,a: (h - 1) == a)(*_parse_score(row.get("MS SKOR","")) )},
        "Handikaplı Maç Sonucu (-1,0) 2": {"func": lambda row: (lambda h,a: (h - 1) < a)(*_parse_score(row.get("MS SKOR","")) )},

        # Handikap (1,0): ev sahibi 1 gol avantajlı başlar
        "Handikaplı Maç Sonucu (1,0) 1": {"func": lambda row: (lambda h,a: (h + 1) > a)(*_parse_score(row.get("MS SKOR","")) )},
        "Handikaplı Maç Sonucu (1,0) X": {"func": lambda row: (lambda h,a: (h + 1) == a)(*_parse_score(row.get("MS SKOR","")) )},
        "Handikaplı Maç Sonucu (1,0) 2": {"func": lambda row: (lambda h,a: (h + 1) < a)(*_parse_score(row.get("MS SKOR","")) )},
    }
    return rules

# ============================================
# Veri kaynakları
# ============================================
@st.cache_data(show_spinner=False)
def load_matches_excel(url: str) -> pd.DataFrame:
    df = _download_sheet_as_excel_df(url)
    # Temizlik: odds kolonlarını numerik yap
    for col in excel_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # Standart kolon isimleri varsa bırak
    return df

@st.cache_data(show_spinner=False)
def fetch_api_data(league_mapping: dict, mtid_mapping: dict):
    """
    Nesine bülten delta API'den veri çek ve mtid_mapping'e göre oran kolonlarını doldur.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Referer": "https://www.nesine.com/",
        "Accept": "application/json, text/plain, */*",
    }
    url = "https://bulten.nesine.com/api/bulten/getprebultendelta?marketVersion=1716908400&eventVersion=1716908400"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    match_list = data.get("Data", {}).get("EventList", [])
    out_rows = []

    for m in match_list:
        try:
            match_date = m.get("D", "")
            match_time = m.get("T", "")
            if not (match_date and match_time):
                continue
            match_dt = datetime.strptime(f"{match_date} {match_time}", "%d.%m.%Y %H:%M").replace(tzinfo=IST)

            league_code = m.get("LC", None)
            league_name = league_mapping.get(int(league_code)) if league_code is not None else str(league_code)

            base = {
                "Saat": match_time,
                "Tarih": match_date,
                "Ev Sahibi Takım": m.get("HN", ""),
                "Deplasman Takım": m.get("AN", ""),
                "Lig Adı": league_name if league_name else "",
                "match_datetime": match_dt,
                "MA": m.get("MA", []),  # marketler
            }
            # Oran kolonlarını boş ekle
            for col in excel_columns:
                base[col] = np.nan

            # MTID/SOV -> kolon eşleme
            for market in m.get("MA", []):
                mtid = market.get("MTID")
                sov  = market.get("SOV", None)
                try:
                    sov_key = None if sov is None else float(sov)
                except Exception:
                    sov_key = None
                key = (int(mtid), sov_key) if mtid is not None else None
                if key and key in mtid_mapping:
                    col_names = mtid_mapping[key]  # OCA sırası
                    oca_list = market.get("OCA", [])
                    for idx, col_name in enumerate(col_names, start=1):
                        # OCA içinden N == idx olanın O (oran) değerini bul
                        val = None
                        for oca in oca_list:
                            if str(oca.get("N")) == str(idx):
                                val = oca.get("O")
                                break
                        if col_name in base:
                            try:
                                base[col_name] = float(val) if val not in (None, "",) else np.nan
                            except Exception:
                                base[col_name] = np.nan
            out_rows.append(base)
        except Exception:
            continue

    api_df = pd.DataFrame(out_rows)
    return api_df

# ============================================
# Benzer arama
# ============================================
def build_odds_row_from_dfrow(row: pd.Series) -> dict:
    return {col: row[col] for col in excel_columns if col in row and pd.notna(row[col])}

def find_similar_matches(api_row: pd.Series, matches_df: pd.DataFrame, min_candidates: int = 10, top_k: int = 25):
    api_odds = build_odds_row_from_dfrow(api_row)
    if not api_odds:
        return []

    # adaylar: ilgili lig öncelikli (varsa), sonra tüm ligler
    if "Lig Adı" in api_row and pd.notna(api_row["Lig Adı"]):
        same_league = matches_df[matches_df["Lig Adı"] == api_row["Lig Adı"]]
    else:
        same_league = pd.DataFrame(columns=matches_df.columns)

    others = matches_df if same_league.empty else matches_df[matches_df["Lig Adı"] != api_row["Lig Adı"]]
    candidates = pd.concat([same_league, others], ignore_index=True)

    results = []
    for _, drow in candidates.iterrows():
        data_odds = build_odds_row_from_dfrow(drow)
        if not data_odds:
            continue
        if not quality_filter(api_odds, data_odds):
            continue
        sim = calculate_similarity(api_odds, data_odds)
        if sim <= 0:
            continue
        results.append({
            "similarity": sim,
            "row": drow
        })
        if len(results) >= 5000:  # güvenlik
            break

    if not results:
        return []

    # benzerlik sıralı top_k
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]

# ============================================
# Skor Tahmini & Genel Tahmin (v26 mantığı sadeleşmiş)
# ============================================
def predict_scores_and_markets(api_row: pd.Series, similars, reverse_mapping: dict, min_majority_ratio=0.65, pred_threshold=80.0):
    """
    similars: [{"similarity": float, "row": Series}, ...]
    Döndürür: predicted_iy, predicted_ms, predictions_text(list[str])
    """
    if not similars:
        return "", "", []

    # 1) Skor modları
    ms_scores = [s["row"].get("MS SKOR", "") for s in similars if str(s["row"].get("MS SKOR","")).strip()]
    iy_scores = [s["row"].get("IY SKOR", "") for s in similars if str(s["row"].get("IY SKOR","")).strip()]

    def majority(scores):
        if not scores:
            return ""
        counts = Counter(scores)
        score, count = counts.most_common(1)[0]
        if count / max(1, len(scores)) >= min_majority_ratio:
            return score
        return ""

    pred_ms = majority(ms_scores)
    pred_iy = majority(iy_scores)

    # 2) Prediction Criteria
    rules = build_prediction_rules()
    predictions = []
    total = len(similars)

    # API'de MTID/SOV mevcut mu ve oran çek?
    def find_market_odds(api_row_local, mtid, sov, oca_key):
        for market in api_row_local.get("MA", []):
            if market.get("MTID") != mtid:
                continue
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

        # API'de bu market var mı?
        market_available = any(
            (mrk.get("MTID") == mtid) and ((sov is None) or (str(mrk.get("SOV")) == str(sov)))
            for mrk in api_row.get("MA", [])
        )
        if not market_available:
            continue

        # yüzdelik
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

# ============================================
# UI & Akış
# ============================================
st.set_page_config(page_title="Bülten Analiz (v26 mantığı)", layout="wide")

st.title("Bülten Analiz – v26 benzerlik & tahmin")

with st.sidebar:
    st.subheader("Veri Kaynakları")
    league_url = st.text_input("league_mapping.json URL", DEFAULT_LEAGUE_JSON_URL)
    mtid_url   = st.text_input("mtid_mapping.json URL",   DEFAULT_MTID_JSON_URL)
    excel_url  = st.text_input("matches.xlsx (Google Sheets) URL", DEFAULT_MATCHES_XLSX_URL)

    st.subheader("Filtreler")
    today = datetime.now(IST).date()
    start_date = st.date_input("Başlangıç Tarihi", today)
    end_date   = st.date_input("Bitiş Tarihi", today + timedelta(days=2))
    start_time = st.time_input("Başlangıç Saati", datetime.now(IST).time())
    end_time   = st.time_input("Bitiş Saati", (datetime.now(IST) + timedelta(hours=6)).time())

    st.subheader("Benzerlik Parametreleri")
    top_k = st.slider("Top-K benzer maç sayısı", 5, 50, 25, step=1)
    majority_ratio = st.slider("Skor tahmini için çoğunluk eşiği (%)", 50, 90, 65, step=5) / 100.0
    pred_threshold = st.slider("Tahmin üretim eşiği (%)", 60, 100, 80, step=5)

# Yüklemeler
try:
    league_mapping, mtid_mapping, reverse_mapping = load_mappings(league_url, mtid_url)
    df_hist = load_matches_excel(excel_url)
except Exception as e:
    st.error(f"Kaynaklar yüklenemedi: {e}")
    st.stop()

# API verisi
api_df = fetch_api_data(league_mapping, mtid_mapping)
if api_df.empty:
    st.warning("API verisi boş döndü.")
    st.stop()

# Tarih/Saat filtre
def to_dt(dmy_str, hm_str):
    try:
        return datetime.strptime(f"{dmy_str} {hm_str}", "%d.%m.%Y %H:%M").replace(tzinfo=IST)
    except Exception:
        return None

start_dt = datetime.combine(start_date, start_time).replace(tzinfo=IST)
end_dt   = datetime.combine(end_date,   end_time).replace(tzinfo=IST)

api_df = api_df[api_df["match_datetime"].between(start_dt, end_dt)].copy()
if api_df.empty:
    st.info("Seçilen aralıkta maç bulunamadı.")
    st.stop()

# Çıktı satırları
output_rows = []
progress = st.progress(0)
for i, (_, api_row) in enumerate(api_df.iterrows(), start=1):
    similars = find_similar_matches(api_row, df_hist, top_k=top_k)
    pred_iy, pred_ms, preds = predict_scores_and_markets(api_row, similars, reverse_mapping, min_majority_ratio=majority_ratio, pred_threshold=pred_threshold)
    similarity_best = max((s["similarity"] for s in similars), default=0.0)

    out = {
        "Benzerlik (%)": round(float(similarity_best), 1),
        "Saat": api_row.get("Saat", ""),
        "Tarih": api_row.get("Tarih", ""),
        "Ev Sahibi Takım": api_row.get("Ev Sahibi Takım", ""),
        "Deplasman Takım": api_row.get("Deplasman Takım", ""),
        "Lig Adı": api_row.get("Lig Adı", ""),
        "IY SKOR": pred_iy,
        "MS SKOR": pred_ms,
        "Tahmin": " | ".join(preds[:2]) if preds else ""
    }
    output_rows.append(out)
    progress.progress(i / len(api_df))

result_df = pd.DataFrame(output_rows)
# Sıralama: yüksek benzerlik
if not result_df.empty:
    result_df.sort_values(by=["Benzerlik (%)", "Tarih", "Saat"], ascending=[False, True, True], inplace=True)
    # Görselleştir
    st.dataframe(result_df.reset_index(drop=True), hide_index=True, use_container_width=True)
else:
    st.info("Çıkış üretilemedi.")
