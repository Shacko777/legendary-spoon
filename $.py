"""
╔══════════════════════════════════════════════════════════════════╗
║   SHACKOBOT  —  Universal Merged Bot  (FINAL)                   ║
║   Signal : SMA 20/50/100/200 ribbon + MACD 12/26/9              ║
║   Filters: BODY · SUPERTREND · CHOP · HTF-MACD(4H) · VWAP      ║
║   Exit   : TP1/TP2 partials + Bybit native trailing              ║
║   Exchange: Bybit Linear Perpetual  (any symbol)                 ║
╠══════════════════════════════════════════════════════════════════╣
║   HOW TO USE                                                     ║
║   1. Change SYMBOL below                                         ║
║   2. Set env vars or paste credentials:                          ║
║        BYBIT_API_KEY  BYBIT_API_SECRET                           ║
║        TELEGRAM_BOT_TOKEN  TELEGRAM_CHAT_ID                      ║
║   3. Set LIVE_TRADING = True when ready                          ║
║   4. Run: python merged_bot_universal_v2.py                      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, sys, time, math, logging, json
import requests
import numpy as np
import pandas as pd
import pandas_ta as ta
from pybit.unified_trading import HTTP

# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION  ← edit only this section
# ══════════════════════════════════════════════════════════════════

SYMBOL       = "BTCUSDT"   # any Bybit linear perpetual
LIVE_TRADING = True        # False = paper (no real orders)
TESTNET      = False

INTERVAL     = "60"        # candle timeframe in minutes
WARMUP_BARS  = 250         # bars needed for SMA-200 warm-up
POLL_SECONDS = 60          # how often to poll (seconds)

# ── Risk / sizing ─────────────────────────────────────────────────
LEVERAGE           = 10
RISK_PCT           = 0.01      # 1% of balance risked per trade
MAX_COLLATERAL_PCT = 0.20      # cap: max 20% of balance as margin

# ── Position management ───────────────────────────────────────────
#
#  Entry  ───► SL @ -5%  ◄── hard stop, full position
#         ───► TP1 @ +10% → close 80%  (SL stays at -5%)
#         ───► TP2 @ +20% → close 10%  (SL → breakeven, trail starts)
#         ───► RIDER 10%  → Bybit native 20% trailing stop
#
#  Trailing example:
#    Price +40% → SL at +20%   (best - 20% gap)
#    Price +120% → SL at +100% (best - 20% gap, always)
#
SL_PCT          = 0.005      # 0.5% price move  = -5% leveraged (10x)
TP1_PCT         = 0.01      # 1% price move  = +10% leveraged → close 80%
TP1_CLOSE_PCT   = 0.80      # 80% of original qty closed at TP1
TP2_PCT         = 0.02      # 2% price move  = +20% leveraged → close next 10%
TP2_CLOSE_PCT   = 0.10      # 10% of original qty closed at TP2
RIDER_TRAIL_PCT = 0.02      # 2% price gap   = 20% leveraged trailing gap
                             # activates at TP2 price; trails best price
                             # e.g. price +4% (leveraged +40%) → SL leveraged +20% (gap stays 20%)
                             #      price +12% (leveraged +120%) → SL leveraged +100% (gap stays 20%)

FEE_RATE        = 0.00055   # Bybit taker fee (0.055%)

# ── MACD params ───────────────────────────────────────────────────
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9

# ── Filters  (73.1% WR validated in backtest) ────────────────────
USE_BODY_FILTER     = True   # candle body ≥ 40% of range
USE_SUPERT_FILTER   = True   # Supertrend must agree with direction
USE_CHOP_FILTER     = True   # Choppiness Index < 61.8
USE_HTF_MACD_FILTER = True   # 4H MACD direction must agree
USE_VWAP_FILTER     = True   # price on correct side of VWAP

BODY_MIN_PCT      = 0.40     # minimum body / range ratio
SUPERT_PERIOD     = 10
SUPERT_MULT       = 3.0
CHOP_PERIOD       = 14
CHOP_MAX          = 61.8
VWAP_PERIOD       = 24       # rolling candles for VWAP
HTF_INTERVAL      = "240"    # 4-hour candles for HTF MACD
HTF_BARS          = 200
HTF_MACD_FAST     = 12
HTF_MACD_SLOW     = 26
HTF_MACD_SIG      = 9

# ── Credentials  (env vars recommended) ──────────────────────────
API_KEY    = os.getenv("BYBIT_API_KEY",      "")
API_SECRET = os.getenv("BYBIT_API_SECRET",   "")
TG_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT    = os.getenv("TELEGRAM_CHAT_ID",   "")

# ── Auto-configured (do not edit) ────────────────────────────────
_MIN_QTY    = 0.001
_QTY_STEP   = 0.001
_QTY_PREC   = 3
_PRICE_PREC = 2
_MAX_LEV    = 100.0

_sym        = SYMBOL.lower().replace("usdt", "")
_LOG_FILE   = f"{_sym}_merged.log"
_STATE_FILE = f"{_sym}_merged_state.json"

# ══════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(f"BOT_{SYMBOL[:3].upper()}")

# ══════════════════════════════════════════════════════════════════
#  CLOCK SYNC  (fixes Bybit ErrCode 10002)
# ══════════════════════════════════════════════════════════════════
import time as _tmod
_real_time    = _tmod.time
_clock_offset = 0.0

def _patched_time():
    return _real_time() - _clock_offset

def sync_clock():
    global _clock_offset
    try:
        r = requests.get("https://api.bybit.com/v5/market/time", timeout=5).json()
        server_ms = int(r["result"]["timeNano"]) // 1_000_000
        local_ms  = int(_real_time() * 1000)
        offset_ms = local_ms - server_ms
        _clock_offset = offset_ms / 1000.0
        if abs(offset_ms) > 100:
            _tmod.time = _patched_time
        log.info(f"Clock offset: {offset_ms:+d}ms")
    except Exception as e:
        log.warning(f"Clock sync: {e}")

# ══════════════════════════════════════════════════════════════════
#  TELEGRAM
# ══════════════════════════════════════════════════════════════════
def tg(msg: str):
    if not TG_TOKEN or "YOUR" in TG_TOKEN:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": msg,
                  "parse_mode": "Markdown", "disable_web_page_preview": True},
            timeout=10,
        )
    except Exception as e:
        log.error(f"Telegram: {e}")

# ══════════════════════════════════════════════════════════════════
#  INSTRUMENT SPECS
# ══════════════════════════════════════════════════════════════════
def _dp(s: str) -> int:
    s = s.rstrip("0").rstrip(".")
    return len(s.split(".")[1]) if "." in s else 0

def fetch_and_apply_specs(client: HTTP) -> None:
    global _MIN_QTY, _QTY_STEP, _QTY_PREC, _PRICE_PREC, _MAX_LEV, LEVERAGE
    try:
        info = client.get_instruments_info(category="linear", symbol=SYMBOL)
        sym  = info["result"]["list"][0]
        lot  = sym["lotSizeFilter"]
        pf   = sym["priceFilter"]
        lf   = sym["leverageFilter"]
        _MIN_QTY    = float(lot["minOrderQty"])
        _QTY_STEP   = float(lot["qtyStep"])
        _QTY_PREC   = _dp(lot["qtyStep"])
        _PRICE_PREC = _dp(pf["tickSize"])
        _MAX_LEV    = float(lf["maxLeverage"])
        if LEVERAGE > _MAX_LEV:
            log.warning(f"Leverage {LEVERAGE}x > max {_MAX_LEV}x — capping")
            LEVERAGE = int(_MAX_LEV)
        log.info(f"Specs [{SYMBOL}]: min_qty={_MIN_QTY} step={_QTY_STEP} "
                 f"qty_prec={_QTY_PREC} price_prec={_PRICE_PREC} max_lev={_MAX_LEV}x")
        try:
            price = float(client.get_tickers(
                category="linear", symbol=SYMBOL)["result"]["list"][0]["lastPrice"])
            log.info(f"Min balance for 1 contract: "
                     f"${_MIN_QTY * price / (RISK_PCT * LEVERAGE):.2f} USDT")
        except Exception:
            pass
    except Exception as e:
        log.warning(f"Specs fetch failed ({e}) — using defaults")

# ══════════════════════════════════════════════════════════════════
#  CLIENT
# ══════════════════════════════════════════════════════════════════
def get_client() -> HTTP:
    sync_clock()
    return HTTP(testnet=TESTNET, api_key=API_KEY,
                api_secret=API_SECRET, recv_window=50000)

# ══════════════════════════════════════════════════════════════════
#  DATA  —  1H candles
# ══════════════════════════════════════════════════════════════════
def fetch_candles(client: HTTP, limit: int = 300) -> pd.DataFrame:
    try:
        resp = client.get_kline(
            category="linear", symbol=SYMBOL, interval=INTERVAL, limit=limit)
        df = pd.DataFrame(
            resp["result"]["list"],
            columns=["timestamp","open","high","low","close","volume","turnover"])
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype("int64"), unit="ms")
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df.iloc[:-1]   # drop the forming bar
    except Exception as e:
        log.error(f"fetch_candles: {e}"); return pd.DataFrame()

# ══════════════════════════════════════════════════════════════════
#  DATA  —  4H candles for HTF MACD filter
# ══════════════════════════════════════════════════════════════════
def fetch_htf(client: HTTP) -> pd.DataFrame:
    try:
        resp = client.get_kline(
            category="linear", symbol=SYMBOL,
            interval=HTF_INTERVAL, limit=HTF_BARS)
        df = pd.DataFrame(
            resp["result"]["list"],
            columns=["timestamp","open","high","low","close","volume","turnover"])
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype("int64"), unit="ms")
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df.iloc[:-1]
    except Exception as e:
        log.warning(f"fetch_htf: {e}"); return pd.DataFrame()

# ══════════════════════════════════════════════════════════════════
#  INDICATORS  (1H)
# ══════════════════════════════════════════════════════════════════
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # SMA ribbon
    df["sma20"]  = ta.sma(df["close"], length=20)
    df["sma50"]  = ta.sma(df["close"], length=50)
    df["sma100"] = ta.sma(df["close"], length=100)
    df["sma200"] = ta.sma(df["close"], length=200)
    # MACD
    macd = ta.macd(df["close"], fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
    df["macd"]      = macd[f"MACD_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}"]
    df["macd_sig"]  = macd[f"MACDs_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}"]
    df["histogram"] = macd[f"MACDh_{MACD_FAST}_{MACD_SLOW}_{MACD_SIGNAL}"]
    # Supertrend
    try:
        st = ta.supertrend(df["high"], df["low"], df["close"],
                           length=SUPERT_PERIOD, multiplier=SUPERT_MULT)
        st_col = next((c for c in st.columns if c.startswith("SUPERTd_")), None)
        df["st_dir"] = st[st_col].astype(float) if st_col else np.nan
    except Exception:
        df["st_dir"] = np.nan
    # Choppiness Index
    try:
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"]  - df["close"].shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr_sum = tr.rolling(CHOP_PERIOD).sum()
        hi_n    = df["high"].rolling(CHOP_PERIOD).max()
        lo_n    = df["low"].rolling(CHOP_PERIOD).min()
        rng_n   = (hi_n - lo_n).replace(0, np.nan)
        df["chop"] = 100 * np.log10(atr_sum / rng_n) / np.log10(CHOP_PERIOD)
    except Exception:
        df["chop"] = np.nan
    # VWAP  (24-bar rolling)
    try:
        tp = (df["high"] + df["low"] + df["close"]) / 3
        df["vwap"] = ((tp * df["volume"]).rolling(VWAP_PERIOD).sum()
                      / df["volume"].rolling(VWAP_PERIOD).sum())
    except Exception:
        df["vwap"] = np.nan
    return df

# ══════════════════════════════════════════════════════════════════
#  SIGNAL  (SMA ribbon + MACD cross + momentum)
# ══════════════════════════════════════════════════════════════════
def get_signal(df: pd.DataFrame) -> str:
    if df is None or len(df) < WARMUP_BARS:
        return "neutral"
    clean = df.dropna(subset=["sma200","macd","macd_sig","histogram"])
    if len(clean) < 2:
        return "neutral"
    prev = clean.iloc[-2]
    curr = clean.iloc[-1]

    bull = curr["close"] > curr["sma20"] > curr["sma50"] > curr["sma100"] > curr["sma200"]
    bear = curr["close"] < curr["sma20"] < curr["sma50"] < curr["sma100"] < curr["sma200"]
    xup  = prev["macd"] <= prev["macd_sig"] and curr["macd"] > curr["macd_sig"]
    xdn  = prev["macd"] >= prev["macd_sig"] and curr["macd"] < curr["macd_sig"]
    mup  = curr["histogram"] > prev["histogram"]
    mdn  = curr["histogram"] < prev["histogram"]

    if bull and xup and curr["macd"] > 0 and mup:
        return "long"
    if bear and xdn and curr["macd"] < 0 and mdn:
        return "short"

    # Debug logging
    if bear and curr["macd"] < 0:
        if not xdn:
            log.debug(f"SHORT no cross  macd={curr['macd']:.4f}")
        elif not mdn:
            log.debug(f"SHORT mom_dn=False  hist={curr['histogram']:.4f}")
    elif bull and curr["macd"] > 0:
        if not xup:
            log.debug(f"LONG no cross  macd={curr['macd']:.4f}")
        elif not mup:
            log.debug(f"LONG mom_up=False  hist={curr['histogram']:.4f}")

    return "neutral"

# ══════════════════════════════════════════════════════════════════
#  FILTERS
# ══════════════════════════════════════════════════════════════════
def apply_filters(df: pd.DataFrame, signal: str,
                  htf_df: pd.DataFrame) -> tuple:
    """Run all enabled filters on the last closed bar.
    Returns (passed: bool, blockers: list[str])"""
    curr     = df.iloc[-1]
    blockers = []

    # 1. Candle body
    if USE_BODY_FILTER:
        rng  = curr["high"] - curr["low"]
        body = abs(curr["close"] - curr["open"])
        pct  = body / rng if rng > 0 else 0
        if pct < BODY_MIN_PCT:
            blockers.append(f"BODY:{pct*100:.0f}%<{BODY_MIN_PCT*100:.0f}%")

    # 2. Supertrend
    if USE_SUPERT_FILTER:
        st = curr.get("st_dir")
        if st is not None and not pd.isna(st):
            if signal == "long"  and int(st) != 1:  blockers.append("SUPERT:bear")
            if signal == "short" and int(st) != -1: blockers.append("SUPERT:bull")

    # 3. Choppiness Index
    if USE_CHOP_FILTER:
        ch = curr.get("chop")
        if ch is not None and not pd.isna(ch):
            if ch > CHOP_MAX:
                blockers.append(f"CHOP:{ch:.1f}>{CHOP_MAX}")

    # 4. VWAP
    if USE_VWAP_FILTER:
        vw = curr.get("vwap")
        px = curr["close"]
        if vw is not None and not pd.isna(vw):
            if signal == "long"  and px < vw: blockers.append(f"VWAP:below({vw:.0f})")
            if signal == "short" and px > vw: blockers.append(f"VWAP:above({vw:.0f})")

    # 5. HTF MACD (4H)
    if USE_HTF_MACD_FILTER and htf_df is not None and len(htf_df) >= HTF_MACD_SLOW + HTF_MACD_SIG:
        try:
            m = ta.macd(htf_df["close"],
                        fast=HTF_MACD_FAST,
                        slow=HTF_MACD_SLOW,
                        signal=HTF_MACD_SIG)
            mc = f"MACD_{HTF_MACD_FAST}_{HTF_MACD_SLOW}_{HTF_MACD_SIG}"
            sc = f"MACDs_{HTF_MACD_FAST}_{HTF_MACD_SLOW}_{HTF_MACD_SIG}"
            if mc in m.columns and sc in m.columns:
                mv = m[mc].iloc[-1]; sv = m[sc].iloc[-1]
                if not pd.isna(mv) and not pd.isna(sv):
                    htf_bull = mv > sv and mv > 0
                    htf_bear = mv < sv and mv < 0
                    if signal == "long"  and not htf_bull:
                        blockers.append(f"HMACD:{'bear' if htf_bear else 'flat'}({mv:.1f})")
                    if signal == "short" and not htf_bear:
                        blockers.append(f"HMACD:{'bull' if htf_bull else 'flat'}({mv:.1f})")
        except Exception as e:
            log.debug(f"HTF MACD filter: {e}")

    return len(blockers) == 0, blockers

# ══════════════════════════════════════════════════════════════════
#  ORDER HELPERS
# ══════════════════════════════════════════════════════════════════
def get_balance(client: HTTP) -> float:
    try:
        acct = client.get_wallet_balance(
            accountType="UNIFIED", coin="USDT")["result"]["list"][0]
        for k in ("totalAvailableBalance","totalMarginBalance",
                   "totalWalletBalance","totalEquity"):
            try:
                v = float(acct.get(k, "") or 0)
                if v > 0: return v
            except Exception:
                pass
        return 0.0
    except Exception as e:
        log.error(f"get_balance: {e}"); return 0.0

def get_position(client: HTTP):
    try:
        for pos in client.get_positions(
                category="linear", symbol=SYMBOL)["result"]["list"]:
            if float(pos.get("size", 0)) > 0:
                return pos
        return None
    except Exception as e:
        log.error(f"get_position: {e}"); return None

def set_leverage_live(client: HTTP):
    try:
        client.set_leverage(category="linear", symbol=SYMBOL,
                            buyLeverage=str(LEVERAGE), sellLeverage=str(LEVERAGE))
    except Exception:
        pass  # 110043 = already set

def calc_qty(balance: float, price: float) -> float:
    notional = min(balance * RISK_PCT * LEVERAGE,
                   balance * MAX_COLLATERAL_PCT * LEVERAGE)
    qty = math.floor((notional / price) / _QTY_STEP) * _QTY_STEP
    return max(round(qty, _QTY_PREC), 0.0)

def place_order(client: HTTP, side: str, qty: float, reduce_only: bool = False):
    try:
        return client.place_order(
            category="linear", symbol=SYMBOL, side=side,
            orderType="Market", qty=str(qty),
            timeInForce="GTC", reduceOnly=reduce_only)
    except Exception as e:
        log.error(f"place_order: {e}"); return None

def place_limit(client: HTTP, side: str, qty: float,
                price: float, reduce_only: bool = False):
    try:
        return client.place_order(
            category="linear", symbol=SYMBOL, side=side,
            orderType="Limit", qty=str(qty),
            price=str(round(price, _PRICE_PREC)),
            timeInForce="GTC", reduceOnly=reduce_only)
    except Exception as e:
        log.error(f"place_limit: {e}"); return None

def cancel_all_orders(client: HTTP):
    try:
        client.cancel_all_orders(category="linear", symbol=SYMBOL)
        log.info("Cancelled all open orders")
    except Exception as e:
        log.warning(f"cancel_all_orders: {e}")

SL_PRICE_CROSSED = -1  # sentinel: mark price already past SL

def set_sl(client: HTTP, sl_price: float,
           direction: str = "", retries: int = 3) -> object:
    """Set stop loss with retries.
    Returns True on success, False on failure,
    SL_PRICE_CROSSED if mark price already past SL."""
    _sl = sl_price
    for attempt in range(1, retries + 1):
        try:
            resp = client.set_trading_stop(
                category="linear", symbol=SYMBOL,
                stopLoss=str(round(_sl, _PRICE_PREC)),
                slTriggerBy="MarkPrice", tpslMode="Full", positionIdx=0)
            if resp and resp.get("retCode") == 0:
                if _sl != sl_price:
                    log.warning(f"set_sl: adjusted {sl_price:.{_PRICE_PREC}f} → {_sl:.{_PRICE_PREC}f}")
                return True
            ret_code = resp.get("retCode") if resp else None
            if ret_code == 10001 and direction:
                try:
                    tk  = client.get_tickers(category="linear", symbol=SYMBOL)
                    mpx = float(tk["result"]["list"][0]["markPrice"])
                    already_hit = (
                        (direction == "long"  and mpx <= sl_price) or
                        (direction == "short" and mpx >= sl_price))
                    if already_hit:
                        log.error(f"set_sl: mark {mpx:.{_PRICE_PREC}f} already past SL "
                                  f"{sl_price:.{_PRICE_PREC}f} — signal immediate close")
                        return SL_PRICE_CROSSED
                    if attempt < retries:
                        _sl = round(mpx * (0.998 if direction == "long" else 1.002), _PRICE_PREC)
                        log.warning(f"set_sl 10001: nudging to {_sl:.{_PRICE_PREC}f}")
                except Exception as te:
                    log.warning(f"set_sl mark fetch: {te}")
            else:
                log.warning(f"set_sl attempt {attempt}/{retries}: {resp}")
        except Exception as e:
            log.warning(f"set_sl attempt {attempt}/{retries} error: {e}")
        if attempt < retries:
            time.sleep(1.5)
    return False

def _safe_trail(entry: float, trail_dist: float,
                direction: str, live_px: float) -> float:
    """Clamp trail_dist so it won't trigger immediately at live_px."""
    if direction == "short":
        if live_px + trail_dist >= entry:
            trail_dist = round(abs(live_px - entry) * 0.8, _PRICE_PREC)
            log.warning(f"[TRAIL] clamped to {trail_dist}")
    else:
        if live_px - trail_dist <= entry:
            trail_dist = round(abs(entry - live_px) * 0.8, _PRICE_PREC)
            log.warning(f"[TRAIL] clamped to {trail_dist}")
    return max(trail_dist, 0.0001)

