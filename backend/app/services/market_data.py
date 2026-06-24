import httpx
import pandas as pd
from typing import Optional
from app.config import settings

BASE_URL = "https://api.twelvedata.com"

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
            print(f"HTTP error fetching {pair}: {e}")
            return None
        except Exception as e:
            print(f"Error fetching {pair}: {e}")
            return None


async def fetch_quote(pair: str) -> Optional[dict]:
    """
    Fetch the latest price quote for a pair.
    Returns dict with bid, ask, price, change, change_percent.
    """
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

            return {
                "pair": pair,
                "price": float(data["price"]),
            }

        except Exception as e:
            print(f"Error fetching quote for {pair}: {e}")
            return None


async def fetch_multiple_quotes(pairs: list) -> dict:
    """Fetch latest prices for multiple pairs at once."""
    results = {}
    for pair in pairs:
        quote = await fetch_quote(pair)
        if quote:
            results[pair] = quote
    return results