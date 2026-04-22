"""Global trading configuration — sourced from env and DB overrides."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# === Capital & risk ===
CAPITAL = float(os.environ.get("TRADING_CAPITAL", 600000))
MAX_DAILY_LOSS = float(os.environ.get("MAX_DAILY_LOSS", 1000))
RISK_PER_TRADE_PCT = 0.015  # 1.5% per trade
TARGET_GROSS_DAILY = float(os.environ.get("TARGET_GROSS_DAILY", 4500))
TARGET_NET_DAILY = 4000
MAX_POSITIONS = 2
SIGNAL_THRESHOLD = 0.68
INDIA_VIX_MAX = 20.0
CHARGES_PER_TRADE = 100  # estimated round trip

# === Paper mode ===
PAPER_MODE = os.environ.get("PAPER_MODE", "True").lower() == "true"

# === Watchlist / instruments ===
INSTRUMENT_MAP = {
    "RELIANCE":   {"token": "NSE_EQ|INE002A01018", "yf": "RELIANCE.NS"},
    "HDFCBANK":   {"token": "NSE_EQ|INE040A01034", "yf": "HDFCBANK.NS"},
    "INFY":       {"token": "NSE_EQ|INE009A01021", "yf": "INFY.NS"},
    "ICICIBANK":  {"token": "NSE_EQ|INE090A01021", "yf": "ICICIBANK.NS"},
    "TCS":        {"token": "NSE_EQ|INE467B01029", "yf": "TCS.NS"},
    "KOTAKBANK":  {"token": "NSE_EQ|INE237A01028", "yf": "KOTAKBANK.NS"},
    "LT":         {"token": "NSE_EQ|INE018A01030", "yf": "LT.NS"},
    "AXISBANK":   {"token": "NSE_EQ|INE238A01034", "yf": "AXISBANK.NS"},
    "SBIN":       {"token": "NSE_EQ|INE062A01020", "yf": "SBIN.NS"},
    "BAJFINANCE": {"token": "NSE_EQ|INE296A01024", "yf": "BAJFINANCE.NS"},
}
WATCHLIST = list(INSTRUMENT_MAP.keys())

# === Signal weights ===
WEIGHTS = {
    "technical":   0.40,
    "sentiment":   0.15,
    "fii_flow":    0.15,
    "gex":         0.20,
    "global_cue":  0.10,
}

# === Schedule (IST) ===
SCHEDULE = {
    "token_refresh":  "08:00",
    "global_scan":    "08:30",
    "regime_check":   "08:45",
    "morning_brief":  "08:59",
    "market_open":    "09:15",
    "market_close":   "15:20",
    "eod_summary":    "15:30",
}

# === Credentials (nullable until user configures) ===
UPSTOX_API_KEY = os.environ.get("UPSTOX_API_KEY", "")
UPSTOX_API_SECRET = os.environ.get("UPSTOX_API_SECRET", "")
UPSTOX_REDIRECT_URI = os.environ.get("UPSTOX_REDIRECT_URI", "https://127.0.0.1")
UPSTOX_ACCESS_TOKEN = os.environ.get("UPSTOX_ACCESS_TOKEN", "")
UPSTOX_TOTP_SECRET = os.environ.get("UPSTOX_TOTP_SECRET", "")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