def set_bybit_trailing(client: HTTP, trail_dist: float, active_price: float = 0.0):
    """Activate Bybit native real-time trailing stop on the open position."""
    try:
        params = dict(category="linear", symbol=SYMBOL,
                      trailingStop=f"{trail_dist:.{_PRICE_PREC}f}", positionIdx=0)
        if active_price > 0:
            params["activePrice"] = f"{active_price:.{_PRICE_PREC}f}"
        resp = client.set_trading_stop(**params)
        if resp and resp.get("retCode") == 0:
            log.info(f"[TRAIL] set dist={trail_dist:.{_PRICE_PREC}f}"
                     + (f"  activates@{active_price:.{_PRICE_PREC}f}" if active_price else ""))
        else:
            log.warning(f"[TRAIL] set failed: {resp}")
        return resp
    except Exception as e:
        log.error(f"set_bybit_trailing: {e}"); return None

def _check_order_filled(client: HTTP, order_id: str) -> bool:
    """Check if a specific order was filled on Bybit."""
    if not order_id: return False
    try:
        resp   = client.get_order_history(category="linear", symbol=SYMBOL, orderId=order_id)
        orders = resp.get("result", {}).get("list", [])
        if orders:
            return orders[0].get("orderStatus", "") in ("Filled", "PartiallyFilled")
        return False
    except Exception as e:
        log.warning(f"[ORDER_CHECK] {order_id[:8]}: {e}"); return False

