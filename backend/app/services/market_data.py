import asyncio
import re
import httpx
import pandas as pd
from typing import Optional
from app.config import settings
from app.services.alert_service import (
    get_cached_price,
    cache_price,
    get_stale_price,
    cache_stale_price,
)

BASE_URL = "https://api.twelvedata.com"


def _scrub(err) -> str:
    """Error text that is safe to log: httpx puts the full request URL
    (including ?apikey=...) in its messages, so strip the key out."""
    return re.sub(r"apikey=[^&\s'\"]+", "apikey=***", str(err))

# Map our pair format to Twelve Data format
PAIR_MAP = {
    "EUR/USD": "EUR/USD",
    "GBP/USD": "GBP/USD",
    "USD/JPY": "USD/JPY",
    "USD/CHF": "USD/CHF",
    "AUD/USD": "AUD/USD",
    "USD/CAD": "USD/CAD",
    "XAU/USD": "XAU/USD",
}

# Map timeframe labels to Twelve Data interval strings
TIMEFRAME_MAP = {
    "M15": "15min",
    "H1":  "1h",
    "H4":  "4h",
    "D1":  "1day",
}


async def fetch_ohlcv(
    pair: str,
    timeframe: str = "H1",
    limit: int = 200,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV candlestick data from Twelve Data API.
    Returns a pandas DataFrame with columns: open, high, low, close, volume
    Index is datetime.
    """
    symbol = PAIR_MAP.get(pair, pair)
    interval = TIMEFRAME_MAP.get(timeframe, "1h")

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": limit,
        "apikey": settings.TWELVE_DATA_API_KEY,
        "format": "JSON",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(f"{BASE_URL}/time_series", params=params)
            response.raise_for_status()
            data = response.json()

            if "values" not in data:
                print(f"Twelve Data error for {pair}: {data.get('message', 'Unknown error')}")
                return None

            # Build DataFrame
            df = pd.DataFrame(data["values"])
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.set_index("datetime").sort_index()

            # Convert columns to float
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            return df

        except httpx.HTTPError as e:
            print(f"HTTP error fetching {pair}: {_scrub(e)}")
            return None
        except Exception as e:
            print(f"Error fetching {pair}: {_scrub(e)}")
            return None


async def fetch_quote(pair: str) -> Optional[dict]:
    """
    Fetch the latest price quote for a pair.

    Checks the 30s Redis price cache first, so repeat calls for the same
    pair within that window (multiple users, the websocket broadcast
    loop, and /quotes/all all ask for the same pairs) don't each hit
    Twelve Data. On a rate-limit (429) or other failure, falls back to a
    longer-lived "stale" cache (up to 10 min old) instead of returning
    nothing, so the UI still shows a recent price rather than a gap.
    """
    cached = get_cached_price(pair)
    if cached is not None:
        return {"pair": pair, "price": cached, "source": "cache"}

    symbol = PAIR_MAP.get(pair, pair)

    params = {
        "symbol": symbol,
        "apikey": settings.TWELVE_DATA_API_KEY,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{BASE_URL}/price", params=params)
            response.raise_for_status()
            data = response.json()

            if "price" not in data:
                return None

            price = float(data["price"])
            cache_price(pair, price)        # fresh cache, 30s
            cache_stale_price(pair, price)  # fallback cache, 10min

            return {"pair": pair, "price": price, "source": "live"}

        except httpx.HTTPStatusError as e:
            if e.response is not None and e.response.status_code == 429:
                print(f"[MarketData] Rate limited by Twelve Data for {pair} — using stale cache if available")
            else:
                print(f"Error fetching quote for {pair}: {_scrub(e)}")
            stale = get_stale_price(pair)
            if stale is not None:
                return {"pair": pair, "price": stale, "source": "stale"}
            return None
        except Exception as e:
            print(f"Error fetching quote for {pair}: {_scrub(e)}")
            stale = get_stale_price(pair)
            if stale is not None:
                return {"pair": pair, "price": stale, "source": "stale"}
            return None


async def fetch_multiple_quotes(pairs: list) -> dict:
    """
    Fetch latest prices for multiple pairs.

    fetch_quote() is cache-aware, so pairs already cached from another
    request resolve instantly with no API call. For pairs that do need a
    live fetch, calls are staggered slightly so a burst across several
    uncached pairs (e.g. right after the cache expires) doesn't itself
    trip Twelve Data's rate limit.
    """
    results = {}
    for i, pair in enumerate(pairs):
        if i > 0:
            await asyncio.sleep(0.25)
        quote = await fetch_quote(pair)
        if quote:
            results[pair] = quote
    return results