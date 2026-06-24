from fastapi import APIRouter, Depends, HTTPException, Query
from app.config import settings
from app.services.market_data import fetch_ohlcv, fetch_quote, fetch_multiple_quotes
from app.services.indicator_engine import compute_all_indicators
from app.services.alert_service import cache_price, get_cached_price
from app.middleware.auth_middleware import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/market", tags=["Market Data"])


@router.get("/pairs")
def get_supported_pairs(current_user: User = Depends(get_current_user)):
    """Return list of all supported trading pairs."""
    return {
        "pairs": settings.SUPPORTED_PAIRS,
        "watchlist": current_user.preferred_pairs,
    }


@router.get("/{pair}/quote")
async def get_quote(
    pair: str,
    current_user: User = Depends(get_current_user),
):
    """Get latest price for a pair. Checks Redis cache first."""
    pair = pair.upper().replace("-", "/")

    # Check cache first
    cached = get_cached_price(pair)
    if cached:
        return {"pair": pair, "price": cached, "source": "cache"}

    # Fetch from Twelve Data
    quote = await fetch_quote(pair)
    if not quote:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {pair}")

    # Cache it
    cache_price(pair, quote["price"])

    return {**quote, "source": "live"}


@router.get("/quotes/all")
async def get_all_quotes(current_user: User = Depends(get_current_user)):
    """Get latest prices for all pairs in user's watchlist."""
    pairs = current_user.preferred_pairs or settings.SUPPORTED_PAIRS
    quotes = await fetch_multiple_quotes(pairs)
    return {"quotes": quotes}


@router.get("/{pair}/ohlcv")
async def get_ohlcv(
    pair: str,
    tf: str = Query(default="H1", description="Timeframe: M15, H1, H4, D1"),
    limit: int = Query(default=200, ge=50, le=500),
    current_user: User = Depends(get_current_user),
):
    """Get OHLCV candlestick data for charting."""
    pair = pair.upper().replace("-", "/")

    df = await fetch_ohlcv(pair, tf, limit)
    if df is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not fetch OHLCV data for {pair} on {tf}",
        )

    # Convert to list of dicts for JSON response
    candles = []
    for idx, row in df.iterrows():
        candles.append({
            "time": int(idx.timestamp()),
            "open": round(float(row["open"]), 5),
            "high": round(float(row["high"]), 5),
            "low": round(float(row["low"]), 5),
            "close": round(float(row["close"]), 5),
            "volume": int(row.get("volume", 0)),
        })

    return {
        "pair": pair,
        "timeframe": tf,
        "candles": candles,
        "count": len(candles),
    }


@router.get("/{pair}/indicators")
async def get_indicators(
    pair: str,
    tf: str = Query(default="H1"),
    current_user: User = Depends(get_current_user),
):
    """Get computed technical indicators for a pair."""
    pair = pair.upper().replace("-", "/")

    df = await fetch_ohlcv(pair, tf, 200)
    if df is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not fetch data for {pair}",
        )

    indicators = compute_all_indicators(df)
    if not indicators:
        raise HTTPException(
            status_code=422,
            detail="Not enough data to compute indicators.",
        )

    # Cache the price
    cache_price(pair, indicators["current_price"])

    return {
        "pair": pair,
        "timeframe": tf,
        "indicators": indicators,
    }


@router.get("/{pair}/support-resistance")
async def get_support_resistance(
    pair: str,
    tf: str = Query(default="H1"),
    current_user: User = Depends(get_current_user),
):
    """Get support and resistance zones for a pair."""
    pair = pair.upper().replace("-", "/")

    df = await fetch_ohlcv(pair, tf, 200)
    if df is None:
        raise HTTPException(status_code=404, detail=f"No data for {pair}")

    indicators = compute_all_indicators(df)
    if not indicators:
        raise HTTPException(status_code=422, detail="Not enough data.")

    return {
        "pair": pair,
        "timeframe": tf,
        "support": indicators["support_levels"],
        "resistance": indicators["resistance_levels"],
        "nearest_support": indicators["nearest_support"],
        "nearest_resistance": indicators["nearest_resistance"],
    }