# ══════════════════════════════════════════════════════════════════
#  BOT
# ══════════════════════════════════════════════════════════════════
class MergedBot:

    def __init__(self):
        self.client = get_client()
        fetch_and_apply_specs(self.client)

        self.in_trade     = False
        self.direction    = None
        self.entry_price  = 0.0
        self.qty_total    = 0.0    # original full qty at entry
        self.qty_remain   = 0.0    # qty still open
        self.sl_price     = 0.0
        self.trail_sl     = 0.0
        self.tp1_price    = 0.0
        self.tp2_price    = 0.0
        self.tp1_hit      = False
        self.tp2_done     = False
        self.best_price   = 0.0
        self.wins         = 0
        self.losses       = 0
        self.trade_count  = 0
        self.total_pnl    = 0.0
        self.tp1_order_id = ""
        self.tp2_order_id = ""
        self._ext_strikes = 0      # consecutive no-position readings
        self._last_bar_ts = 0      # same-bar re-entry guard
        self._htf_df      = pd.DataFrame()
        self._htf_last    = 0.0    # epoch of last HTF fetch

        self._load_state()
        if not self.in_trade:
            self._detect_position()

    # ── Helpers ─────────────────────────────────────────────────
    def _qty(self, frac: float) -> float:
        """Floor qty fraction to exchange step."""
        q = math.floor(self.qty_total * frac / _QTY_STEP) * _QTY_STEP
        return max(round(q, _QTY_PREC), _MIN_QTY)

    # ── Entry ────────────────────────────────────────────────────
    def enter_trade(self, signal: str, price: float):
        balance = get_balance(self.client)
        if balance <= 0:
            log.warning("Zero balance — skipping entry"); return

        if LIVE_TRADING:
            set_leverage_live(self.client)

        qty = calc_qty(balance, price)
        if qty <= 0 or qty < _MIN_QTY:
            if balance >= _MIN_QTY * price / LEVERAGE:
                qty = _MIN_QTY
            else:
                log.warning(f"Balance ${balance:.2f} too low for {SYMBOL}"); return

        is_long = signal == "long"
        sl  = round(price * (1 - SL_PCT  if is_long else 1 + SL_PCT),  _PRICE_PREC)
        tp1 = round(price * (1 + TP1_PCT if is_long else 1 - TP1_PCT), _PRICE_PREC)
        tp2 = round(price * (1 + TP2_PCT if is_long else 1 - TP2_PCT), _PRICE_PREC)

        if LIVE_TRADING:
            side = "Buy" if is_long else "Sell"
            resp = place_order(self.client, side, qty)
            if not resp or resp.get("retCode") != 0:
                log.error(f"Entry failed: {resp}"); return

            # Set qty_total NOW so _qty() works correctly for TP limit sizing
            self.qty_total = qty

            sl_ok = set_sl(self.client, sl, direction=signal)
            if sl_ok is SL_PRICE_CROSSED:
                log.error("[ENTRY] Mark already past SL — emergency close")
                tg(f"🚨 *SL CROSSED AT ENTRY {SYMBOL}*\nEmergency close @ market")
                cancel_all_orders(self.client)
                place_order(self.client, "Sell" if is_long else "Buy", qty, reduce_only=True)
                return
            elif not sl_ok:
                log.error("[ENTRY] SL set failed — position NAKED, will retry")
                tg(f"🚨 *SL FAILED AFTER ENTRY {SYMBOL}*\nSL=`{sl:.{_PRICE_PREC}f}` — retrying next loop")

            # TP1 limit
            tp1_qty  = self._qty(TP1_CLOSE_PCT)
            tp1_side = "Sell" if is_long else "Buy"
            r1 = place_limit(self.client, tp1_side, tp1_qty, tp1, reduce_only=True)
            if r1 and r1.get("retCode") == 0:
                self.tp1_order_id = r1["result"]["orderId"]
                log.info(f"TP1 limit @ {tp1:.{_PRICE_PREC}f}  qty={tp1_qty}")
            else:
                log.warning(f"TP1 limit failed: {r1}")

            # TP2 limit
            tp2_qty = self._qty(TP2_CLOSE_PCT)
            r2 = place_limit(self.client, tp1_side, tp2_qty, tp2, reduce_only=True)
            if r2 and r2.get("retCode") == 0:
                self.tp2_order_id = r2["result"]["orderId"]
                log.info(f"TP2 limit @ {tp2:.{_PRICE_PREC}f}  qty={tp2_qty}")
            else:
                log.warning(f"TP2 limit failed: {r2}")
        else:
            self.qty_total = qty  # set before state so _qty() works
            log.info(f"[PAPER] {signal.upper()} {qty} @ {price:.{_PRICE_PREC}f}")

        self.in_trade     = True;   self.tp1_hit     = False
        self.tp2_done     = False;  self.best_price  = price
        self.direction    = signal; self.entry_price  = price
        self.qty_total    = qty;    self.qty_remain   = qty
        self.sl_price     = sl;     self.trail_sl     = sl
        self.tp1_price    = tp1;    self.tp2_price    = tp2
        self.trade_count += 1
        self.total_pnl   -= qty * price * FEE_RATE  # entry fee

        self._save_state()
        log.info(f"ENTRY {signal.upper()} @ {price:.{_PRICE_PREC}f}  qty={qty}  "
                 f"SL={sl:.{_PRICE_PREC}f}  TP1={tp1:.{_PRICE_PREC}f}  TP2={tp2:.{_PRICE_PREC}f}")
        tg(f"📈 *ENTRY {signal.upper()} {SYMBOL}*\n"
           f"Price: `{price:.{_PRICE_PREC}f}`  Qty: `{qty}`\n"
           f"SL: `{sl:.{_PRICE_PREC}f}` (-{SL_PCT*100*LEVERAGE:.0f}% lev / -{SL_PCT*100:.1f}% price)\n"
           f"TP1: `{tp1:.{_PRICE_PREC}f}` (+{TP1_PCT*100*LEVERAGE:.0f}% lev) → close 80%\n"
           f"TP2: `{tp2:.{_PRICE_PREC}f}` (+{TP2_PCT*100*LEVERAGE:.0f}% lev) → close 10% + trail\n"
           f"Rider: {RIDER_TRAIL_PCT*100*LEVERAGE:.0f}% lev trailing gap  Trade #{self.trade_count}")

    # ── TP order verification + recovery ────────────────────────
    def _verify_tp_orders(self, price: float):
        """Every poll: verify TP orders still live on Bybit, re-place if not."""
        if not LIVE_TRADING or not self.in_trade: return
        if self.tp1_price <= 0 or self.qty_total <= 0: return

        is_long  = self.direction == "long"
        tp_side  = "Sell" if is_long else "Buy"

        try:
            resp     = self.client.get_open_orders(category="linear", symbol=SYMBOL)
            open_ids = {o["orderId"] for o in resp.get("result", {}).get("list", [])}
        except Exception as e:
            log.warning(f"[TP_CHECK] open orders fetch failed: {e}"); return

        def _check_and_replace(order_id, label, tp_price, frac):
            """Check if order live; if not, check filled; if not, re-place."""
            if order_id and order_id in open_ids:
                return order_id, False   # confirmed live

            if order_id:
                # Not in open orders — check if filled
                if _check_order_filled(self.client, order_id):
                    log.info(f"[TP_CHECK] {label} filled silently")
                    return "", True   # (new_id, filled)

            # Either no ID or cancelled — re-place
            qty = self._qty(frac)
            qty = min(qty, self.qty_remain)
            if qty <= 0 or self.qty_remain <= 0:
                return "", False
            r = place_limit(self.client, tp_side, qty, tp_price, reduce_only=True)
            if r and r.get("retCode") == 0:
                nid = r["result"]["orderId"]
                log.warning(f"[TP_RECOVERY] {label} re-placed @ {tp_price:.{_PRICE_PREC}f}  qty={qty}")
                tg(f"♻️ *{label} RE-PLACED {SYMBOL}*\n@ `{tp_price:.{_PRICE_PREC}f}`  qty=`{qty}`")
                return nid, False
            log.error(f"[TP_RECOVERY] {label} re-place failed: {r}")
            return "", False

        # TP1
        if not self.tp1_hit:
            nid, filled = _check_and_replace(self.tp1_order_id, "TP1",
                                             self.tp1_price, TP1_CLOSE_PCT)
            if filled:
                tp1_qty         = self._qty(TP1_CLOSE_PCT)
                self.qty_remain = round(self.qty_total - tp1_qty, _QTY_PREC)
                self.tp1_hit    = True
                self.tp1_order_id = ""
                pnl = (tp1_qty * (self.tp1_price - self.entry_price)
                       if self.direction == "long"
                       else tp1_qty * (self.entry_price - self.tp1_price))
                pnl -= tp1_qty * self.tp1_price * FEE_RATE
                self.total_pnl += pnl
                tg(f"🥇 *TP1 SILENT FILL {SYMBOL}*\n"
                   f"@ `{self.tp1_price:.{_PRICE_PREC}f}`  remain=`{self.qty_remain}`")
            else:
                self.tp1_order_id = nid

        # TP2
        if not self.tp2_done:
            nid, filled = _check_and_replace(self.tp2_order_id, "TP2",
                                             self.tp2_price, TP2_CLOSE_PCT)
            if filled:
                tp2_qty         = self._qty(TP2_CLOSE_PCT)
                self.qty_remain = round(self.qty_remain - tp2_qty, _QTY_PREC)
                self.tp2_done   = True
                self.tp2_order_id = ""
                self.trail_sl   = round(self.entry_price, _PRICE_PREC)
                # SL → breakeven
                set_sl(self.client, self.entry_price, direction=self.direction)
                # Activate trailing
                try:
                    tk   = self.client.get_tickers(category="linear", symbol=SYMBOL)
                    lpx  = float(tk["result"]["list"][0]["lastPrice"])
                except Exception:
                    lpx  = price
                td = _safe_trail(self.entry_price,
                                 round(self.entry_price * RIDER_TRAIL_PCT, _PRICE_PREC),
                                 self.direction, lpx)
                set_bybit_trailing(self.client, td)
                tg(f"🥈 *TP2 SILENT FILL {SYMBOL}*\n"
                   f"@ `{self.tp2_price:.{_PRICE_PREC}f}`\n"
                   f"Rider: `{self.qty_remain}`  Trail: `{RIDER_TRAIL_PCT*100:.0f}%`  SL→BE")
            else:
                self.tp2_order_id = nid

    # ── SL recovery: re-set if missing on Bybit ─────────────────
    def _recover_sl(self, price: float, pos: dict):
        if not LIVE_TRADING or self.tp2_done or not pos: return
        live_sl = float(pos.get("stopLoss", 0) or 0)
        if live_sl == 0 and self.trail_sl > 0:
            log.warning(f"[SL_RECOVERY] No SL on Bybit — re-setting to {self.trail_sl:.{_PRICE_PREC}f}")
            ok = set_sl(self.client, self.trail_sl, direction=self.direction)
            if ok is SL_PRICE_CROSSED:
                tg(f"🚨 *SL HIT DURING RECOVERY {SYMBOL}*\nClosing now")
                self._close(price, "SL_PRICE_CROSSED")
            elif ok:
                log.info(f"[SL_RECOVERY] Restored @ {self.trail_sl:.{_PRICE_PREC}f}")
                tg(f"✅ *SL RESTORED {SYMBOL}*\n`{self.trail_sl:.{_PRICE_PREC}f}`")
            else:
                log.error("[SL_RECOVERY] Failed again — NAKED POSITION")
                tg(f"🚨 *SL STILL MISSING {SYMBOL}*\nCheck manually")

    # ── Manage open position ─────────────────────────────────────
    def manage_trade(self, price: float, signal: str, cached_pos=None):
        if not self.in_trade: return

        pos = cached_pos
        if pos is None and LIVE_TRADING:
            pos = get_position(self.client)

        # SL recovery
        self._recover_sl(price, pos)

        # TP order verification / recovery
        self._verify_tp_orders(price)

        # ── Phase 3: RIDER — Bybit native trailing ───────────────
        if self.tp2_done and self.qty_remain > 0:
            if LIVE_TRADING:
                size = float(pos.get("size", -1)) if pos else -1
                if size == 0:
                    # Trailing stop fired — position closed by Bybit
                    try:
                        hist   = self.client.get_closed_pnl(
                            category="linear", symbol=SYMBOL, limit=1)
                        ep_    = float(hist["result"]["list"][0]["avgExitPrice"]) if hist["result"]["list"] else price
                        epnl   = float(hist["result"]["list"][0]["closedPnl"]) if hist["result"]["list"] else 0.0
                    except Exception:
                        ep_ = price; epnl = 0.0
                    self.total_pnl += epnl
                    if epnl >= 0: self.wins += 1
                    else:         self.losses += 1
                    log.info(f"[RIDER] Trailing stop fired @ ~{ep_:.{_PRICE_PREC}f}  pnl={epnl:+.4f}")
                    tg(f"🏁 *RIDER EXIT {self.direction.upper()} {SYMBOL}*\n"
                       f"Trailing stop @ `{ep_:.{_PRICE_PREC}f}`\n"
                       f"Entry: `{self.entry_price:.{_PRICE_PREC}f}`  PnL: `{epnl:+.4f}`\n"
                       f"W{self.wins}/L{self.losses}")
                    self._reset(); self._save_state(); return
                elif size == -1:
                    log.warning("[RIDER] get_position failed — skipping this poll"); return
                else:
                    # Position still open — verify trailing still active
                    live_trail = float(pos.get("trailingStop", 0) or 0) if pos else 0
                    if live_trail == 0:
                        log.warning("[RIDER] Trailing missing on Bybit — re-activating")
                        try:
                            tk  = self.client.get_tickers(category="linear", symbol=SYMBOL)
                            lpx = float(tk["result"]["list"][0]["lastPrice"])
                        except Exception:
                            lpx = price
                        td = _safe_trail(self.entry_price,
                                         round(self.entry_price * RIDER_TRAIL_PCT, _PRICE_PREC),
                                         self.direction, lpx)
                        set_bybit_trailing(self.client, td)
                        tg(f"♻️ *TRAIL RE-ACTIVATED {SYMBOL}*\ndist=`{td:.{_PRICE_PREC}f}`")
            else:
                # Paper mode: manual trailing
                is_long = self.direction == "long"
                if is_long:
                    if price > self.best_price: self.best_price = price
                    new_sl = self.best_price * (1 - RIDER_TRAIL_PCT)
                    if new_sl > self.trail_sl: self.trail_sl = round(new_sl, _PRICE_PREC)
                    if price <= self.trail_sl:
                        self._close(price, "RIDER_TRAIL"); return
                else:
                    if self.best_price == 0 or price < self.best_price: self.best_price = price
                    new_sl = self.best_price * (1 + RIDER_TRAIL_PCT)
                    if new_sl < self.trail_sl: self.trail_sl = round(new_sl, _PRICE_PREC)
                    if price >= self.trail_sl:
                        self._close(price, "RIDER_TRAIL"); return
            return

        # ── SL check (pre-TP2 only) ──────────────────────────────
        if not self.tp2_done:
            sl_hit = ((self.direction == "long"  and price <= self.trail_sl) or
                      (self.direction == "short" and price >= self.trail_sl))
            if sl_hit:
                log.info(f"[SL] hit @ {price:.{_PRICE_PREC}f}  SL={self.trail_sl:.{_PRICE_PREC}f}")
                tg(f"🛑 *STOP LOSS {self.direction.upper()} {SYMBOL}*\n"
                   f"Price: `{price:.{_PRICE_PREC}f}`  SL: `{self.trail_sl:.{_PRICE_PREC}f}`\n"
                   f"Entry: `{self.entry_price:.{_PRICE_PREC}f}`  TP1_hit: `{self.tp1_hit}`")
                self._close(price, "STOP_LOSS"); return

        # ── TP1 detection ────────────────────────────────────────
        if not self.tp1_hit and self.qty_remain > 0:
            tp1_fired = False
            if LIVE_TRADING:
                actual = float(pos.get("size", self.qty_remain)) if pos else self.qty_remain
                log.info(f"[TP1 CHECK] actual={actual} total={self.qty_total} "
                         f"threshold={self.qty_total*0.30:.4f}")
                if actual <= self.qty_total * 0.30:
                    tp1_fired       = True
                    self.qty_remain = actual
            else:
                hit = ((self.direction == "long"  and price >= self.tp1_price) or
                       (self.direction == "short" and price <= self.tp1_price))
                if hit:
                    cq = min(self._qty(TP1_CLOSE_PCT), self.qty_remain)
                    self.qty_remain -= cq
                    tp1_fired = True

            if tp1_fired:
                self.tp1_hit = True
                cq_used = round(self.qty_total * TP1_CLOSE_PCT, _QTY_PREC)
                pnl = (cq_used * (self.tp1_price - self.entry_price)
                       if self.direction == "long"
                       else cq_used * (self.entry_price - self.tp1_price))
                pnl -= cq_used * self.tp1_price * FEE_RATE
                self.total_pnl += pnl
                self._save_state()
                log.info(f"[TP1] +{TP1_PCT*100*LEVERAGE:.0f}% lev fired  remain={self.qty_remain}  pnl={pnl:+.4f}")
                tg(f"🥇 *TP1 +{TP1_PCT*100*LEVERAGE:.0f}% lev {self.direction.upper()} {SYMBOL}*\n"
                   f"@ `{self.tp1_price:.{_PRICE_PREC}f}`  Closed 80%\n"
                   f"Remain: `{self.qty_remain}`  SL still: `-{SL_PCT*100*LEVERAGE:.0f}%` lev\n"
                   f"PnL leg: `{pnl:+.4f}`")

        # ── TP2 detection ─────────────────────────────────────────
        if self.tp1_hit and not self.tp2_done and self.qty_remain > 0:
            tp2_fired = False
            if LIVE_TRADING:
                actual = float(pos.get("size", self.qty_remain)) if pos else self.qty_remain
                log.info(f"[TP2 CHECK] actual={actual} total={self.qty_total} "
                         f"threshold={self.qty_total*0.15:.4f}")
                if actual <= self.qty_total * 0.15:   # ≤15% → TP2 filled (rider ~10%)
                    tp2_fired       = True
                    self.qty_remain = actual
            else:
                hit = ((self.direction == "long"  and price >= self.tp2_price) or
                       (self.direction == "short" and price <= self.tp2_price))
                if hit:
                    cq = min(self._qty(TP2_CLOSE_PCT), self.qty_remain)
                    self.qty_remain -= cq
                    tp2_fired = True

            if tp2_fired:
                cq_used = round(self.qty_total * TP2_CLOSE_PCT, _QTY_PREC)
                pnl = (cq_used * (self.tp2_price - self.entry_price)
                       if self.direction == "long"
                       else cq_used * (self.entry_price - self.tp2_price))
                pnl -= cq_used * self.tp2_price * FEE_RATE
                self.total_pnl += pnl
                self.tp2_done   = True
                self.best_price = price
                self.trail_sl   = round(self.entry_price, _PRICE_PREC)
                if LIVE_TRADING:
                    set_sl(self.client, self.entry_price, direction=self.direction)
                    td = _safe_trail(
                        self.entry_price,
                        round(self.entry_price * RIDER_TRAIL_PCT, _PRICE_PREC),
                        self.direction, price)
                    # Activate at TP2 price, 20% trailing gap from there
                    set_bybit_trailing(self.client, td, active_price=self.tp2_price)
                self._save_state()
                log.info(f"[TP2] fired  rider={self.qty_remain}  SL→BE  "
                         f"trail={RIDER_TRAIL_PCT*100*LEVERAGE:.0f}% lev  pnl={pnl:+.4f}")
                tg(f"🥈 *TP2 +{TP2_PCT*100*LEVERAGE:.0f}% lev {self.direction.upper()} {SYMBOL}*\n"
                   f"@ `{self.tp2_price:.{_PRICE_PREC}f}`  Closed 10%\n"
                   f"🏇 Rider: `{self.qty_remain}` — trailing `{RIDER_TRAIL_PCT*100*LEVERAGE:.0f}%` lev\n"
                   f"SL → BE `{self.entry_price:.{_PRICE_PREC}f}`\n"
                   f"PnL leg: `{pnl:+.4f}`")

        # ── Signal flip exit (pre-TP2 only; rider never flips) ───
        if not self.tp2_done:
            if signal != "neutral" and signal != self.direction:
                self._close(price, "SIGNAL_FLIP")

    # ── Close ────────────────────────────────────────────────────
    def _close(self, price: float, reason: str):
        if self.qty_remain <= 0:
            self._reset(); return
        if LIVE_TRADING:
            cancel_all_orders(self.client)
            self.tp1_order_id = ""; self.tp2_order_id = ""
            side = "Sell" if self.direction == "long" else "Buy"
            resp = place_order(self.client, side, self.qty_remain, reduce_only=True)
            if not resp or resp.get("retCode") != 0:
                log.error(f"Close failed: {resp}"); return

        pnl = self.qty_remain * abs(price - self.entry_price)
        if ((self.direction == "long"  and price < self.entry_price) or
                (self.direction == "short" and price > self.entry_price)):
            pnl = -pnl
        net = pnl - self.qty_remain * price * FEE_RATE
        self.total_pnl += net
        if net >= 0: self.wins   += 1
        else:        self.losses += 1

        emoji = "✅" if net >= 0 else "❌"
        log.info(f"CLOSE [{reason}] @ {price:.{_PRICE_PREC}f}  "
                 f"pnl={net:+.4f}  W{self.wins}/L{self.losses}")
        tg(f"{emoji} *CLOSE {reason} {SYMBOL}*\n"
           f"Entry: `{self.entry_price:.{_PRICE_PREC}f}`  Exit: `{price:.{_PRICE_PREC}f}`\n"
           f"PnL: `{net:+.4f}`  W{self.wins}/L{self.losses}")
        self._reset()
        self._save_state()

    def _reset(self):
        self.in_trade     = False; self.direction    = None
        self.entry_price  = 0.0;   self.qty_total    = 0.0
        self.qty_remain   = 0.0;   self.sl_price     = 0.0
        self.trail_sl     = 0.0;   self.tp1_hit      = False
        self.tp2_done     = False; self.best_price   = 0.0
        self.tp1_order_id = "";    self.tp2_order_id = ""
        self._ext_strikes = 0

    # ── State save ───────────────────────────────────────────────
    def _save_state(self):
        try:
            with open(_STATE_FILE, "w") as f:
                json.dump({
                    "in_trade":     self.in_trade,
                    "direction":    self.direction,
                    "entry_price":  self.entry_price,
                    "qty":          self.qty_remain,
                    "initial_qty":  self.qty_total,
                    "sl_price":     self.trail_sl,
                    "partial_done": self.tp1_hit,
                    "tp2_done":     self.tp2_done,
                    "tp1_price":    self.tp1_price,
                    "tp2_price":    self.tp2_price,
                    "tp1_order_id": self.tp1_order_id,
                    "tp2_order_id": self.tp2_order_id,
                    "wins":         self.wins,
                    "losses":       self.losses,
                    "total_pnl":    round(self.total_pnl, 6),
                }, f, indent=2)
        except Exception as e:
            log.warning(f"State save: {e}")

    # ── State load with full TP catch-up verification ────────────
    def _load_state(self):
        try:
            if not os.path.exists(_STATE_FILE): return
            with open(_STATE_FILE) as f: s = json.load(f)
            if not s.get("in_trade"): return

            self.in_trade     = True
            self.direction    = s.get("direction")
            self.entry_price  = float(s.get("entry_price", 0))
            self.qty_remain   = float(s.get("qty", 0))
            self.qty_total    = float(s.get("initial_qty", self.qty_remain))
            self.trail_sl     = float(s.get("sl_price", 0))
            self.sl_price     = self.trail_sl
            self.tp1_hit      = bool(s.get("partial_done", False))
            self.tp2_done     = bool(s.get("tp2_done", False))
            self.tp1_price    = float(s.get("tp1_price", 0))
            self.tp2_price    = float(s.get("tp2_price", 0))
            self.tp1_order_id = s.get("tp1_order_id") or ""
            self.tp2_order_id = s.get("tp2_order_id") or ""
            self.wins         = int(s.get("wins", 0))
            self.losses       = int(s.get("losses", 0))
            self.total_pnl    = float(s.get("total_pnl", 0))

            log.info(f"[RESTORED] {self.direction} @ {self.entry_price}  "
                     f"TP1={self.tp1_hit}  TP2={self.tp2_done}  "
                     f"qty={self.qty_remain}")

            if not LIVE_TRADING: return

            # Live: get actual position + live price
            try:
                pos    = get_position(self.client)
                actual = float(pos.get("size", 0)) if pos else 0.0
            except Exception:
                actual = self.qty_remain
            try:
                tk     = self.client.get_tickers(category="linear", symbol=SYMBOL)
                lpx    = float(tk["result"]["list"][0]["lastPrice"])
            except Exception:
                lpx = self.entry_price

            tp_side = "Sell" if self.direction == "long" else "Buy"

            # Position gone while offline
            if actual == 0 and self.qty_remain > 0:
                log.info("[RESTORE] Position closed while offline — resetting")
                tg(f"⚠️ *{SYMBOL} closed while offline*\nEntry was `{self.entry_price:.{_PRICE_PREC}f}`")
                self._reset(); self._save_state(); return

            # Both TPs filled while offline (only 10% rider left)
            if not self.tp1_hit and not self.tp2_done and actual > 0:
                if actual <= self.qty_total * 0.15:
                    log.info("[RESTORE] Both TPs filled offline — activating rider")
                    self.qty_remain = actual
                    self.tp1_hit    = True; self.tp2_done   = True
                    self.tp1_order_id = ""; self.tp2_order_id = ""
                    self.trail_sl   = round(self.entry_price, _PRICE_PREC)
                    set_sl(self.client, self.entry_price, direction=self.direction)
                    td = _safe_trail(self.entry_price,
                                     round(self.entry_price * RIDER_TRAIL_PCT, _PRICE_PREC),
                                     self.direction, lpx)
                    set_bybit_trailing(self.client, td)
                    tg(f"🚨 *CATCH-UP BOTH TPs {self.direction.upper()} {SYMBOL}*\n"
                       f"Rider: `{actual}` @ live `{lpx:.{_PRICE_PREC}f}`\n"
                       f"SL→BE  Trail `{RIDER_TRAIL_PCT*100*LEVERAGE:.0f}%` lev ACTIVE")

            # TP1 order filled while offline
            if not self.tp1_hit and self.tp1_order_id:
                if _check_order_filled(self.client, self.tp1_order_id):
                    tp1_qty = self._qty(TP1_CLOSE_PCT)
                    self.qty_remain   = round(self.qty_total - tp1_qty, _QTY_PREC)
                    self.tp1_hit      = True
                    self.tp1_order_id = ""
                    log.info(f"[RESTORE] TP1 filled offline  remain={self.qty_remain}")
                    tg(f"🥇 *TP1 CATCH-UP {self.direction.upper()} {SYMBOL}*\n"
                       f"Filled while offline @ `{self.tp1_price:.{_PRICE_PREC}f}`\n"
                       f"Remain: `{self.qty_remain}`")
                else:
                    # Verify still on exchange
                    try:
                        resp = self.client.get_open_orders(category="linear", symbol=SYMBOL)
                        oids = {o["orderId"] for o in resp.get("result", {}).get("list", [])}
                        if self.tp1_order_id not in oids:
                            self.tp1_order_id = ""  # will be re-placed below
                    except Exception: pass

            # TP2 order filled while offline
            if self.tp1_hit and not self.tp2_done and self.tp2_order_id:
                if _check_order_filled(self.client, self.tp2_order_id):
                    self.qty_remain   = actual if actual > 0 else round(
                        self.qty_remain - self._qty(TP2_CLOSE_PCT), _QTY_PREC)
                    self.tp2_done     = True
                    self.tp2_order_id = ""
                    self.trail_sl     = round(self.entry_price, _PRICE_PREC)
                    set_sl(self.client, self.entry_price, direction=self.direction)
                    td = _safe_trail(self.entry_price,
                                     round(self.entry_price * RIDER_TRAIL_PCT, _PRICE_PREC),
                                     self.direction, lpx)
                    set_bybit_trailing(self.client, td)
                    log.info(f"[RESTORE] TP2 filled offline  rider={self.qty_remain}")
                    tg(f"🥈 *TP2 CATCH-UP {self.direction.upper()} {SYMBOL}*\n"
                       f"Filled while offline @ `{self.tp2_price:.{_PRICE_PREC}f}`\n"
                       f"Rider: `{self.qty_remain}`  Trail `{RIDER_TRAIL_PCT*100*LEVERAGE:.0f}%` lev ACTIVE")
                else:
                    try:
                        resp = self.client.get_open_orders(category="linear", symbol=SYMBOL)
                        oids = {o["orderId"] for o in resp.get("result", {}).get("list", [])}
                        if self.tp2_order_id not in oids:
                            self.tp2_order_id = ""
                    except Exception: pass

            # Re-activate trailing if already in rider phase
            if self.tp2_done and self.qty_remain > 0:
                td = _safe_trail(self.entry_price,
                                 round(self.entry_price * RIDER_TRAIL_PCT, _PRICE_PREC),
                                 self.direction, lpx)
                set_bybit_trailing(self.client, td)
                log.info(f"[RESTORE] Trailing re-activated  dist={td}  live={lpx}")
                tg(f"🏇 *RIDER RESTORED {self.direction.upper()} {SYMBOL}*\n"
                   f"Trail `{RIDER_TRAIL_PCT*100*LEVERAGE:.0f}%` lev re-activated  live=`{lpx:.{_PRICE_PREC}f}`")

            # Re-place missing TP limit orders
            if self.tp1_price > 0:
                if not self.tp1_hit and not self.tp1_order_id:
                    qty = min(self._qty(TP1_CLOSE_PCT), self.qty_remain)
                    r = place_limit(self.client, tp_side, qty, self.tp1_price, reduce_only=True)
                    if r and r.get("retCode") == 0:
                        self.tp1_order_id = r["result"]["orderId"]
                        log.info(f"[RESTORE] TP1 re-placed @ {self.tp1_price}")
                if not self.tp2_done and not self.tp2_order_id and self.tp2_price > 0:
                    qty = min(self._qty(TP2_CLOSE_PCT), self.qty_remain)
                    r = place_limit(self.client, tp_side, qty, self.tp2_price, reduce_only=True)
                    if r and r.get("retCode") == 0:
                        self.tp2_order_id = r["result"]["orderId"]
                        log.info(f"[RESTORE] TP2 re-placed @ {self.tp2_price}")

            self._save_state()

        except Exception as e:
            log.warning(f"State load: {e}")

    # ── Detect open position on fresh start ──────────────────────
    def _detect_position(self):
        if not LIVE_TRADING: return
        try:
            pos = get_position(self.client)
            if not pos or float(pos.get("size", 0)) == 0: return

            side      = pos.get("side", "")
            entry     = float(pos.get("avgPrice", 0))
            qty       = float(pos.get("size", 0))
            upnl      = float(pos.get("unrealisedPnl", 0))
            direction = "long" if side == "Buy" else "short"
            is_long   = direction == "long"

            sl  = round(entry * (1 - SL_PCT  if is_long else 1 + SL_PCT),  _PRICE_PREC)
            tp1 = round(entry * (1 + TP1_PCT if is_long else 1 - TP1_PCT), _PRICE_PREC)
            tp2 = round(entry * (1 + TP2_PCT if is_long else 1 - TP2_PCT), _PRICE_PREC)

            try:
                tk  = self.client.get_tickers(category="linear", symbol=SYMBOL)
                lpx = float(tk["result"]["list"][0]["lastPrice"])
            except Exception:
                lpx = entry

            tp1_passed = (lpx >= tp1 if is_long else lpx <= tp1)
            tp2_passed = (lpx >= tp2 if is_long else lpx <= tp2)

            self.in_trade    = True
            self.direction   = direction
            self.entry_price = entry
            self.qty_total   = qty
            self.qty_remain  = qty
            self.trail_sl    = sl
            self.sl_price    = sl
            self.tp1_price   = tp1
            self.tp2_price   = tp2
            self.tp1_hit     = False
            self.tp2_done    = False
            self.best_price  = entry
            self.trade_count += 1

            tp_side = "Sell" if is_long else "Buy"
            log.info(f"[DETECT] {direction.upper()} {qty} @ {entry}  "
                     f"uPnL={upnl:+.4f}  tp1_passed={tp1_passed}  tp2_passed={tp2_passed}")

            if tp2_passed:
                # Both TPs passed — close 80%+10% at market, activate rider
                log.info("[CATCH-UP] Both TPs passed — catching up now")
                q1 = max(round(math.floor(qty*TP1_CLOSE_PCT/_QTY_STEP)*_QTY_STEP, _QTY_PREC), _MIN_QTY)
                q2 = max(round(math.floor(qty*TP2_CLOSE_PCT/_QTY_STEP)*_QTY_STEP, _QTY_PREC), _MIN_QTY)
                place_order(self.client, tp_side, q1, reduce_only=True)
                place_order(self.client, tp_side, q2, reduce_only=True)
                time.sleep(1.5)
                pos2 = get_position(self.client)
                self.qty_remain   = float(pos2.get("size", round(qty-q1-q2, _QTY_PREC))) if pos2 else round(qty-q1-q2, _QTY_PREC)
                self.tp1_hit      = True
                self.tp2_done     = True
                self.trail_sl     = round(entry, _PRICE_PREC)
                set_sl(self.client, entry, direction=direction)
                time.sleep(1.0)
                td = _safe_trail(entry, round(entry*RIDER_TRAIL_PCT, _PRICE_PREC), direction, lpx)
                set_bybit_trailing(self.client, td)
                tg(f"🚨 *CATCH-UP {direction.upper()} {SYMBOL}*\n"
                   f"Both TPs passed offline → closed 90% @ market\n"
                   f"🏇 Rider `{self.qty_remain}`  Trail `{RIDER_TRAIL_PCT*100*LEVERAGE:.0f}%` lev  SL→BE `{entry}`")

            elif tp1_passed:
                # TP1 passed — close 80% at market, place TP2 limit
                log.info("[CATCH-UP] TP1 passed — catching up now")
                q1 = max(round(math.floor(qty*TP1_CLOSE_PCT/_QTY_STEP)*_QTY_STEP, _QTY_PREC), _MIN_QTY)
                place_order(self.client, tp_side, q1, reduce_only=True)
                self.qty_remain   = round(qty - q1, _QTY_PREC)
                self.tp1_hit      = True
                q2 = max(round(math.floor(qty*TP2_CLOSE_PCT/_QTY_STEP)*_QTY_STEP, _QTY_PREC), _MIN_QTY)
                r2 = place_limit(self.client, tp_side, q2, tp2, reduce_only=True)
                if r2 and r2.get("retCode") == 0:
                    self.tp2_order_id = r2["result"]["orderId"]
                tg(f"🚨 *CATCH-UP {direction.upper()} {SYMBOL}*\n"
                   f"TP1 passed → closed 80% @ market\nTP2 limit @ `{tp2}`")

            else:
                # Neither TP passed — place both limit orders
                q1 = max(round(math.floor(qty*TP1_CLOSE_PCT/_QTY_STEP)*_QTY_STEP, _QTY_PREC), _MIN_QTY)
                r1 = place_limit(self.client, tp_side, q1, tp1, reduce_only=True)
                if r1 and r1.get("retCode") == 0:
                    self.tp1_order_id = r1["result"]["orderId"]
                q2 = max(round(math.floor(qty*TP2_CLOSE_PCT/_QTY_STEP)*_QTY_STEP, _QTY_PREC), _MIN_QTY)
                r2 = place_limit(self.client, tp_side, q2, tp2, reduce_only=True)
                if r2 and r2.get("retCode") == 0:
                    self.tp2_order_id = r2["result"]["orderId"]
                set_sl(self.client, sl, direction=direction)
                tg(f"♻️ *RECONNECTED {direction.upper()} {SYMBOL}*\n"
                   f"Entry:`{entry}`  Qty:`{qty}`  uPnL:`{upnl:+.4f}`\n"
                   f"TP1:`{tp1}` | TP2:`{tp2}` | SL:`{sl}`")

            self._save_state()
        except Exception as e:
            log.warning(f"[DETECT] {e}")

    # ── Main loop ─────────────────────────────────────────────────
    def run(self):
        mode = "LIVE ⚡" if LIVE_TRADING else "PAPER 📄"
        log.info(f"{SYMBOL} | {INTERVAL}m | {LEVERAGE}x | {mode}")
        tg(f"🚀 *{SYMBOL} SHACKOBOT STARTED*  `{mode}`\n"
           f"TF: `{INTERVAL}m`  Lev: `{LEVERAGE}x`  Risk: `{RISK_PCT*100:.1f}%`\n"
           f"SL: `-{SL_PCT*100*LEVERAGE:.0f}%` lev (-{SL_PCT*100:.1f}% price)\n"
           f"TP1: `+{TP1_PCT*100*LEVERAGE:.0f}%` lev → close 80%  (SL stays)\n"
           f"TP2: `+{TP2_PCT*100*LEVERAGE:.0f}%` lev → close 10%  (SL→BE + trail)\n"
           f"Rider: `{RIDER_TRAIL_PCT*100*LEVERAGE:.0f}%` lev trailing gap  (10% position)\n"
           f"Filters: BODY · SUPERT · CHOP · HMACD(4H) · VWAP")

        _clock_tick = 0

        while True:
            try:
                # Periodic clock re-sync (every 10 polls)
                _clock_tick += 1
                if _clock_tick >= 10:
                    _clock_tick = 0
                    old = _clock_offset
                    sync_clock()
                    if abs(_clock_offset - old) > 0.5:
                        log.info("[CLOCK] Drift corrected — rebuilding client")
                        self.client = get_client()

                # Refresh HTF candles every 4 hours
                if time.time() - self._htf_last > 14400:
                    self._htf_df   = fetch_htf(self.client)
                    self._htf_last = time.time()
                    log.info(f"[HTF] Refreshed: {len(self._htf_df)} 4H bars")

                df = fetch_candles(self.client, limit=WARMUP_BARS + 10)
                if df.empty:
                    time.sleep(POLL_SECONDS); continue

                df     = compute_indicators(df)
                signal = get_signal(df)
                price  = float(df.iloc[-1]["close"])

                # External close guard (3-strike)
                pos = None
                if self.in_trade and LIVE_TRADING:
                    pos = get_position(self.client)
                    if pos is None:
                        self._ext_strikes += 1
                        log.warning(f"[EXT_CLOSE] Strike {self._ext_strikes}/3")
                        if self._ext_strikes >= 3:
                            bar_ts = int(df.iloc[-1]["timestamp"].timestamp() * 1000)
                            log.warning("[EXT_CLOSE] Confirmed — resetting state")
                            tg(f"⚠️ *{SYMBOL} external close confirmed*\nPosition gone 3x in a row")
                            self._last_bar_ts = bar_ts
                            self._ext_strikes = 0
                            self._reset()
                    else:
                        self._ext_strikes = 0

                log.info(
                    f"[{SYMBOL}] ${price:.{_PRICE_PREC}f} | sig={signal} | "
                    f"in_trade={self.in_trade} | W{self.wins}/L{self.losses}"
                    + (f" | {self.direction.upper()} @ {self.entry_price:.{_PRICE_PREC}f}"
                       if self.in_trade else "")
                )

                if self.in_trade:
                    self.manage_trade(price, signal, cached_pos=pos)
                elif signal != "neutral":
                    bar_ts = int(df.iloc[-1]["timestamp"].timestamp() * 1000)
                    if bar_ts == self._last_bar_ts:
                        log.info("[ENTRY] Blocked — same bar as last close")
                    else:
                        passed, blockers = apply_filters(df, signal, self._htf_df)
                        if passed:
                            self.enter_trade(signal, price)
                        else:
                            log.info(f"[FILTERED] {signal.upper()} → {', '.join(blockers)}")

                self._save_state()
                time.sleep(POLL_SECONDS)

            except KeyboardInterrupt:
                tg(f"🛑 *{SYMBOL} STOPPED*  W{self.wins}/L{self.losses}")
                log.info("Stopped."); break
            except Exception as e:
                log.error(f"Loop error: {e}", exc_info=True)
                tg(f"⚠️ *ERROR {SYMBOL}*\n`{str(e)[:200]}`")
                time.sleep(POLL_SECONDS * 3)

