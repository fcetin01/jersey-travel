"""Tek seferlik fiyat karsilastirma araci - ayarlar."""
from datetime import date, timedelta

# --- Paximum (net maliyetimiz) ---
PAXIMUM_BASE_URL = "https://service.paximum.com/v2"
PAXIMUM_AGENCY = "PXM135369"
PAXIMUM_USER = "USR170417"
PAXIMUM_CURRENCY = "USD"      # Paximum'da sadece USD var
PAXIMUM_NATIONALITY = "TR"
PAXIMUM_CULTURE = "tr-TR"

# --- MakCorps (Booking/OTA fiyatlari) ---
MAKCORPS_BASE_URL = "https://api.makcorps.com"

# --- Arama kriterleri ---
ADULTS = 2
ROOMS = 1

# --- Satis marji: net fiyatin uzerine koydugumuz oran ---
MARGIN = 0.10                 # %10

# --- Kredi butcesi ---
CREDIT_BUDGET = 30            # ucretsiz deneme kotasi (yaklasik)
SLEEP_BETWEEN_CALLS = 1.0     # saniye

# --- Tarih senaryolari (sirasi onemli, --dates N ilk N tanesini calistirir) ---
DATE_SCENARIOS = [
    {"key": "yakin", "label": "Yakin tarih", "days_ahead": 21,  "nights": 3},
    {"key": "orta",  "label": "Orta vade",   "days_ahead": 60,  "nights": 3},
    {"key": "uzak",  "label": "Uzak",        "days_ahead": 120, "nights": 3},
]

# Paximum otel adi eslestirme esigi (0-1, difflib oran)
NAME_MATCH_THRESHOLD = 0.60


def build_scenarios(count=1, today=None):
    """Ilk `count` tarih senaryosunu somut checkin/checkout'a cevirir."""
    today = today or date.today()
    out = []
    for sc in DATE_SCENARIOS[:count]:
        ci = today + timedelta(days=sc["days_ahead"])
        co = ci + timedelta(days=sc["nights"])
        out.append({
            "key": sc["key"], "label": sc["label"], "nights": sc["nights"],
            "checkin": ci.isoformat(), "checkout": co.isoformat(),
        })
    return out
