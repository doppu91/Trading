"""Real-source signal layer enhancers — replace deterministic placeholders.

Sentiment: Google News RSS scrape (no API key needed) + simple polarity.
FII flow:  Moneycontrol FII/DII daily data scrape.
GEX:       NSE option chain via nsepython for Nifty/BankNifty.
"""
from __future__ import annotations
import logging
import re
from datetime import datetime, timezone, timedelta
import httpx

logger = logging.getLogger(__name__)

POSITIVE_TERMS = {"surge", "rally", "jumps", "soars", "gain", "gains", "buy", "upgrade", "outperform", "beats", "record high", "growth", "bullish", "strong"}
NEGATIVE_TERMS = {"plunge", "drops", "fall", "falls", "crash", "miss", "downgrade", "underperform", "losses", "bearish", "decline", "warning", "investigation", "fraud"}

_news_cache: dict[str, dict] = {}
_fii_cache: dict = {"ts": None, "data": None}
NEWS_TTL = 1800   # 30 min
FII_TTL = 3600    # 1 hour


def _polarity(text: str) -> int:
    t = text.lower()
    pos = sum(1 for w in POSITIVE_TERMS if w in t)
    neg = sum(1 for w in NEGATIVE_TERMS if w in t)
    return pos - neg


async def fetch_sentiment(symbol: str) -> dict:
    """Google News RSS scrape. Returns {score, articles_count, polarity_sum}."""
    now = datetime.now(timezone.utc)
    cached = _news_cache.get(symbol)
    if cached and (now - cached["ts"]).total_seconds() < NEWS_TTL:
        return cached["data"]

    query = f"{symbol} NSE stock"
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        items = re.findall(r"<title>([^<]+)</title>", r.text)
        items = [t for t in items if "Google News" not in t][:15]
        polarity_sum = sum(_polarity(t) for t in items)
        # Map to 0..1 score; centred at 0.5
        score = max(0.0, min(1.0, 0.5 + polarity_sum * 0.04))
        data = {
            "score": round(score, 3),
            "articles_count": len(items),
            "polarity_sum": polarity_sum,
            "source": "google_news_rss",
            "headlines_sample": items[:3],
        }
    except Exception as e:
        logger.debug(f"sentiment fail {symbol}: {e}")
        data = {"score": 0.5, "articles_count": 0, "polarity_sum": 0, "source": "fallback"}

    _news_cache[symbol] = {"ts": now, "data": data}
    return data


async def fetch_fii_flow() -> dict:
    """Moneycontrol FII/DII daily data scrape. Returns {score, fii_net, dii_net, date}."""
    now = datetime.now(timezone.utc)
    if _fii_cache["ts"] and (now - _fii_cache["ts"]).total_seconds() < FII_TTL:
        return _fii_cache["data"]

    url = "https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/index.php"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
        # Crude: find first table data rows; values have ₹ + comma
        nums = re.findall(r"-?[\d,]+\.\d{2}", r.text)
        fii_net = float(nums[2].replace(",", "")) if len(nums) >= 3 else 0.0
        dii_net = float(nums[5].replace(",", "")) if len(nums) >= 6 else 0.0
        # Score: positive FII+DII = bullish
        net = fii_net + dii_net
        score = max(0.0, min(1.0, 0.5 + net / 5000))  # ±5000 cr saturates
        data = {
            "score": round(score, 3),
            "fii_net_cr": round(fii_net, 2),
            "dii_net_cr": round(dii_net, 2),
            "combined_net_cr": round(net, 2),
            "source": "moneycontrol",
            "date": now.strftime("%Y-%m-%d"),
        }
    except Exception as e:
        logger.debug(f"fii fetch fail: {e}")
        data = {"score": 0.5, "fii_net_cr": 0, "dii_net_cr": 0, "source": "fallback"}

    _fii_cache["ts"] = now
    _fii_cache["data"] = data
    return data


async def fetch_gex(index: str = "NIFTY") -> dict:
    """Gamma exposure proxy from NSE option chain. Warms cookies first."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.nseindia.com/option-chain",
        "Connection": "keep-alive",
    }
    url = f"https://www.nseindia.com/api/option-chain-indices?symbol={index}"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            # Cookie warm-up sequence
            await client.get("https://www.nseindia.com/")
            await client.get("https://www.nseindia.com/option-chain")
            # Now the actual API
            r = await client.get(url)
            if r.status_code != 200:
                # Retry once after a tiny delay
                import asyncio as _a; await _a.sleep(1)
                r = await client.get(url)
            data = r.json()
        records = data.get("records", {}).get("data", [])
        ce_oi = sum(r["CE"]["openInterest"] for r in records if "CE" in r)
        pe_oi = sum(r["PE"]["openInterest"] for r in records if "PE" in r)
        pcr = pe_oi / ce_oi if ce_oi else 1.0
        score = max(0.0, min(1.0, (pcr - 0.6) / 1.2))
        return {
            "score": round(score, 3),
            "pcr": round(pcr, 3),
            "call_oi": int(ce_oi),
            "put_oi": int(pe_oi),
            "source": "nse_option_chain",
        }
    except Exception as e:
        logger.debug(f"gex fail: {e}")
        return {"score": 0.5, "pcr": None, "source": "fallback", "error": str(e)[:200]}
