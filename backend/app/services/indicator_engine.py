import pandas as pd
import numpy as np
from typing import Optional


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def calculate_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict:
    """
    Calculate MACD indicator.
    Returns dict with macd_line, signal_line, histogram.
    """
    ema_fast = calculate_ema(series, fast)
    ema_slow = calculate_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {
        "macd_line": macd_line,
        "signal_line": signal_line,
        "histogram": histogram,
    }


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range.
    Requires DataFrame with high, low, close columns.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.ewm(span=period, adjust=False).mean()
    return atr


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate the Average Directional Index (ADX, Wilder smoothing).

    ADX measures how STRONG a trend is, not which way it points: roughly
    below 20 the market is ranging/sideways, above 25 it is trending.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)

    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)

    alpha = 1.0 / period
    atr_w = true_range.ewm(alpha=alpha, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_w.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_w.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=alpha, adjust=False).mean()
    return adx.fillna(0)


def detect_support_resistance(
    df: pd.DataFrame,
    window: int = 10,
    num_levels: int = 3,
) -> dict:
    """
    Detect support and resistance zones from swing highs and lows.
    Returns dict with support and resistance lists.
    """
    highs = df["high"]
    lows = df["low"]

    # Find swing highs — local maxima
    resistance_levels = []
    for i in range(window, len(highs) - window):
        if highs.iloc[i] == highs.iloc[i - window: i + window].max():
            resistance_levels.append(round(highs.iloc[i], 5))

    # Find swing lows — local minima
    support_levels = []
    for i in range(window, len(lows) - window):
        if lows.iloc[i] == lows.iloc[i - window: i + window].min():
            support_levels.append(round(lows.iloc[i], 5))

    # Remove duplicates and sort
    resistance_levels = sorted(set(resistance_levels), reverse=True)[:num_levels]
    support_levels = sorted(set(support_levels), reverse=False)[:num_levels]

    return {
        "resistance": resistance_levels,
        "support": support_levels,
    }


def get_trend_label(ema20: float, ema50: float, rsi: float) -> str:
    """Return a simple trend label."""
    if ema20 > ema50 and rsi > 50:
        return "BULLISH"
    elif ema20 < ema50 and rsi < 50:
        return "BEARISH"
    return "NEUTRAL"


def get_volatility_label(atr: float, price: float) -> str:
    """Classify volatility relative to price."""
    ratio = (atr / price) * 100
    if ratio < 0.2:
        return "LOW"
    elif ratio < 0.5:
        return "MEDIUM"
    return "HIGH"


def compute_all_indicators(df: pd.DataFrame, include_chart: bool = True) -> Optional[dict]:
    """
    Master function — computes all indicators from OHLCV DataFrame.
    Returns a dict of the latest values ready for AI analysis and API response.
    """
    if df is None or len(df) < 60:
        return None

    close = df["close"]

    # Calculate all indicators
    ema20 = calculate_ema(close, 20)
    ema50 = calculate_ema(close, 50)
    rsi = calculate_rsi(close, 14)
    macd = calculate_macd(close)
    atr = calculate_atr(df, 14)
    sr_zones = detect_support_resistance(df)

    # Get latest values
    latest_close = round(float(close.iloc[-1]), 5)
    latest_ema20 = round(float(ema20.iloc[-1]), 5)
    latest_ema50 = round(float(ema50.iloc[-1]), 5)
    latest_rsi = round(float(rsi.iloc[-1]), 2)
    latest_macd_hist = round(float(macd["histogram"].iloc[-1]), 5)
    latest_atr = round(float(atr.iloc[-1]), 5)

    # EMA slope over last 5 candles
    ema20_slope = round(float(ema20.iloc[-1] - ema20.iloc[-5]), 5)
    ema50_slope = round(float(ema50.iloc[-1] - ema50.iloc[-5]), 5)

    # EMA cross status
    ema_cross = "ABOVE" if latest_ema20 > latest_ema50 else "BELOW"

    # Trend and volatility labels
    trend = get_trend_label(latest_ema20, latest_ema50, latest_rsi)
    volatility = get_volatility_label(latest_atr, latest_close)

    # Nearest support and resistance
    nearest_support = max(
        [s for s in sr_zones["support"] if s < latest_close], default=None
    )
    nearest_resistance = min(
        [r for r in sr_zones["resistance"] if r > latest_close], default=None
    )

    # --- Market-regime measurements (trending vs sideways) ---
    adx = calculate_adx(df, 14)
    latest_adx = round(float(adx.iloc[-1]), 2)
    safe_atr = latest_atr if latest_atr > 0 else 1e-9

    # Distance between the two EMAs, measured in ATRs.
    ema_gap_atr = round(abs(latest_ema20 - latest_ema50) / safe_atr, 3)
    # How far EMA50 moved over the last 10 candles, in ATRs (signed).
    ema50_slope_atr = round(float(ema50.iloc[-1] - ema50.iloc[-11]) / safe_atr, 3)
    # How many times EMA20 crossed EMA50 in the last 30 candles.
    ema_sign = np.sign((ema20 - ema50).iloc[-31:])
    ema_cross_count_30 = int((ema_sign.diff().abs() > 0).sum())
    # Height of the last 20 candles' high-low box, in ATRs.
    range_atr_20 = round(
        float(df["high"].iloc[-20:].max() - df["low"].iloc[-20:].min()) / safe_atr, 2
    )

    # Build series data for charting (last 100 candles)
    chart_data = []
    chart_start = max(0, len(df) - 100) if include_chart else len(df)
    for i in range(chart_start, len(df)):
        chart_data.append({
            "time": int(df.index[i].timestamp()),
            "open": round(float(df["open"].iloc[i]), 5),
            "high": round(float(df["high"].iloc[i]), 5),
            "low": round(float(df["low"].iloc[i]), 5),
            "close": round(float(df["close"].iloc[i]), 5),
            "ema20": round(float(ema20.iloc[i]), 5),
            "ema50": round(float(ema50.iloc[i]), 5),
            "rsi": round(float(rsi.iloc[i]), 2),
            "macd_hist": round(float(macd["histogram"].iloc[i]), 5),
            "atr": round(float(atr.iloc[i]), 5),
        })

    return {
        # Latest snapshot
        "current_price": latest_close,
        "ema20": latest_ema20,
        "ema50": latest_ema50,
        "ema_cross": ema_cross,
        "ema20_slope": ema20_slope,
        "ema50_slope": ema50_slope,
        "rsi": latest_rsi,
        "macd_hist": latest_macd_hist,
        "atr": latest_atr,
        "trend": trend,
        "volatility": volatility,
        "adx": latest_adx,
        "ema_gap_atr": ema_gap_atr,
        "ema50_slope_atr": ema50_slope_atr,
        "ema_cross_count_30": ema_cross_count_30,
        "range_atr_20": range_atr_20,
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
        "support_levels": sr_zones["support"],
        "resistance_levels": sr_zones["resistance"],
        # Chart series
        "chart_data": chart_data,
    }