# ══════════════════════════════════════════════════════════════════
#  PID LOCK  (prevents double instance)
# ══════════════════════════════════════════════════════════════════
def _acquire_lock():
    lock = _STATE_FILE.replace(".json", ".lock")
    if os.path.exists(lock):
        try:
            pid = int(open(lock).read().strip())
            import psutil
            if psutil.pid_exists(pid):
                print(f"[LOCK] Already running (PID {pid}) — exiting"); sys.exit(0)
        except Exception:
            pass
    open(lock, "w").write(str(os.getpid()))
    import atexit
    atexit.register(lambda: os.path.exists(lock) and os.remove(lock))

# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║  SHACKOBOT  |  {SYMBOL:<20}  |  {INTERVAL}m  |  {LEVERAGE}x          ║
╠══════════════════════════════════════════════════════════════════╣
║  Risk     : {RISK_PCT*100:.1f}%   Leverage : {LEVERAGE}x                        ║
║  SL       : -{SL_PCT*100*LEVERAGE:.0f}% lev (-{SL_PCT*100:.1f}% price)                       ║
║  TP1      : +{TP1_PCT*100*LEVERAGE:.0f}% lev → close 80%  (SL stays)                  ║
║  TP2      : +{TP2_PCT*100*LEVERAGE:.0f}% lev → close 10%  (SL→BE, rider starts)       ║
║  Rider    : 10% position, {RIDER_TRAIL_PCT*100*LEVERAGE:.0f}% lev trailing gap                  ║
║  Signal   : SMA 20/50/100/200 + MACD {MACD_FAST}/{MACD_SLOW}/{MACD_SIGNAL}              ║
║  Filters  : BODY({BODY_MIN_PCT*100:.0f}%) SUPERT CHOP(<{CHOP_MAX:.0f}) VWAP HMACD(4H)  ║
║  Log      : {_LOG_FILE:<52}║
╚══════════════════════════════════════════════════════════════════╝
""")
    if not LIVE_TRADING:
        print("  Mode: PAPER — no real orders\n")
    else:
        print("  Mode: LIVE — REAL MONEY\n")
        if not API_KEY:
            print("  Set BYBIT_API_KEY and BYBIT_API_SECRET first")
            sys.exit(1)

    _acquire_lock()
    MergedBot().run()
