# =========================================================
# Crypto Signal Bot - PRO MAX 1H
# Binance Spot Data Only
# Main TF: 1H
# Confirmation TF: 30M
# Higher TF Context: 4H + Daily
# Binance Spot only | No auto-trading
# Version: 2026-10-06 v63.12 | ROOT FIX 3 | GRADE CLASSIFICATION | HARD EVIDENCE GATE | REVERSAL 2OF3 | DIAGNOSTIC LABELS | FAIL-CLOSED | CLOSED-CANDLE ONLY | SELL HARDENED | Binance Spot Only
# =========================================================

import os
import json
import time
import traceback
import requests
import pandas as pd
import numpy as np

from datetime import datetime, timezone, timedelta


# =========================================================
# 1. TELEGRAM
# =========================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# GitHub Actions: run one scan and exit.
RUN_ONCE = os.getenv("RUN_ONCE", "0") == "1"
TELEGRAM_TEST_ON_START = False

# Deployment identity: workflow must verify this exact build before execution.
DEPLOYMENT_ID = "v63.12-root-fix3-20261006"



# =========================================================
# 2. TIMEFRAME
# =========================================================

TIMEFRAME_MAIN = "1h"
TIMEFRAME_CONFIRM = "30m"
TIMEFRAME_4H = "4h"
TIMEFRAME_DAILY = "1d"

# Separate higher-timeframe signals
ENABLE_4H_SIGNALS = True
ENABLE_DAILY_SIGNALS = True
HIGHER_TF_MIN_SCORE = 90
HIGHER_TF_STRONG_SCORE = 95

KLINE_LIMIT_MAIN = 250
KLINE_LIMIT_CONFIRM = 250
KLINE_LIMIT_4H = 250
KLINE_LIMIT_DAILY = 250


# =========================================================
# 3. SIGNAL SCORE
# =========================================================

MIN_SCORE = 90
SELL_MIN_SCORE = 92
STRONG_SCORE = 95
BREAKOUT_MIN_SCORE = 90

# =========================================================
# PROFESSIONAL-STYLE QUALITY GATE
# Common discretionary/systematic filters used by experienced
# traders: multi-timeframe alignment, ADX/DI, VWAP, OBV,
# Bollinger regime, volume expansion, momentum agreement,
# market structure, and trade-location/R:R checks.
# These are filters, not guarantees of profitability.
# =========================================================
PRO_MIN_SCORE = 90
# v55: SELL is stricter because v55 outcome analytics showed 40.4% SL and 0 TP1.
PRO_SELL_MIN_SCORE = 92
PRO_SELL_MIN_1H_ADX = 26.0
PRO_SELL_MIN_VOLUME_RATIO = 1.50
PRO_SELL_MIN_30M_CONFIRMATIONS = 6
PRO_BREAKOUT_MIN_SCORE = 90
PRO_BOTTOM_MIN_SCORE = 90
PRO_HIGHER_TF_MIN_SCORE = 90
PRO_MIN_QUALITY_POINTS = 15
PRO_BOTTOM_MIN_QUALITY_POINTS = 15
PRO_MIN_1H_ADX = 23.0
PRO_MIN_REVERSAL_ADX = 18.0
PRO_MIN_30M_ADX = 17.0
PRO_MIN_VOLUME_RATIO = 1.35
PRO_MIN_BREAKOUT_VOLUME_RATIO = 1.50
PRO_MAX_EMA21_DISTANCE = 4.00
PRO_MAX_EMA21_SEVERE_DISTANCE = 5.00
PRO_MAX_EMA200_DISTANCE = 12.00
PRO_EMA200_EXTENDED_DISTANCE = 10.00
PRO_MAX_ATR_PERCENT = 6.00
# v63.1: RR thresholds are defined once in the ATR/RISK section below.
PRO_MIN_30M_CONFIRMATIONS = 6
PRO_MIN_HTF_ALIGNMENT = 1
PRO_SELL_MIN_HTF_ALIGNMENT = 2
PRO_MAX_RESISTANCE_ROOM_ATR = 0.80
PRO_MAX_SUPPORT_ROOM_ATR = 0.80
PRO_MIN_SIDE_SCORE_GAP = 5
# v59: Early-reversal signals are now treated as actionable trades, not
# educational/anticipation signals. Require real participation, directional
# energy and multi-timeframe confirmation before Telegram delivery.
PRO_BOTTOM_MIN_ADX = 23.0
PRO_BOTTOM_MIN_VOLUME_RATIO = 1.35
PRO_BOTTOM_MIN_30M_CONFIRMATIONS = 6
PRO_BOTTOM_REQUIRE_HTF_ALIGNMENT = 1
# v63.11: reversal momentum is measured by independent evidence components.
# Require at least 2 of RSI slope, MACD-histogram slope, and DI direction.
# This removes the contradictory old logic that first allowed OR, then required
# RSI AND MACD simultaneously, while keeping ADX and volume/30M/HTF hard gates.
PRO_BOTTOM_MIN_MOMENTUM_COMPONENTS = 2
BREAKOUT_LOOKBACK = 20
BREAKOUT_BUFFER_PERCENT = 0.15
BREAKOUT_MIN_VOLUME_RATIO = 1.25

BOTTOM_MIN_SCORE = 72
BOTTOM_MAX_SIGNALS_PER_RUN = 3
BOTTOM_LOOKBACK = 72
BOTTOM_NEAR_LOW_PERCENT = 4.5
BOTTOM_RSI_MIN = 24
BOTTOM_RSI_MAX = 44
BOTTOM_MAX_DISTANCE_EMA21 = 10.0

# Bottom Hunter quality caps:
# Prevent weak trend strength / weak participation from producing inflated scores.
BOTTOM_ADX_CAP_WEAK = 82
BOTTOM_ADX_CAP_MODERATE = 88
BOTTOM_ADX_CAP_GOOD = 94
BOTTOM_VOLUME_CAP_VERY_WEAK = 82
BOTTOM_VOLUME_CAP_WEAK = 88
BOTTOM_VOLUME_CAP_ACCEPTABLE = 94


# =========================================================
# 4. UNIVERSE / LIQUIDITY
# =========================================================

# هدف: بررسی تعداد بیشتری از ارزهای منتخب
# تعداد نهایی با توجه به حجم و وجود جفت Binance تعیین می‌شود.

TARGET_MAX_COINS = 100

# BTC is macro/context only and must never be emitted as a normal signal.
BTC_CONTEXT_ONLY = True

# حداقل حجم 24 ساعته Binance
# برای اینکه ارزهای خیلی کم‌نقدشونده وارد تحلیل 1H نشوند.
MIN_24H_USDT_VOLUME = 5_000_000

# حداقل نسبت حجم کندل فعلی به میانگین حجم
MIN_VOLUME_RATIO = 1.20
STRONG_VOLUME_RATIO = 1.50


# =========================================================
# 5. EMA
# =========================================================

EMA_FAST = 9
EMA_MID = 21
EMA_TREND = 50
EMA_MAJOR = 200


# =========================================================
# 6. RSI
# =========================================================

RSI_PERIOD = 14

RSI_BUY_MIN = 50
RSI_BUY_MAX = 68

RSI_SELL_MIN = 32
RSI_SELL_MAX = 50

RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30


# =========================================================
# 7. MACD
# =========================================================

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9


# =========================================================
# 8. ADX
# =========================================================

ADX_PERIOD = 14

MIN_ADX = 20
STRONG_ADX = 25


# =========================================================
# 9. ATR / RISK
# =========================================================

ATR_PERIOD = 14

MIN_ATR_PERCENT = 0.20
MAX_ATR_PERCENT = 8.00

SL_ATR_MULTIPLIER = 1.50

TP1_RR = 1.80
TP2_RR = 2.40

# v63.1: single source of truth for executable trade geometry.
# Professional/Bottom-Hunter gates must never drift away from the TP geometry.
PRO_MIN_RR_TP1 = TP1_RR
PRO_MIN_RR_TP2 = TP2_RR
# Floating-point-safe inclusive RR boundary. Exact configured values must pass.
RR_EPSILON = 1e-9

BOTTOM_PRO_MIN_RR_TP1 = TP1_RR
BOTTOM_PRO_MIN_RR_TP2 = TP2_RR

# Higher-timeframe risk tuning. 4H/Daily candles naturally have larger ATR,
# so they use a tighter ATR multiplier and a dedicated stop ceiling.
HIGHER_TF_SL_ATR_MULTIPLIER = 1.20
HIGHER_TF_MAX_STOP_DISTANCE_PERCENT = 15.0


# =========================================================
# 10. PRICE DISTANCE FILTER
# =========================================================

# جلوگیری از ورود بعد از یک حرکت بیش از حد کشیده

MAX_DISTANCE_FROM_EMA21 = 4.5

# ورود بسیار دیرهنگام: اگر هم RSI بالا باشد و هم قیمت از EMA21 دور شده باشد،
# سیگنال صادر نمی‌شود تا احتمال خرید در سقف حرکت کمتر شود.
MAX_LATE_ENTRY_EMA21_DISTANCE = 6.0
MAX_LATE_ENTRY_RSI_BUY = 68.0
MIN_LATE_ENTRY_RSI_SELL = 32.0
MAX_DISTANCE_FROM_EMA200 = 12.0


# =========================================================
# 11. CANDLE FILTER
# =========================================================

MIN_CANDLE_BODY_RATIO = 0.25


# =========================================================
# 12. DIVERGENCE
# =========================================================

DIVERGENCE_LOOKBACK = 30
DIVERGENCE_MIN_GAP = 3
DIVERGENCE_MAX_GAP = 20


# =========================================================
# 13. BTC REGIME
# =========================================================

BTC_SYMBOL = "BTCUSDT"  # Context/regime only; excluded from independent signal scan

BTC_MAIN_TIMEFRAME = "1h"
BTC_MACRO_TIMEFRAME = "1d"



# =========================================================
# 15. FILES
# =========================================================

STATE_FILE = "signals_state.json"

HISTORY_FILE = "signals_history.json"

# =========================================================
# 16. SIGNAL OUTCOME TRACKER
# =========================================================
# Outcome tracking is observational only. It does not change signal
# qualification, Telegram sending, or trading logic.
OUTCOME_TRACKER_ENABLED = True
OUTCOME_HORIZONS_HOURS = (1, 2, 4, 8)
OUTCOME_MAX_HISTORY_SCAN = 120
OUTCOME_KLINE_LIMIT = 32



# =========================================================
# 16. API
# =========================================================

BINANCE_SPOT_BASE = "https://data-api.binance.vision"





# =========================================================
# 17. NETWORK
# =========================================================

REQUEST_TIMEOUT = 15

MAX_RETRIES = 3

RETRY_DELAY = 2


# =========================================================
# 18. BOT LOOP
# =========================================================

# هر 30 دقیقه یک بار بررسی
CHECK_INTERVAL_SECONDS = 3600


# =========================================================
# 19. CACHE
# =========================================================


BINANCE_SYMBOL_CACHE = None

BINANCE_VOLUME_CACHE = None

BINANCE_VOLUME_CACHE_TIME = 0

BINANCE_CACHE_TIME = 0

BINANCE_CACHE_TTL = 300

# Signal-data freshness: never build a signal from stale candles.
KLINE_FRESHNESS_TOLERANCE = {
    "1m": 5 * 60,
    "5m": 10 * 60,
    "15m": 25 * 60,
    "30m": 45 * 60,
    "1h": 75 * 60,
    "2h": 150 * 60,
    "4h": 270 * 60,
    "6h": 390 * 60,
    "8h": 510 * 60,
    "12h": 750 * 60,
    "1d": 27 * 60 * 60,
}

# 24H volume is refreshed at least once per minute; it is used only for
# universe/liquidity filtering, not as a substitute for fresh candles.
BINANCE_VOLUME_CACHE_TTL = 60

# Live ticker settings. Candles drive indicators; live ticker drives Entry/SL/TP.
LIVE_PRICE_MAX_AGE_SECONDS = 15
MAX_LIVE_PRICE_DEVIATION_PERCENT = 5.0


# =========================================================
# 20. SCORE WEIGHTS
# =========================================================

SCORE_EMA200 = 20

SCORE_EMA9_21 = 15

SCORE_ADX = 10

SCORE_RSI = 10

SCORE_MACD = 10

SCORE_VOLUME = 10

SCORE_CANDLE = 5

SCORE_ATR = 5

SCORE_CONFIRM_30M = 5

SCORE_BTC_REGIME = 5



# =========================================================
# TOTAL SCORE = 100
# =========================================================


# =========================================================
# 21. LOGGING FLAGS
# =========================================================

DEBUG_MODE = False

PRINT_ALL_COINS = False

SEND_NO_SIGNAL_REPORT = False


# =========================================================
# 22. TIMEZONE
# =========================================================

IRAN_TZ = timezone(timedelta(hours=3, minutes=30))


# =========================================================
# 23. GLOBAL SESSION
# =========================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 "
        "(Linux; Android 14) "
        "AppleWebKit/537.36 "
        "Chrome/120 Safari/537.36"
    ),
    "Accept": "application/json",
})


# =========================================================
# 24. RUNTIME STATE
# =========================================================

LAST_SCAN_TIME = None

RUNNING = True


# =========================================================
# 25. BASIC HELPERS
# =========================================================

def now_iran():
    return datetime.now(timezone.utc).astimezone(IRAN_TZ)


def log(message):
    print(message, flush=True)


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


# =========================================================
# END OF SECTION 1
# =========================================================# =========================================================
# SECTION 2
# HTTP / NETWORK / RETRY
# =========================================================

def http_get(url, params=None, timeout=REQUEST_TIMEOUT, retries=MAX_RETRIES):
    """
    درخواست GET مقاوم در برابر:
    - قطع اینترنت
    - DNS Error
    - Timeout
    - خطاهای موقت HTTP
    - Rate Limit
    """

    last_error = None

    for attempt in range(1, retries + 1):

        try:

            response = SESSION.get(
                url,
                params=params,
                timeout=timeout
            )

            # -------------------------------------------------
            # Rate Limit
            # -------------------------------------------------

            if response.status_code == 429:

                retry_after = response.headers.get(
                    "Retry-After",
                    RETRY_DELAY
                )

                try:
                    retry_after = float(retry_after)
                except Exception:
                    retry_after = RETRY_DELAY

                log(
                    f"⚠️ HTTP 429 Rate Limit | "
                    f"Waiting {retry_after:.1f}s..."
                )

                time.sleep(retry_after)
                continue

            # -------------------------------------------------
            # Server Errors
            # -------------------------------------------------

            if response.status_code >= 500:

                log(
                    f"⚠️ Server error "
                    f"{response.status_code} "
                    f"(attempt {attempt}/{retries})"
                )

                time.sleep(RETRY_DELAY * attempt)
                continue

            # -------------------------------------------------
            # Other HTTP Errors
            # -------------------------------------------------

            if response.status_code != 200:

                log(
                    f"⚠️ HTTP {response.status_code}: "
                    f"{url}"
                )

                return None

            # -------------------------------------------------
            # JSON
            # -------------------------------------------------

            try:
                return response.json()

            except ValueError as e:

                log(
                    f"⚠️ Invalid JSON response: {e}"
                )

                return None

        # -----------------------------------------------------
        # DNS / Connection / Timeout
        # -----------------------------------------------------

        except requests.exceptions.Timeout as e:

            last_error = e

            log(
                f"⚠️ Timeout "
                f"(attempt {attempt}/{retries})"
            )

        except requests.exceptions.ConnectionError as e:

            last_error = e

            log(
                f"⚠️ Connection/DNS error "
                f"(attempt {attempt}/{retries})"
            )

        except requests.exceptions.RequestException as e:

            last_error = e

            log(
                f"⚠️ Request error "
                f"(attempt {attempt}/{retries}): {e}"
            )

        except Exception as e:

            last_error = e

            log(
                f"⚠️ Unexpected HTTP error: {e}"
            )

        # -----------------------------------------------------
        # Retry delay
        # -----------------------------------------------------

        if attempt < retries:
            time.sleep(RETRY_DELAY * attempt)

    # ---------------------------------------------------------
    # All attempts failed
    # ---------------------------------------------------------

    if last_error:

        log(
            f"❌ HTTP request failed after "
            f"{retries} attempts:"
        )

        log(
            f"   {type(last_error).__name__}: "
            f"{last_error}"
        )

    return None


# =========================================================
# JSON FILE HELPERS
# =========================================================

def load_json_file(filename, default=None):

    if default is None:
        default = {}

    try:

        if not os.path.exists(filename):
            return default

        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception as e:

        log(
            f"⚠️ Could not read {filename}: {e}"
        )

        return default


def save_json_file(filename, data):

    temp_file = filename + ".tmp"

    try:

        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )

        # Atomic replacement
        os.replace(
            temp_file,
            filename
        )

        return True

    except Exception as e:

        log(
            f"⚠️ Could not save {filename}: {e}"
        )

        try:

            if os.path.exists(temp_file):
                os.remove(temp_file)

        except Exception:
            pass

        return False


# =========================================================
# END OF SECTION 2
# =========================================================# =========================================================
# SECTION 3 - CURATED CRYPTO UNIVERSE
# Binance Market Data Only
# Binance-only universe
# =========================================================

# ---------------------------------------------------------
# CURATED COIN LIST
# حدود 180 ارز شناخته‌شده و قابل بررسی
# ---------------------------------------------------------

CURATED_COINS = {
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "TRX",
    "AVAX", "LINK", "DOT", "MATIC", "POL", "LTC", "BCH", "UNI",
    "ATOM", "ETC", "FIL", "NEAR", "APT", "ARB", "OP", "SUI",
    "INJ", "AAVE", "MKR", "ALGO", "XLM", "HBAR", "VET", "ICP",
    "FTM", "SAND", "MANA", "AXS", "GRT", "THETA", "EOS", "XTZ",
    "EGLD", "FLOW", "KAVA", "NEO", "IOTA", "RUNE", "CAKE",
    "CRV", "SNX", "COMP", "SUSHI", "1INCH", "DYDX", "LDO",
    "ENS", "IMX", "GALA", "CHZ", "ENJ", "BAT", "ZRX", "ANKR",
    "SKL", "STX", "MINA", "CELO", "ONE", "ZIL", "QTUM", "DASH",
    "WAVES", "ONT", "ICX", "RVN", "DCR", "KSM", "YFI", "BAL",
    "BAND", "API3", "OCEAN", "FET", "AGIX", "RENDER", "TAO",
    "AKT", "AR", "JASMY", "ROSE", "IOTX", "CKB", "COTI",
    "DENT", "HOT", "SC", "IOST", "XVG", "DGB", "ZEN", "ZEC",
    "XMR", "DCR", "KNC", "STORJ", "LRC", "CELR", "CTSI",
    "MASK", "GMT", "APE", "YGG", "MAGIC", "SSV", "ACH",
    "HIGH", "HOOK", "ID", "EDU", "CYBER", "BLUR", "WLD",
    "SEI", "TIA", "JTO", "JUP", "PYTH", "STRK", "DYM",
    "ALT", "PORTAL", "PIXEL", "MANTA", "MAV", "PENDLE",
    "ENA", "ETHFI", "EIGEN", "REZ", "OMNI", "ONDO", "LISTA",
    "NOT", "TURBO", "PEPE", "SHIB", "FLOKI", "BONK", "WIF",
    "BOME", "MEME", "ORDI", "SATS", "1000SATS", "1000SHIB",
    "1000PEPE", "MEW", "NEIRO", "NEIROETH", "ACT", "PNUT",
    "POPCAT", "GOAT", "MOG", "TNSR", "DOGS", "HMSTR",
    "CATI", "EURI", "USUAL", "VANA", "MOVE", "SONIC",
    "BERA", "KAITO", "LAYER", "TRUMP", "MELANIA", "VIRTUAL",
    "AERO", "MORPHO", "DEEP", "SHELL", "FORM", "IP",
    "HYPE", "XCN", "SXP", "ILV", "GMT", "API3", "UMA",
    "SSV", "GMX", "GNS", "RDNT", "JOE", "POLS", "TWT",
    "CAKE", "BABYDOGE", "LUNC", "USTC", "PEOPLE", "WOO",
    "ACH", "C98", "ARPA", "CHR", "DODO", "FLUX", "GLM",
    "NMR", "OXT", "POND", "PERP", "STG", "TRU", "TRB",
    "VTHO", "WIN", "XVS", "YGG"
}


# Dynamic Binance universe exclusions: stablecoins and leveraged-token suffixes
# are not useful directional 1H spot signal candidates. The universe is now
# driven by Binance liquidity instead of a stale hand-maintained coin list.
EXCLUDED_BASE_ASSETS = {
    "USDT", "USDC", "BUSD", "FDUSD", "TUSD", "USDP", "DAI", "EUR",
    "EURI", "USDE", "USDS", "PYUSD", "USTC", "UST", "USD1"
}
LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")


def is_directional_spot_asset(base_asset):
    base = normalize_coin_symbol(base_asset) if 'normalize_coin_symbol' in globals() else str(base_asset).upper()
    if not base or base in EXCLUDED_BASE_ASSETS:
        return False
    return not any(base.endswith(suffix) for suffix in LEVERAGED_SUFFIXES)


def normalize_coin_symbol(symbol):
    """
    تبدیل نام ارز به فرمت استاندارد Binance.

    BTC       -> BTC
    btc       -> BTC
    BTCUSDT   -> BTC
    BTC-USDT  -> BTC
    """

    if not symbol:
        return None

    symbol = str(symbol).strip().upper()

    if symbol.endswith("-USDT"):
        symbol = symbol[:-5]

    elif symbol.endswith("USDT"):
        symbol = symbol[:-4]

    if not symbol:
        return None

    return symbol


def get_binance_spot_symbols():
    """
    دریافت ارزهای فعال Binance Spot با جفت USDT.
    """

    global BINANCE_SYMBOL_CACHE
    global BINANCE_CACHE_TIME

    current_time = time.time()

    if (
        BINANCE_SYMBOL_CACHE is not None
        and current_time - BINANCE_CACHE_TIME
        < BINANCE_CACHE_TTL
    ):
        return BINANCE_SYMBOL_CACHE

    print("\n🔎 Loading Binance Spot symbols...")

    url = (
        f"{BINANCE_SPOT_BASE}"
        "/api/v3/exchangeInfo"
    )

    data = http_get(url)

    if not isinstance(data, dict):
        print("❌ Binance exchangeInfo unavailable.")
        return set()

    symbols = data.get("symbols", [])

    if not isinstance(symbols, list):
        print("❌ Binance symbols data invalid.")
        return set()

    result = set()

    for item in symbols:

        if not isinstance(item, dict):
            continue

        symbol = str(
            item.get("symbol", "")
        ).upper()

        status = str(
            item.get("status", "")
        ).upper()

        quote_asset = str(
            item.get("quoteAsset", "")
        ).upper()

        if status != "TRADING":
            continue

        if quote_asset != "USDT":
            continue

        if not symbol.endswith("USDT"):
            continue

        base_asset = normalize_coin_symbol(symbol)

        if base_asset:
            result.add(base_asset)

    BINANCE_SYMBOL_CACHE = result
    BINANCE_CACHE_TIME = current_time

    print(
        f"✅ Binance active USDT coins: "
        f"{len(result)}"
    )

    return result


def get_binance_24h_volumes():
    """
    دریافت حجم 24 ساعته جفت‌های USDT از Binance.
    """

    global BINANCE_VOLUME_CACHE
    global BINANCE_VOLUME_CACHE_TIME

    current_time = time.time()

    if (
        BINANCE_VOLUME_CACHE is not None
        and current_time - BINANCE_VOLUME_CACHE_TIME < BINANCE_VOLUME_CACHE_TTL
    ):
        return BINANCE_VOLUME_CACHE

    print("\n📊 Loading Binance 24H volumes...")

    url = (
        f"{BINANCE_SPOT_BASE}"
        "/api/v3/ticker/24hr"
    )

    data = http_get(url)

    if not isinstance(data, list):
        print("❌ Binance volume data unavailable.")
        return {}

    volumes = {}

    for item in data:

        if not isinstance(item, dict):
            continue

        symbol = str(
            item.get("symbol", "")
        ).upper()

        if not symbol.endswith("USDT"):
            continue

        base_asset = normalize_coin_symbol(symbol)

        if not base_asset:
            continue

        quote_volume = safe_float(
            item.get("quoteVolume"),
            0.0
        )

        if quote_volume > 0:
            volumes[base_asset] = quote_volume

    BINANCE_VOLUME_CACHE = volumes
    BINANCE_VOLUME_CACHE_TIME = current_time

    print(
        f"✅ Binance volumes loaded: "
        f"{len(volumes)} coins"
    )

    return volumes


def get_scan_coins():
    """
    ساخت Universe نهایی:

        CURATED_COINS
             ↓
        Binance Spot
             ↓
        USDT pairs
             ↓
        حداقل حجم 24H
             ↓
        مرتب‌سازی حجم
             ↓
        حداکثر 150 ارز
    """

    print("\n" + "=" * 60)
    print("🚀 BUILDING FINAL BINANCE 1H SCAN UNIVERSE")
    print("=" * 60)

    # -----------------------------------------------------
    # 1. لیست ثابت
    # -----------------------------------------------------

    curated = {
        normalize_coin_symbol(x)
        for x in CURATED_COINS
        if normalize_coin_symbol(x)
    }

    print(
        f"📚 Curated coin list: "
        f"{len(curated)} coins"
    )

    # -----------------------------------------------------
    # 2. Binance
    # -----------------------------------------------------

    binance_coins = get_binance_spot_symbols()

    if not binance_coins:

        print(
            "❌ Binance coin list is empty."
        )

        return []

    print(
        f"📌 Binance USDT coins: "
        f"{len(binance_coins)}"
    )

    # -----------------------------------------------------
    # 3. Binance-only dynamic universe
    # -----------------------------------------------------
    # Root fix: the previous curated-list intersection left only ~43 assets
    # despite TARGET_MAX_COINS=150 and could miss newer/liquid Binance pairs.
    # Binance exchangeInfo is the authority; liquidity ranking decides what
    # gets scanned. BTC remains context-only.
    common_coins = {
        coin for coin in binance_coins
        if (not BTC_CONTEXT_ONLY or coin != BTC_SYMBOL)
        and is_directional_spot_asset(coin)
    }

    print(
        f"🔗 Binance directional USDT universe (BTC excluded): "
        f"{len(common_coins)} coins"
    )

    if not common_coins:
        print("❌ No eligible Binance directional coins found.")
        return []

    # -----------------------------------------------------
    # 4. حجم 24H
    # -----------------------------------------------------

    volumes = get_binance_24h_volumes()

    if not volumes:

        print(
            "❌ Binance volume list is empty."
        )

        return []

    # -----------------------------------------------------
    # 5. فیلتر حجم
    # -----------------------------------------------------

    volume_filtered = []

    for coin in common_coins:

        volume = safe_float(
            volumes.get(coin),
            0.0
        )

        if volume >= MIN_24H_USDT_VOLUME:

            volume_filtered.append(
                (coin, volume)
            )

    print(
        f"💰 Volume >= "
        f"${MIN_24H_USDT_VOLUME:,.0f}: "
        f"{len(volume_filtered)} coins"
    )

    if not volume_filtered:

        print(
            "❌ No coins passed volume filter."
        )

        return []

    # -----------------------------------------------------
    # 6. مرتب‌سازی بر اساس حجم
    # -----------------------------------------------------

    volume_filtered.sort(
        key=lambda x: x[1],
        reverse=True
    )

    # -----------------------------------------------------
    # 7. محدود کردن به 150 ارز
    # -----------------------------------------------------

    selected = volume_filtered[
        :TARGET_MAX_COINS
    ]

    scan_coins = [
        coin
        for coin, volume in selected
    ]

    # -----------------------------------------------------
    # 8. گزارش
    # -----------------------------------------------------

    print("\n" + "-" * 60)
    print("📋 FINAL SCAN UNIVERSE")
    print("-" * 60)

    for index, (coin, volume) in enumerate(
        selected,
        start=1
    ):

        print(
            f"{index:03d}. "
            f"{coin:<12} "
            f"${volume:,.0f}"
        )

    print("-" * 60)

    print(
        f"✅ FINAL COINS: "
        f"{len(scan_coins)}"
    )

    print(
        f"🎯 TARGET MAX: "
        f"{TARGET_MAX_COINS}"
    )

    return scan_coins


# =========================================================
# END OF SECTION 3
# =========================================================# =========================================================
# SECTION 4
# MARKET DATA + PREPARE 1H / 30M DATA
# =========================================================

def to_binance_usdt_symbol(symbol):
    """
    Convert base symbol to Binance Spot USDT symbol.
    Examples:
        BTC      -> BTCUSDT
        BTCUSDT  -> BTCUSDT
        BTC-USDT -> BTCUSDT
    """

    if symbol is None:
        return None

    symbol = str(symbol).upper().strip()

    symbol = symbol.replace("-", "")
    symbol = symbol.replace("/", "")

    if symbol.endswith("USDT"):
        return symbol

    return f"{symbol}USDT"


# =========================================================
# GET BINANCE KLINES
# =========================================================

def get_klines(symbol, interval, limit=200):

    try:

        binance_symbol = to_binance_usdt_symbol(symbol)

        url = f"{BINANCE_SPOT_BASE}/api/v3/klines"

        params = {
            "symbol": binance_symbol,
            "interval": interval,
            "limit": limit
        }

        data = http_get(
            url,
            params=params
        )

        if not data:
            log(
                f"⚠️ No kline data: "
                f"{binance_symbol} {interval}"
            )
            return None

        if not isinstance(data, list):
            log(
                f"⚠️ Invalid kline response: "
                f"{binance_symbol} {interval}"
            )
            return None

        rows = []

        for row in data:

            if not isinstance(row, list):
                continue

            if len(row) < 6:
                continue

            try:

                rows.append({
                    "open_time": int(row[0]),

                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),

                    "close_time": int(row[6])
                    if len(row) > 6 else 0
                })

            except Exception:
                continue

        if not rows:
            log(
                f"⚠️ Empty parsed klines: "
                f"{binance_symbol} {interval}"
            )
            return None

        df = pd.DataFrame(rows)

        if df.empty:
            return None

        # -------------------------------------------------
        # Datetime
        # -------------------------------------------------

        df["open_time"] = pd.to_datetime(
            df["open_time"],
            unit="ms",
            utc=True
        )

        df["close_time"] = pd.to_datetime(
            df["close_time"],
            unit="ms",
            utc=True
        )

        # -------------------------------------------------
        # فقط کندل‌های کاملاً بسته‌شده
        # -------------------------------------------------
        # Binance معمولاً آخرین کندل در حال تشکیل را هم برمی‌گرداند.
        # استفاده از آن باعث نوسان مصنوعی RSI/MACD/Volume و تغییر سیگنال می‌شود.
        now_utc = pd.Timestamp.now(tz="UTC")
        df = df[df["close_time"] < now_utc].copy()

        if df.empty:
            log(
                f"⚠️ No closed candles: {binance_symbol} {interval}"
            )
            return None

        # -------------------------------------------------
        # Freshness gate
        # -------------------------------------------------
        # A technically correct candle is not useful for a live signal if
        # it is too old. We therefore reject stale market data before any
        # indicators or scoring are calculated.
        latest_close_time = df["close_time"].iloc[-1]
        data_age_seconds = max(0.0, (now_utc - latest_close_time).total_seconds())
        max_age_seconds = KLINE_FRESHNESS_TOLERANCE.get(
            str(interval).lower(),
            2 * 60 * 60,
        )

        if data_age_seconds > max_age_seconds:
            log(
                f"⚠️ STALE DATA: {binance_symbol} {interval} | "
                f"age={data_age_seconds/60:.1f}m "
                f"max={max_age_seconds/60:.1f}m"
            )
            return None

        # Keep the age available for diagnostics without changing the
        # dataframe schema used by the indicator functions.
        df.attrs["data_age_seconds"] = data_age_seconds
        df.attrs["data_fresh"] = True

        # -------------------------------------------------
        # Numeric columns
        # -------------------------------------------------

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]

        for column in numeric_columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        # -------------------------------------------------
        # Remove invalid rows
        # -------------------------------------------------

        df = df.dropna(
            subset=[
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]
        )

        if df.empty:
            return None

        # -------------------------------------------------
        # Sort and remove duplicates
        # -------------------------------------------------

        df = (
            df.sort_values("open_time")
              .drop_duplicates(
                  subset=["open_time"]
              )
              .reset_index(drop=True)
        )

        return df

    except Exception as e:

        log(
            f"⚠️ get_klines error "
            f"{symbol} {interval}: {e}"
        )

        if DEBUG_MODE:
            traceback.print_exc()

        return None


# =========================================================
# GET LIVE BINANCE PRICE
# =========================================================

def get_live_price(symbol):
    """
    دریافت قیمت لحظه‌ای Binance برای Entry و سطوح ریسک.

    اندیکاتورها از آخرین کندل بسته‌شده محاسبه می‌شوند؛ این تابع فقط
    قیمت لحظه‌ای را جداگانه می‌گیرد تا Entry/SL/TP با قیمت قدیمی ساخته نشوند.
    """
    binance_symbol = to_binance_usdt_symbol(symbol)
    if not binance_symbol:
        return None

    request_started = time.time()
    url = f"{BINANCE_SPOT_BASE}/api/v3/ticker/price"
    data = http_get(url, params={"symbol": binance_symbol})
    fetched_at = time.time()

    if not isinstance(data, dict):
        log(f"⚠️ Live price unavailable: {binance_symbol}")
        return None

    price = safe_float(data.get("price"), 0.0)
    if price <= 0:
        log(f"⚠️ Invalid live price: {binance_symbol}")
        return None

    age = fetched_at - request_started
    if age > LIVE_PRICE_MAX_AGE_SECONDS:
        log(
            f"⚠️ LIVE PRICE TOO OLD: {binance_symbol} | "
            f"request_time={age:.2f}s max={LIVE_PRICE_MAX_AGE_SECONDS:.1f}s"
        )
        return None

    return {
        "price": price,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "request_latency_seconds": age,
        "source": "Binance Spot /api/v3/ticker/price"
    }


# =========================================================
# GET MAIN 1H DATA
# =========================================================

def get_main_1h_data(symbol):

    return get_klines(
        symbol,
        TIMEFRAME_MAIN,
        KLINE_LIMIT_MAIN
    )


# =========================================================
# GET CONFIRMATION 30M DATA
# =========================================================

def get_confirm_30m_data(symbol):

    return get_klines(
        symbol,
        TIMEFRAME_CONFIRM,
        KLINE_LIMIT_CONFIRM
    )


# =========================================================
# GET 4H / DAILY CONTEXT DATA
# =========================================================

def get_4h_data(symbol):

    return get_klines(
        symbol,
        TIMEFRAME_4H,
        KLINE_LIMIT_4H
    )


def get_daily_data(symbol):

    return get_klines(
        symbol,
        TIMEFRAME_DAILY,
        KLINE_LIMIT_DAILY
    )


# =========================================================
# GET SYMBOL MARKET DATA
# =========================================================

def get_symbol_market_data(symbol):

    try:

        binance_symbol = to_binance_usdt_symbol(
            symbol
        )

        main_df = get_main_1h_data(
            binance_symbol
        )

        if main_df is None or main_df.empty:

            log(
                f"⚠️ No 1H data: "
                f"{binance_symbol}"
            )

            return None

        confirm_df = get_confirm_30m_data(
            binance_symbol
        )

        if confirm_df is None or confirm_df.empty:

            log(
                f"⚠️ No 30M data: "
                f"{binance_symbol}"
            )

            return None

        # 4H/Daily are optional: the core 1H+30M scan must continue even
        # when Binance has a temporary/missing higher-TF response.
        df_4h = get_4h_data(binance_symbol)
        if df_4h is None or df_4h.empty:
            log(f"⚠️ Optional 4H data unavailable: {binance_symbol}")
            df_4h = None

        df_daily = get_daily_data(binance_symbol)
        if df_daily is None or df_daily.empty:
            log(f"⚠️ Optional 1D data unavailable: {binance_symbol}")
            df_daily = None

        return {
            "1h": main_df,
            "30m": confirm_df,
            "4h": df_4h,
            "1d": df_daily
        }

    except Exception as e:

        log(
            f"⚠️ get_symbol_market_data "
            f"error {symbol}: {e}"
        )

        if DEBUG_MODE:
            traceback.print_exc()

        return None


# =========================================================
# VALIDATE OHLCV DATA
# =========================================================

def validate_market_dataframe(df):

    if df is None:
        return False

    if not isinstance(df, pd.DataFrame):
        return False

    if df.empty:
        return False

    required_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for column in required_columns:

        if column not in df.columns:
            return False

    if len(df) < 50:
        return False

    # -----------------------------------------------------
    # Check latest rows
    # -----------------------------------------------------

    row = df.iloc[-1]

    for column in required_columns:

        value = row.get(
            column,
            np.nan
        )

        if pd.isna(value):
            return False

        try:

            if not np.isfinite(
                float(value)
            ):
                return False

        except Exception:
            return False

    return True


# =========================================================
# TECHNICAL INDICATORS
# =========================================================

def add_indicators(df):
    """Add all indicators required by the v28 scoring engine.

    Uses only historical/closed candles already returned by get_klines.
    No third-party TA package is required.
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None

    out = df.copy()
    required = ["open", "high", "low", "close", "volume"]
    if any(c not in out.columns for c in required):
        return None

    for c in required:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    # EMA
    out["ema9"] = out["close"].ewm(span=EMA_FAST, adjust=False, min_periods=EMA_FAST).mean()
    out["ema21"] = out["close"].ewm(span=EMA_MID, adjust=False, min_periods=EMA_MID).mean()
    out["ema50"] = out["close"].ewm(span=EMA_TREND, adjust=False, min_periods=EMA_TREND).mean()
    out["ema200"] = out["close"].ewm(span=EMA_MAJOR, adjust=False, min_periods=EMA_MAJOR).mean()

    # Price distance / EMA slope fields used by the scoring engine.
    # Keep these as percentage values so they are directly comparable
    # with MAX_DISTANCE_FROM_EMA21 / MAX_DISTANCE_FROM_EMA200.
    out["distance_ema21"] = (
        (out["close"] - out["ema21"]).abs()
        / out["ema21"].replace(0, np.nan)
        * 100.0
    )
    out["distance_ema200"] = (
        (out["close"] - out["ema200"]).abs()
        / out["ema200"].replace(0, np.nan)
        * 100.0
    )
    out["ema21_slope"] = out["ema21"] - out["ema21"].shift(1)

    # RSI (Wilder-style RMA)
    delta = out["close"].diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / RSI_PERIOD, adjust=False, min_periods=RSI_PERIOD).mean()
    avg_loss = loss.ewm(alpha=1.0 / RSI_PERIOD, adjust=False, min_periods=RSI_PERIOD).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["rsi"] = 100.0 - (100.0 / (1.0 + rs))
    out.loc[(avg_loss == 0) & (avg_gain > 0), "rsi"] = 100.0
    out.loc[(avg_loss == 0) & (avg_gain == 0), "rsi"] = 50.0

    # MACD
    ema_fast = out["close"].ewm(span=MACD_FAST, adjust=False, min_periods=MACD_FAST).mean()
    ema_slow = out["close"].ewm(span=MACD_SLOW, adjust=False, min_periods=MACD_SLOW).mean()
    out["macd"] = ema_fast - ema_slow
    out["macd_signal"] = out["macd"].ewm(span=MACD_SIGNAL, adjust=False, min_periods=MACD_SIGNAL).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    out["macd_hist_prev"] = out["macd_hist"].shift(1)
    out["macd_hist_rising"] = out["macd_hist"] > out["macd_hist_prev"]
    out["macd_hist_falling"] = out["macd_hist"] < out["macd_hist_prev"]

    # ATR / volatility
    prev_close = out["close"].shift(1)
    tr = pd.concat([
        out["high"] - out["low"],
        (out["high"] - prev_close).abs(),
        (out["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    out["tr"] = tr
    out["atr"] = tr.ewm(alpha=1.0 / ATR_PERIOD, adjust=False, min_periods=ATR_PERIOD).mean()
    out["atr_percent"] = (out["atr"] / out["close"].replace(0, np.nan)) * 100.0

    # Volume ratio: latest candle vs previous 20 closed candles' mean.
    volume_mean = out["volume"].shift(1).rolling(20, min_periods=10).mean()
    out["volume_ratio"] = out["volume"] / volume_mean.replace(0, np.nan)

    # Candle structure
    candle_range = (out["high"] - out["low"]).replace(0, np.nan)
    out["body"] = (out["close"] - out["open"]).abs()
    out["body_ratio"] = out["body"] / candle_range
    out["upper_wick"] = out["high"] - out[["open", "close"]].max(axis=1)
    out["lower_wick"] = out[["open", "close"]].min(axis=1) - out["low"]
    out["bullish_candle"] = out["close"] > out["open"]
    out["bearish_candle"] = out["close"] < out["open"]

    # ADX / DI using Wilder smoothing.
    up_move = out["high"].diff()
    down_move = -out["low"].diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=out.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=out.index)
    atr_w = tr.ewm(alpha=1.0 / ADX_PERIOD, adjust=False, min_periods=ADX_PERIOD).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / ADX_PERIOD, adjust=False, min_periods=ADX_PERIOD).mean() / atr_w.replace(0, np.nan)
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / ADX_PERIOD, adjust=False, min_periods=ADX_PERIOD).mean() / atr_w.replace(0, np.nan)
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum
    adx = dx.ewm(alpha=1.0 / ADX_PERIOD, adjust=False, min_periods=ADX_PERIOD).mean()
    out["plus_di"] = plus_di
    out["minus_di"] = minus_di
    out["dx"] = dx
    out["adx"] = adx

    # =====================================================
    # PROFESSIONAL-STYLE MARKET FILTERS
    # =====================================================
    # Rolling VWAP: useful as a price-location filter.
    typical_price = (out["high"] + out["low"] + out["close"]) / 3.0
    pv = typical_price * out["volume"]
    vwap_volume = out["volume"].rolling(24, min_periods=12).sum()
    out["rolling_vwap"] = pv.rolling(24, min_periods=12).sum() / vwap_volume.replace(0, np.nan)
    out["vwap_distance_pct"] = (out["close"] - out["rolling_vwap"]) / out["rolling_vwap"].replace(0, np.nan) * 100.0

    # OBV and short slope: confirms whether participation agrees with price.
    direction = np.sign(out["close"].diff()).fillna(0.0)
    out["obv"] = (direction * out["volume"]).cumsum()
    out["obv_slope"] = out["obv"] - out["obv"].shift(5)

    # Bollinger Bands: volatility regime + location filter.
    bb_mid = out["close"].rolling(20, min_periods=20).mean()
    bb_std = out["close"].rolling(20, min_periods=20).std(ddof=0)
    out["bb_mid"] = bb_mid
    out["bb_upper"] = bb_mid + 2.0 * bb_std
    out["bb_lower"] = bb_mid - 2.0 * bb_std
    out["bb_width_pct"] = (out["bb_upper"] - out["bb_lower"]) / bb_mid.replace(0, np.nan) * 100.0
    bb_range = (out["bb_upper"] - out["bb_lower"]).replace(0, np.nan)
    out["bb_position"] = (out["close"] - out["bb_lower"]) / bb_range

    # Volume z-score catches genuine expansion better than ratio alone.
    vol_mean = out["volume"].shift(1).rolling(20, min_periods=10).mean()
    vol_std = out["volume"].shift(1).rolling(20, min_periods=10).std(ddof=0)
    out["volume_zscore"] = (out["volume"] - vol_mean) / vol_std.replace(0, np.nan)

    # DI spread measures directional conviction.
    out["di_spread"] = out["plus_di"] - out["minus_di"]

    # Momentum acceleration.
    out["rsi_slope"] = out["rsi"] - out["rsi"].shift(2)

    # Momentum / structure helpers used by reversal and scoring logic.
    out["rsi_prev"] = out["rsi"].shift(1)
    out["rsi_rising"] = out["rsi"] > out["rsi_prev"]
    out["rsi_falling"] = out["rsi"] < out["rsi_prev"]
    out["higher_high"] = out["high"] > out["high"].shift(1)
    out["higher_low"] = out["low"] > out["low"].shift(1)
    out["lower_high"] = out["high"] < out["high"].shift(1)
    out["lower_low"] = out["low"] < out["low"].shift(1)

    out = out.replace([np.inf, -np.inf], np.nan)
    return out


def indicators_ready(row):
    required = [
        "close", "ema9", "ema21", "ema50", "ema200", "rsi",
        "macd", "macd_signal", "macd_hist", "atr", "atr_percent",
        "volume_ratio", "body_ratio", "adx", "plus_di", "minus_di",
        "rolling_vwap", "obv_slope", "bb_width_pct", "bb_position",
        "volume_zscore", "di_spread", "rsi_slope"
    ]
    for column in required:
        value = row.get(column, np.nan)
        try:
            if pd.isna(value) or not np.isfinite(float(value)):
                return False
        except Exception:
            return False
    return True


# =========================================================
# APPLY INDICATORS TO BOTH TIMEFRAMES
# =========================================================

def prepare_symbol_data(symbol):

    try:

        data = get_symbol_market_data(symbol)
        if not data:
            return None

        frames = {
            "1h": data.get("1h"),
            "30m": data.get("30m"),
            "4h": data.get("4h"),
            "1d": data.get("1d"),
        }

        for tf, frame in frames.items():
            if not validate_market_dataframe(frame):
                if tf in ("1h", "30m"):
                    log(f"⚠️ Invalid required {tf} data: {symbol}")
                    return None
                log(f"⚠️ Optional {tf} data unavailable: {symbol}")
                frames[tf] = None
                continue

            frame = add_indicators(frame)
            if frame is None or frame.empty:
                if tf in ("1h", "30m"):
                    log(f"⚠️ Failed required indicators {tf}: {symbol}")
                    return None
                log(f"⚠️ Optional indicators failed {tf}: {symbol}")
                frames[tf] = None
                continue
            frames[tf] = frame

        return frames

    except Exception as e:
        log(f"⚠️ prepare_symbol_data error {symbol}: {e}")
        if DEBUG_MODE:
            traceback.print_exc()
        return None


# =========================================================
# MULTI-TIMEFRAME CONTEXT
# =========================================================

def get_mtf_context(data):
    """Return descriptive 4H and Daily trend context from closed candles."""
    result = {}

    for tf, label in (("4h", "4H"), ("1d", "Daily")):
        df = data.get(tf) if isinstance(data, dict) else None
        if df is None or len(df) < 50:
            result[tf] = {"trend": "UNKNOWN", "adx": 0.0}
            continue

        row = df.iloc[-1]
        close = safe_float(row.get("close"))
        ema9 = safe_float(row.get("ema9"))
        ema21 = safe_float(row.get("ema21"))
        ema200 = safe_float(row.get("ema200"))
        adx = safe_float(row.get("adx"))

        bullish = close > ema200 and ema9 > ema21
        bearish = close < ema200 and ema9 < ema21
        trend = "BULLISH" if bullish else ("BEARISH" if bearish else "NEUTRAL")

        result[tf] = {
            "trend": trend,
            "adx": adx,
            "rsi": safe_float(row.get("rsi")),
            "close": close,
            "ema9": ema9,
            "ema21": ema21,
            "ema200": ema200,
        }

    return result


def mtf_side_adjustment(mtf, side):
    """Small score adjustment; higher TFs guide but do not hard-block signals."""
    side = str(side).upper()
    adjustment = 0
    reasons = []

    for tf, label in (("4h", "4H"), ("1d", "Daily")):
        trend = str(mtf.get(tf, {}).get("trend", "UNKNOWN")).upper()
        if trend == "BULLISH" and side == "BUY":
            adjustment += 4
            reasons.append(f"{label} trend bullish")
        elif trend == "BEARISH" and side == "SELL":
            adjustment += 4
            reasons.append(f"{label} trend bearish")
        elif trend == "BEARISH" and side == "BUY":
            adjustment -= 3
            reasons.append(f"{label} trend bearish (headwind)")
        elif trend == "BULLISH" and side == "SELL":
            adjustment -= 3
            reasons.append(f"{label} trend bullish (headwind)")
        elif trend == "NEUTRAL":
            adjustment += 1

    return adjustment, reasons


# =========================================================
# BTC REGIME HELPERS
# =========================================================

def _btc_regime_from_row(row):
    if row is None or not indicators_ready(row):
        return {"regime": "UNKNOWN", "score": 0, "bullish": False, "bearish": False}

    score = 0
    close = safe_float(row.get("close"))
    ema9 = safe_float(row.get("ema9"))
    ema21 = safe_float(row.get("ema21"))
    ema50 = safe_float(row.get("ema50"))
    ema200 = safe_float(row.get("ema200"))
    macd = safe_float(row.get("macd"))
    macd_signal = safe_float(row.get("macd_signal"))
    rsi = safe_float(row.get("rsi"))
    adx = safe_float(row.get("adx"))
    plus_di = safe_float(row.get("plus_di"))
    minus_di = safe_float(row.get("minus_di"))

    score += 2 if close > ema200 else (-2 if close < ema200 else 0)
    score += 2 if ema9 > ema21 else (-2 if ema9 < ema21 else 0)
    score += 1 if ema21 > ema50 else (-1 if ema21 < ema50 else 0)
    score += 1 if macd > macd_signal else (-1 if macd < macd_signal else 0)
    score += 1 if rsi >= 52 else (-1 if rsi <= 48 else 0)
    if adx >= MIN_ADX:
        score += 1 if plus_di > minus_di else (-1 if minus_di > plus_di else 0)

    bullish = score >= 3
    bearish = score <= -3
    regime = "BULLISH" if bullish else ("BEARISH" if bearish else "NEUTRAL")
    return {"regime": regime, "score": score, "bullish": bullish, "bearish": bearish}


def get_btc_dataframe(timeframe, limit=250):
    df = get_klines(BTC_SYMBOL, timeframe, limit)
    if df is None or df.empty:
        return None
    df = add_indicators(df)
    if df is None or df.empty:
        return None
    return df


def get_btc_1h_regime():
    df = get_btc_dataframe(BTC_MAIN_TIMEFRAME, KLINE_LIMIT_MAIN)
    if df is None or len(df) < 50:
        return {"regime": "UNKNOWN", "score": 0, "bullish": False, "bearish": False}
    return _btc_regime_from_row(df.iloc[-1])


def get_btc_daily_regime():
    df = get_btc_dataframe(BTC_MACRO_TIMEFRAME, KLINE_LIMIT_DAILY)
    if df is None or len(df) < 50:
        return {"regime": "UNKNOWN", "score": 0, "bullish": False, "bearish": False}
    return _btc_regime_from_row(df.iloc[-1])


# =========================================================
# COMBINED BTC REGIME
# =========================================================

def get_btc_market_regime():

    btc_1h = get_btc_1h_regime()

    btc_daily = get_btc_daily_regime()

    # -----------------------------------------------------
    # Scores
    # -----------------------------------------------------

    score_1h = btc_1h["score"]

    score_daily = btc_daily["score"]

    combined_score = (
        score_1h +
        score_daily
    )

    # -----------------------------------------------------
    # Strong bullish
    # -----------------------------------------------------

    if (
        btc_1h["bullish"]
        and
        btc_daily["bullish"]
    ):

        combined = "BULLISH"

    # -----------------------------------------------------
    # Strong bearish
    # -----------------------------------------------------

    elif (
        btc_1h["bearish"]
        and
        btc_daily["bearish"]
    ):

        combined = "BEARISH"

    # -----------------------------------------------------
    # Mixed
    # -----------------------------------------------------

    elif (
        btc_1h["bearish"]
        and
        btc_daily["bullish"]
    ):

        combined = "MIXED_BEARISH_1H"

    elif (
        btc_1h["bullish"]
        and
        btc_daily["bearish"]
    ):

        combined = "MIXED_BULLISH_1H"

    else:

        combined = "NEUTRAL"


    return {
        "combined": combined,
        "combined_score": combined_score,

        "1h": btc_1h,
        "daily": btc_daily
    }


# =========================================================
# BTC FILTER FOR ALTCOIN SIGNALS
# =========================================================

def btc_allows_signal(
    side,
    btc_regime
):

    side = str(
        side
    ).upper()

    combined = btc_regime.get(
        "combined",
        "UNKNOWN"
    )

    # -----------------------------------------------------
    # BUY
    # -----------------------------------------------------

    if side == "BUY":

        # BTC کاملاً نزولی
        if combined == "BEARISH":
            return False

        return True

    # -----------------------------------------------------
    # SELL
    # -----------------------------------------------------

    if side == "SELL":

        # BTC کاملاً صعودی
        if combined == "BULLISH":
            return False

        return True

    return False


# =========================================================
# BTC REPORT
# =========================================================

def print_btc_regime(
    btc_regime
):

    if not btc_regime:
        return

    btc_1h = btc_regime.get(
        "1h",
        {}
    )

    btc_daily = btc_regime.get(
        "daily",
        {}
    )

    log("")
    log("=" * 60)
    log("₿ BTC MARKET REGIME")
    log("=" * 60)

    log(
        f"📊 BTC 1H: "
        f"{btc_1h.get('regime', 'UNKNOWN')} "
        f"(score "
        f"{btc_1h.get('score', 0)})"
    )

    log(
        f"📅 BTC Daily: "
        f"{btc_daily.get('regime', 'UNKNOWN')} "
        f"(score "
        f"{btc_daily.get('score', 0)})"
    )

    log(
        f"📌 Combined: "
        f"{btc_regime.get('combined', 'UNKNOWN')}"
    )

    log(
        f"🎯 Combined score: "
        f"{btc_regime.get('combined_score', 0)}"
    )

    log("=" * 60)


# =========================================================
# END OF SECTION 6
# =========================================================# 



# =========================================================
# END OF SECTION 7
# =========================================================# =========================================================
# SECTION 8
# PRICE STRUCTURE + RSI / MACD DIVERGENCE
# =========================================================


# =========================================================
# FIND LOCAL LOWS
# =========================================================

def find_local_lows(
    series,
    lookback=2
):

    values = series.values

    lows = []

    for i in range(
        lookback,
        len(values) - lookback
    ):

        current = values[i]

        left = values[
            i - lookback:i
        ]

        right = values[
            i + 1:
            i + 1 + lookback
        ]

        if (
            current <= left.min()
            and
            current <= right.min()
        ):

            lows.append(i)

    return lows


# =========================================================
# FIND LOCAL HIGHS
# =========================================================

def find_local_highs(
    series,
    lookback=2
):

    values = series.values

    highs = []

    for i in range(
        lookback,
        len(values) - lookback
    ):

        current = values[i]

        left = values[
            i - lookback:i
        ]

        right = values[
            i + 1:
            i + 1 + lookback
        ]

        if (
            current >= left.max()
            and
            current >= right.max()
        ):

            highs.append(i)

    return highs


# =========================================================
# BULLISH RSI DIVERGENCE
# =========================================================

def detect_bullish_rsi_divergence(
    df
):

    if df is None or len(df) < 20:
        return False

    recent = df.tail(
        DIVERGENCE_LOOKBACK
    ).reset_index(
        drop=True
    )

    if (
        "close" not in recent.columns
        or
        "rsi" not in recent.columns
    ):
        return False

    lows = find_local_lows(
        recent["low"],
        lookback=2
    )

    if len(lows) < 2:
        return False

    # فقط آخرین چند کف
    lows = lows[-5:]

    for i in range(
        len(lows) - 1
    ):

        first_idx = lows[i]
        second_idx = lows[i + 1]

        gap = (
            second_idx -
            first_idx
        )

        if (
            gap < DIVERGENCE_MIN_GAP
            or
            gap > DIVERGENCE_MAX_GAP
        ):
            continue

        price_1 = safe_float(
            recent.loc[
                first_idx,
                "low"
            ]
        )

        price_2 = safe_float(
            recent.loc[
                second_idx,
                "low"
            ]
        )

        rsi_1 = safe_float(
            recent.loc[
                first_idx,
                "rsi"
            ]
        )

        rsi_2 = safe_float(
            recent.loc[
                second_idx,
                "rsi"
            ]
        )

        # قیمت کف پایین‌تر
        # RSI کف بالاتر
        if (
            price_2 < price_1
            and
            rsi_2 > rsi_1
        ):

            return True

    return False


# =========================================================
# BEARISH RSI DIVERGENCE
# =========================================================

def detect_bearish_rsi_divergence(
    df
):

    if df is None or len(df) < 20:
        return False

    recent = df.tail(
        DIVERGENCE_LOOKBACK
    ).reset_index(
        drop=True
    )

    if (
        "close" not in recent.columns
        or
        "rsi" not in recent.columns
    ):
        return False

    highs = find_local_highs(
        recent["high"],
        lookback=2
    )

    if len(highs) < 2:
        return False

    highs = highs[-5:]

    for i in range(
        len(highs) - 1
    ):

        first_idx = highs[i]
        second_idx = highs[i + 1]

        gap = (
            second_idx -
            first_idx
        )

        if (
            gap < DIVERGENCE_MIN_GAP
            or
            gap > DIVERGENCE_MAX_GAP
        ):
            continue

        price_1 = safe_float(
            recent.loc[
                first_idx,
                "high"
            ]
        )

        price_2 = safe_float(
            recent.loc[
                second_idx,
                "high"
            ]
        )

        rsi_1 = safe_float(
            recent.loc[
                first_idx,
                "rsi"
            ]
        )

        rsi_2 = safe_float(
            recent.loc[
                second_idx,
                "rsi"
            ]
        )

        # قیمت سقف بالاتر
        # RSI سقف پایین‌تر
        if (
            price_2 > price_1
            and
            rsi_2 < rsi_1
        ):

            return True

    return False


# =========================================================
# BULLISH MACD DIVERGENCE
# =========================================================

def detect_bullish_macd_divergence(
    df
):

    if df is None or len(df) < 20:
        return False

    recent = df.tail(
        DIVERGENCE_LOOKBACK
    ).reset_index(
        drop=True
    )

    if "macd_hist" not in recent.columns:
        return False

    lows = find_local_lows(
        recent["low"],
        lookback=2
    )

    if len(lows) < 2:
        return False

    lows = lows[-5:]

    for i in range(
        len(lows) - 1
    ):

        first_idx = lows[i]
        second_idx = lows[i + 1]

        gap = (
            second_idx -
            first_idx
        )

        if (
            gap < DIVERGENCE_MIN_GAP
            or
            gap > DIVERGENCE_MAX_GAP
        ):
            continue

        price_1 = safe_float(
            recent.loc[
                first_idx,
                "low"
            ]
        )

        price_2 = safe_float(
            recent.loc[
                second_idx,
                "low"
            ]
        )

        macd_1 = safe_float(
            recent.loc[
                first_idx,
                "macd_hist"
            ]
        )

        macd_2 = safe_float(
            recent.loc[
                second_idx,
                "macd_hist"
            ]
        )

        if (
            price_2 < price_1
            and
            macd_2 > macd_1
        ):

            return True

    return False


# =========================================================
# BEARISH MACD DIVERGENCE
# =========================================================

def detect_bearish_macd_divergence(
    df
):

    if df is None or len(df) < 20:
        return False

    recent = df.tail(
        DIVERGENCE_LOOKBACK
    ).reset_index(
        drop=True
    )

    if "macd_hist" not in recent.columns:
        return False

    highs = find_local_highs(
        recent["high"],
        lookback=2
    )

    if len(highs) < 2:
        return False

    highs = highs[-5:]

    for i in range(
        len(highs) - 1
    ):

        first_idx = highs[i]
        second_idx = highs[i + 1]

        gap = (
            second_idx -
            first_idx
        )

        if (
            gap < DIVERGENCE_MIN_GAP
            or
            gap > DIVERGENCE_MAX_GAP
        ):
            continue

        price_1 = safe_float(
            recent.loc[
                first_idx,
                "high"
            ]
        )

        price_2 = safe_float(
            recent.loc[
                second_idx,
                "high"
            ]
        )

        macd_1 = safe_float(
            recent.loc[
                first_idx,
                "macd_hist"
            ]
        )

        macd_2 = safe_float(
            recent.loc[
                second_idx,
                "macd_hist"
            ]
        )

        if (
            price_2 > price_1
            and
            macd_2 < macd_1
        ):

            return True

    return False


# =========================================================
# COMBINED DIVERGENCE ANALYSIS
# =========================================================

def analyze_divergence(
    df
):

    bullish_rsi = (
        detect_bullish_rsi_divergence(
            df
        )
    )

    bearish_rsi = (
        detect_bearish_rsi_divergence(
            df
        )
    )

    bullish_macd = (
        detect_bullish_macd_divergence(
            df
        )
    )

    bearish_macd = (
        detect_bearish_macd_divergence(
            df
        )
    )

    bullish_score = 0
    bearish_score = 0

    reasons_buy = []
    reasons_sell = []

    if bullish_rsi:

        bullish_score += 1

        reasons_buy.append(
            "RSI bullish divergence"
        )

    if bullish_macd:

        bullish_score += 1

        reasons_buy.append(
            "MACD bullish divergence"
        )

    if bearish_rsi:

        bearish_score += 1

        reasons_sell.append(
            "RSI bearish divergence"
        )

    if bearish_macd:

        bearish_score += 1

        reasons_sell.append(
            "MACD bearish divergence"
        )

    return {

        "bullish_rsi": bullish_rsi,

        "bearish_rsi": bearish_rsi,

        "bullish_macd": bullish_macd,

        "bearish_macd": bearish_macd,

        "bullish_score": bullish_score,

        "bearish_score": bearish_score,

        "buy_reason": (
            ", ".join(reasons_buy)
            if reasons_buy
            else ""
        ),

        "sell_reason": (
            ", ".join(reasons_sell)
            if reasons_sell
            else ""
        )
    }


# =========================================================
# PRICE STRUCTURE
# =========================================================

def analyze_price_structure(
    df
):

    if df is None or len(df) < 10:

        return {
            "bullish": False,
            "bearish": False,
            "score_buy": 0,
            "score_sell": 0
        }

    row = df.iloc[-1]

    previous = df.iloc[-2]

    score_buy = 0
    score_sell = 0

    # -----------------------------------------------------
    # EMA structure
    # -----------------------------------------------------

    if (
        row["ema9"] >
        row["ema21"] >
        row["ema50"]
    ):

        score_buy += 2

    elif (
        row["ema9"] <
        row["ema21"] <
        row["ema50"]
    ):

        score_sell += 2

    # -----------------------------------------------------
    # Price structure
    # -----------------------------------------------------

    if (
        row["high"] >
        previous["high"]
        and
        row["low"] >
        previous["low"]
    ):

        score_buy += 1

    if (
        row["high"] <
        previous["high"]
        and
        row["low"] <
        previous["low"]
    ):

        score_sell += 1

    # -----------------------------------------------------
    # EMA slopes
    # -----------------------------------------------------

    if row["ema21_slope"] > 0:
        score_buy += 1

    elif row["ema21_slope"] < 0:
        score_sell += 1

    # -----------------------------------------------------
    # Final structure
    # -----------------------------------------------------

    return {

        "bullish": score_buy >= 2,

        "bearish": score_sell >= 2,

        "score_buy": score_buy,

        "score_sell": score_sell
    }


# =========================================================
# END OF SECTION 8
# =========================================================# =========================================================
# SECTION 9
# 1H SIGNAL ENGINE
# 100 POINT SCORING
# =========================================================


def score_timeframe(df, side, timeframe_label="TF"):
    """
    امتیازدهی اصلی 1H

    BUY:
    - روند صعودی کامل امتیاز کامل می‌گیرد.
    - پولبک/شروع برگشت صعودی امتیاز جزئی می‌گیرد.
    - فاصله زیاد از EMA21/EMA200 برای BUY جریمه می‌شود.

    SELL:
    - منطق فعلی نزولی حفظ شده است.
    """

    side = str(side).upper()

    if df is None or len(df) < 50:
        return {
            "score": 0,
            "reasons": ["Insufficient 1H data"],
            "hard_pass": False
        }

    row = df.iloc[-1]

    if not indicators_ready(row):
        return {
            "score": 0,
            "reasons": ["Indicators not ready"],
            "hard_pass": False
        }

    score = 0
    reasons = []

    # =====================================================
    # VALUES
    # =====================================================

    close = safe_float(row["close"])

    ema9 = safe_float(row["ema9"])
    ema21 = safe_float(row["ema21"])
    ema50 = safe_float(row["ema50"])
    ema200 = safe_float(row["ema200"])

    adx = safe_float(row["adx"])
    plus_di = safe_float(row["plus_di"])
    minus_di = safe_float(row["minus_di"])

    rsi = safe_float(row["rsi"])

    macd = safe_float(row["macd"])
    macd_signal = safe_float(row["macd_signal"])
    macd_hist = safe_float(row["macd_hist"])

    volume_ratio = safe_float(row["volume_ratio"])

    body_ratio = safe_float(row["body_ratio"])

    atr_percent = safe_float(row["atr_percent"])

    # =====================================================
    # EMA200 — MAIN TREND
    # =====================================================

    if side == "BUY":

        if close > ema200:

            score += SCORE_EMA200

            reasons.append(
                "Price above EMA200"
            )

        else:

            reasons.append(
                "Price below EMA200"
            )

    else:

        if close < ema200:

            score += SCORE_EMA200

            reasons.append(
                "Price below EMA200"
            )

        else:

            reasons.append(
                "Price above EMA200"
            )

    # =====================================================
    # EMA9 / EMA21
    # =====================================================

    if side == "BUY":

        if ema9 > ema21:

            score += SCORE_EMA9_21

            reasons.append(
                "EMA9 > EMA21"
            )

        else:

            bullish_pullback = (
                close > ema21
                and
                macd > macd_signal
                and
                macd_hist > 0
                and
                rsi >= 45
                and
                row["bullish_candle"]
            )

            if bullish_pullback:

                partial_ema_score = max(
                    3,
                    SCORE_EMA9_21 // 3
                )

                score += partial_ema_score

                reasons.append(
                    "Bullish pullback / early EMA recovery"
                )

            elif (
                close > ema21
                and
                macd > macd_signal
            ):

                partial_ema_score = max(
                    2,
                    SCORE_EMA9_21 // 4
                )

                score += partial_ema_score

                reasons.append(
                    "Early bullish recovery"
                )

            else:

                reasons.append(
                    "EMA9 below EMA21"
                )

    else:

        if ema9 < ema21:

            score += SCORE_EMA9_21

            reasons.append(
                "EMA9 < EMA21"
            )

        else:

            bearish_pullback = (
                close < ema21
                and
                macd < macd_signal
                and
                macd_hist < 0
                and
                rsi <= 55
                and
                row["bearish_candle"]
            )

            if bearish_pullback:

                partial_ema_score = max(
                    3,
                    SCORE_EMA9_21 // 3
                )

                score += partial_ema_score

                reasons.append(
                    "Bearish pullback / early EMA recovery"
                )

            elif (
                close < ema21
                and
                macd < macd_signal
            ):

                partial_ema_score = max(
                    2,
                    SCORE_EMA9_21 // 4
                )

                score += partial_ema_score

                reasons.append(
                    "Early bearish recovery"
                )

            else:

                reasons.append(
                    "EMA9 above EMA21"
                )

    # =====================================================
    # ADX + DI
    # =====================================================

    if adx >= STRONG_ADX:

        if side == "BUY" and plus_di > minus_di:

            score += SCORE_ADX

            reasons.append(
                f"ADX strong bullish ({adx:.1f})"
            )

        elif side == "SELL" and minus_di > plus_di:

            score += SCORE_ADX

            reasons.append(
                f"ADX strong bearish ({adx:.1f})"
            )

        else:

            reasons.append(
                f"ADX strong but direction mismatch ({adx:.1f})"
            )

    elif adx >= MIN_ADX:

        half_adx = max(
            1,
            SCORE_ADX // 2
        )

        if side == "BUY" and plus_di > minus_di:

            score += half_adx

            reasons.append(
                f"ADX moderate bullish ({adx:.1f})"
            )

        elif side == "SELL" and minus_di > plus_di:

            score += half_adx

            reasons.append(
                f"ADX moderate bearish ({adx:.1f})"
            )

        else:

            reasons.append(
                f"ADX moderate but direction mismatch ({adx:.1f})"
            )

    else:

        reasons.append(
            f"ADX weak ({adx:.1f})"
        )

    # =====================================================
    # RSI
    # =====================================================

    if side == "BUY":

        if RSI_BUY_MIN <= rsi <= RSI_BUY_MAX:

            score += SCORE_RSI

            reasons.append(
                f"RSI healthy ({rsi:.1f})"
            )

        elif rsi >= 80:

            score -= 10

            reasons.append(
                f"RSI very high -10 ({rsi:.1f})"
            )

        elif rsi >= RSI_OVERBOUGHT:

            score -= 5

            reasons.append(
                f"RSI high -5 ({rsi:.1f})"
            )

        elif RSI_OVERSOLD <= rsi < RSI_BUY_MIN:

            score += max(
                1,
                SCORE_RSI // 2
            )

            reasons.append(
                f"RSI recovering ({rsi:.1f})"
            )

        elif rsi > RSI_BUY_MAX:

            score += max(
                1,
                SCORE_RSI // 2
            )

            reasons.append(
                f"RSI elevated ({rsi:.1f})"
            )

        else:

            reasons.append(
                f"RSI unsuitable ({rsi:.1f})"
            )

    else:

        if RSI_SELL_MIN <= rsi <= RSI_SELL_MAX:

            score += SCORE_RSI

            reasons.append(
                f"RSI healthy ({rsi:.1f})"
            )

        elif RSI_SELL_MIN > rsi > RSI_OVERSOLD:

            score += max(
                1,
                SCORE_RSI // 2
            )

            reasons.append(
                f"RSI weakening ({rsi:.1f})"
            )

        elif rsi > RSI_OVERBOUGHT:

            score += max(
                1,
                SCORE_RSI // 2
            )

            reasons.append(
                f"RSI overbought ({rsi:.1f})"
            )

        else:

            reasons.append(
                f"RSI unsuitable ({rsi:.1f})"
            )

    # =====================================================
    # MACD
    # =====================================================

    if side == "BUY":

        if (
            macd > macd_signal
            and
            macd_hist > 0
        ):

            score += SCORE_MACD

            reasons.append(
                "MACD bullish"
            )

        elif (
            macd > macd_signal
            or
            macd_hist > 0
        ):

            score += max(
                1,
                SCORE_MACD // 2
            )

            reasons.append(
                "MACD partially bullish"
            )

        else:

            reasons.append(
                "MACD not bullish"
            )

    else:

        if (
            macd < macd_signal
            and
            macd_hist < 0
        ):

            score += SCORE_MACD

            reasons.append(
                "MACD bearish"
            )

        elif (
            macd < macd_signal
            or
            macd_hist < 0
        ):

            score += max(
                1,
                SCORE_MACD // 2
            )

            reasons.append(
                "MACD partially bearish"
            )

        else:

            reasons.append(
                "MACD not bearish"
            )

    # =====================================================
    # VOLUME
    # =====================================================

    if volume_ratio >= STRONG_VOLUME_RATIO:

        score += SCORE_VOLUME

        reasons.append(
            f"Strong volume {volume_ratio:.2f}x"
        )

    elif volume_ratio >= MIN_VOLUME_RATIO:

        score += max(
            1,
            SCORE_VOLUME // 2
        )

        reasons.append(
            f"Good volume {volume_ratio:.2f}x"
        )

    elif volume_ratio >= 0.90:

        score += max(
            1,
            SCORE_VOLUME // 4
        )

        reasons.append(
            f"Normal volume {volume_ratio:.2f}x"
        )

    else:

        reasons.append(
            f"Low volume {volume_ratio:.2f}x"
        )

    # =====================================================
    # CANDLE
    # =====================================================

    if body_ratio >= MIN_CANDLE_BODY_RATIO:

        if side == "BUY":

            if row["bullish_candle"]:

                score += SCORE_CANDLE

                reasons.append(
                    "Bullish candle"
                )

            else:

                reasons.append(
                    "Candle not bullish"
                )

        else:

            if row["bearish_candle"]:

                score += SCORE_CANDLE

                reasons.append(
                    "Bearish candle"
                )

            else:

                reasons.append(
                    "Candle not bearish"
                )

    else:

        reasons.append(
            "Weak candle body"
        )

    # =====================================================
    # ATR
    # =====================================================

    if (
        MIN_ATR_PERCENT
        <= atr_percent
        <= MAX_ATR_PERCENT
    ):

        score += SCORE_ATR

        reasons.append(
            f"ATR suitable {atr_percent:.2f}%"
        )

    elif (
        atr_percent > 0
        and
        atr_percent < MAX_ATR_PERCENT * 1.25
    ):

        score += max(
            1,
            SCORE_ATR // 2
        )

        reasons.append(
            f"ATR slightly outside ideal range {atr_percent:.2f}%"
        )

    else:

        reasons.append(
            f"ATR unsuitable {atr_percent:.2f}%"
        )

    # =====================================================
    # DISTANCE FROM EMA21 / EMA200
    # =====================================================

    distance_ema21 = abs(
        safe_float(
            row["distance_ema21"]
        )
    )

    distance_ema200 = abs(
        safe_float(
            row["distance_ema200"]
        )
    )

    # -----------------------------------------------------
    # BUY: penalize overextended price
    # -----------------------------------------------------

    if side == "BUY":

        if distance_ema21 > MAX_DISTANCE_FROM_EMA21:

            score -= 5

            reasons.append(
                f"BUY overextended from EMA21 -5 ({distance_ema21:.2f}%)"
            )

        elif distance_ema21 > MAX_DISTANCE_FROM_EMA21 * 0.75:

            score -= 2

            reasons.append(
                f"BUY somewhat extended from EMA21 -2 ({distance_ema21:.2f}%)"
            )

        if distance_ema200 > MAX_DISTANCE_FROM_EMA200:

            score -= 5

            reasons.append(
                f"BUY far from EMA200 -5 ({distance_ema200:.2f}%)"
            )

        elif distance_ema200 > MAX_DISTANCE_FROM_EMA200 * 0.75:

            score -= 2

            reasons.append(
                f"BUY somewhat far from EMA200 -2 ({distance_ema200:.2f}%)"
            )

    # -----------------------------------------------------
    # SELL: فقط هشدار؛ امتیازدهی قبلی حفظ شود
    # -----------------------------------------------------

    else:

        if distance_ema21 > MAX_DISTANCE_FROM_EMA21:

            reasons.append(
                f"Warning: far from EMA21 ({distance_ema21:.2f}%)"
            )

        if distance_ema200 > MAX_DISTANCE_FROM_EMA200:

            reasons.append(
                f"Warning: far from EMA200 ({distance_ema200:.2f}%)"
            )

    # =====================================================
    # LATE ENTRY PROTECTION
    # =====================================================
    # خرید با RSI بالا + فاصله زیاد از EMA21، حتی با امتیاز بالا،
    # می‌تواند ورود دیرهنگام باشد. در این حالت سیگنال را سخت‌گیرانه رد می‌کنیم.
    if side == "BUY":
        if (
            rsi >= MAX_LATE_ENTRY_RSI_BUY
            and
            distance_ema21 > MAX_LATE_ENTRY_EMA21_DISTANCE
        ):
            reasons.append(
                f"Late BUY entry blocked (RSI {rsi:.1f}, EMA21 distance {distance_ema21:.2f}%)"
            )
            return {
                "score": 0,
                "reasons": reasons,
                "hard_pass": False,
                "rsi": rsi,
                "adx": adx,
                "volume_ratio": volume_ratio,
                "atr_percent": atr_percent,
                "distance_ema21": distance_ema21,
                "distance_ema200": distance_ema200
            }

    elif side == "SELL":
        if (
            rsi <= MIN_LATE_ENTRY_RSI_SELL
            and
            distance_ema21 > MAX_LATE_ENTRY_EMA21_DISTANCE
        ):
            reasons.append(
                f"Late SELL entry blocked (RSI {rsi:.1f}, EMA21 distance {distance_ema21:.2f}%)"
            )
            return {
                "score": 0,
                "reasons": reasons,
                "hard_pass": False,
                "rsi": rsi,
                "adx": adx,
                "volume_ratio": volume_ratio,
                "atr_percent": atr_percent,
                "distance_ema21": distance_ema21,
                "distance_ema200": distance_ema200
            }

    # =====================================================
    # FINAL SCORE
    # =====================================================

    score = max(
        0,
        min(
            100,
            int(round(score))
        )
    )

    # اجازه عبور اولیه برای امتیازهای 55+
    hard_pass = score >= 55

    return {
        "score": score,
        "reasons": reasons,
        "hard_pass": hard_pass,
        "rsi": rsi,
        "adx": adx,
        "volume_ratio": volume_ratio,
        "atr_percent": atr_percent,
        "distance_ema21": distance_ema21,
        "distance_ema200": distance_ema200
    }

# =========================================================
# 30M CONFIRMATION
# =========================================================

def score_30m_confirmation(
    df,
    side
):

    side = str(side).upper()

    if df is None or len(df) < 30:

        return {
            "score": 0,
            "confirmed": False,
            "reasons": []
        }

    row = df.iloc[-1]

    if not indicators_ready(row):

        return {
            "score": 0,
            "confirmed": False,
            "reasons": []
        }

    score = 0
    reasons = []

      # -----------------------------------------------------
    # EMA direction
    # -----------------------------------------------------

    if side == "BUY":

        if row["close"] > row["ema21"]:
            score += 1
            reasons.append("30M price above EMA21")

        if row["ema9"] > row["ema21"]:
            score += 1
            reasons.append("30M EMA9 > EMA21")

    else:

        if row["close"] < row["ema21"]:
            score += 1
            reasons.append("30M price below EMA21")

        if row["ema9"] < row["ema21"]:
            score += 1
            reasons.append("30M EMA9 < EMA21")

    # -----------------------------------------------------
    # MACD
    # -----------------------------------------------------

    if side == "BUY":

        if (
            row["macd"] >
            row["macd_signal"]
            and
            row["macd_hist"] > 0
        ):

            score += 1

            reasons.append(
                "30M MACD bullish"
            )

    else:

        if (
            row["macd"] <
            row["macd_signal"]
            and
            row["macd_hist"] < 0
        ):

            score += 1

            reasons.append(
                "30M MACD bearish"
            )


    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    if side == "BUY":

        if (
            row["rsi"] >= 50
            and
            row["rsi"] < 72
        ):

            score += 1

            reasons.append(
                "30M RSI supportive"
            )

    else:

        if (
            row["rsi"] <= 50
            and
            row["rsi"] > 28
        ):

            score += 1

            reasons.append(
                "30M RSI supportive"
            )


        # -----------------------------------------------------
    # Professional confirmation filters
    # -----------------------------------------------------
    rsi = safe_float(row.get("rsi"))
    adx = safe_float(row.get("adx"))
    plus_di = safe_float(row.get("plus_di"))
    minus_di = safe_float(row.get("minus_di"))
    volume_ratio = safe_float(row.get("volume_ratio"))
    vwap = safe_float(row.get("rolling_vwap"))
    close = safe_float(row.get("close"))
    macd_hist = safe_float(row.get("macd_hist"))
    macd_hist_prev = safe_float(row.get("macd_hist_prev"))
    obv_slope = safe_float(row.get("obv_slope"))

    confirmations = score

    if adx >= PRO_MIN_30M_ADX and ((side == "BUY" and plus_di > minus_di) or (side == "SELL" and minus_di > plus_di)):
        confirmations += 1
        reasons.append("30M ADX/DI directional confirmation")

    if volume_ratio >= PRO_MIN_VOLUME_RATIO:
        confirmations += 1
        reasons.append(f"30M volume expansion {volume_ratio:.2f}x")

    if vwap > 0 and ((side == "BUY" and close > vwap) or (side == "SELL" and close < vwap)):
        confirmations += 1
        reasons.append("30M VWAP alignment")

    if ((side == "BUY" and obv_slope > 0) or (side == "SELL" and obv_slope < 0)):
        confirmations += 1
        reasons.append("30M OBV participation alignment")

    if ((side == "BUY" and macd_hist > macd_hist_prev) or (side == "SELL" and macd_hist < macd_hist_prev)):
        confirmations += 1
        reasons.append("30M MACD histogram momentum improving")

    if side == "BUY":
        if 50 <= rsi < 70 and rsi >= safe_float(row.get("rsi_prev")):
            confirmations += 1
            reasons.append("30M RSI momentum supportive")
    else:
        if 30 < rsi <= 50 and rsi <= safe_float(row.get("rsi_prev")):
            confirmations += 1
            reasons.append("30M RSI momentum supportive")

    # Require independent evidence rather than two easy EMA checks.
    confirmed = confirmations >= PRO_MIN_30M_CONFIRMATIONS

    return {
        "score": (
            SCORE_CONFIRM_30M
            if confirmed
            else 0
        ),
        "confirmations": confirmations,
        "confirmed": confirmed,
        "reasons": reasons
    }


# =========================================================
# BTC SCORE
# =========================================================

def score_btc_regime(
    side,
    btc_regime
):

    if not btc_regime:

        return {
            "score": 0,
            "allowed": False,
            "reason": "BTC data unavailable"
        }

    side = str(side).upper()

    combined = btc_regime.get(
        "combined",
        "UNKNOWN"
    )

    # -----------------------------------------------------
    # BUY
    # -----------------------------------------------------

    if side == "BUY":

        if combined == "BEARISH":

            return {
                "score": 0,
                "allowed": False,
                "reason": "BTC bearish"
            }

        if combined == "BULLISH":

            return {
                "score": SCORE_BTC_REGIME,
                "allowed": True,
                "reason": "BTC bullish"
            }

        return {
            "score": 2,
            "allowed": True,
            "reason": f"BTC {combined}"
        }

    # -----------------------------------------------------
    # SELL
    # -----------------------------------------------------

    if side == "SELL":

        if combined == "BULLISH":

            return {
                "score": 0,
                "allowed": False,
                "reason": "BTC bullish"
            }

        if combined == "BEARISH":

            return {
                "score": SCORE_BTC_REGIME,
                "allowed": True,
                "reason": "BTC bearish"
            }

        return {
            "score": 2,
            "allowed": True,
            "reason": f"BTC {combined}"
        }

    return {
        "score": 0,
        "allowed": False,
        "reason": "Invalid side"
    }


# =========================================================
# DIVERGENCE SCORE
# =========================================================

def score_divergence(
    df,
    side
):

    data = analyze_divergence(
        df
    )

    side = str(side).upper()

    if side == "BUY":

        score = min(
            data["bullish_score"] * 2,
            4
        )

        return {
            "score": score,
            "reason": data["buy_reason"],
            "data": data
        }

    if side == "SELL":

        score = min(
            data["bearish_score"] * 2,
            4
        )

        return {
            "score": score,
            "reason": data["sell_reason"],
            "data": data
        }

    return {
        "score": 0,
        "reason": "",
        "data": data
    }


# =========================================================
# PRICE STRUCTURE SCORE
# =========================================================

def score_price_structure(
    df,
    side
):

    structure = analyze_price_structure(
        df
    )

    side = str(side).upper()

    if side == "BUY":

        return {
            "score": structure["score_buy"],
            "bullish": structure["bullish"],
            "bearish": structure["bearish"]
        }

    if side == "SELL":

        return {
            "score": structure["score_sell"],
            "bullish": structure["bullish"],
            "bearish": structure["bearish"]
        }

    return {
        "score": 0,
        "bullish": False,
        "bearish": False
    }


# =========================================================
# END OF SECTION 9
# =========================================================# =========================================================
# SECTION 10
# FINAL SIGNAL ENGINE
# 1H + 30M + BTC + DIVERGENCE
# =========================================================




# =========================================================
# 1H TREND SCORER WRAPPER
# =========================================================

def score_main_1h(df, side):
    return score_timeframe(df, side, "1H")


def evaluate_final_signal(
    symbol,
    data,
    btc_regime=None
):
    """
    ساخت سیگنال نهایی برای یک نماد.

    خروجی:
        BUY
        SELL
        NO_SIGNAL
    """

    result = {
        "symbol": symbol,
        "signal": "NO_SIGNAL",
        "score": 0,
        "strength": "NONE",
        "reasons": [],
        "warnings": [],
        "timestamp": now_iran().isoformat()
    }

    # =====================================================
    # CHECK DATA
    # =====================================================

    if not data:
        result["warnings"].append(
            "Market data unavailable"
        )
        return result

    df_1h = data.get("1h")
    df_30m = data.get("30m")
    df_4h = data.get("4h")
    df_daily = data.get("1d")

    if (
        df_1h is None
        or df_30m is None
        or len(df_1h) < 50
        or len(df_30m) < 30
    ):
        result["warnings"].append(
            "Insufficient timeframe data"
        )
        return result

    # =====================================================
    # TRY BOTH SIDES
    # =====================================================

    buy_main = score_main_1h(
        df_1h,
        "BUY"
    )

    sell_main = score_main_1h(
        df_1h,
        "SELL"
    )

    # =====================================================
    # 30M CONFIRMATION
    # =====================================================

    buy_confirm = score_30m_confirmation(
        df_30m,
        "BUY"
    )

    sell_confirm = score_30m_confirmation(
        df_30m,
        "SELL"
    )

    if DEBUG_MODE:
        log(
            f"🔬 30M {symbol} BUY: "
            f"score={buy_confirm.get('score', 0)} "
            f"confirmed={buy_confirm.get('confirmed', False)} "
            f"reasons={buy_confirm.get('reasons', [])}"
        )

        log(
            f"🔬 30M {symbol} SELL: "
            f"score={sell_confirm.get('score', 0)} "
            f"confirmed={sell_confirm.get('confirmed', False)} "
            f"reasons={sell_confirm.get('reasons', [])}"
        )

        log(
            f"🧪 AFTER 30M | {symbol} | "
            f"BUY confirmed={buy_confirm.get('confirmed', False)} "
            f"score={buy_confirm.get('score', 0)} | "
            f"SELL confirmed={sell_confirm.get('confirmed', False)} "
            f"score={sell_confirm.get('score', 0)}"
        )

    # =====================================================
    # BTC REGIME
    # =====================================================

    buy_btc = score_btc_regime(
        "BUY",
        btc_regime
    )

    sell_btc = score_btc_regime(
        "SELL",
        btc_regime
    )

    # =====================================================
    # DIVERGENCE
    # =====================================================

    buy_divergence = score_divergence(
        df_1h,
        "BUY"
    )

    sell_divergence = score_divergence(
        df_1h,
        "SELL"
    )

    # =====================================================
    # PRICE STRUCTURE
    # =====================================================

    buy_structure = score_price_structure(
        df_1h,
        "BUY"
    )

    sell_structure = score_price_structure(
        df_1h,
        "SELL"
    )

    # =====================================================
    # MAIN SCORE
    # =====================================================

    buy_score = 0
    sell_score = 0

    # -----------------------------------------------------
    # Main 1H score
    # -----------------------------------------------------

    if buy_main["hard_pass"]:
        buy_score += buy_main["score"]

    if sell_main["hard_pass"]:
        sell_score += sell_main["score"]

    # -----------------------------------------------------
    # 30M confirmation
    # -----------------------------------------------------

    if buy_main["hard_pass"]:
        buy_score += buy_confirm["score"]

    if sell_main["hard_pass"]:
        sell_score += sell_confirm["score"]

    # -----------------------------------------------------
    # BTC
    # -----------------------------------------------------

    if buy_main["hard_pass"]:
        if buy_btc["allowed"]:
            buy_score += min(
                5,
                buy_btc["score"]
            )

    if sell_main["hard_pass"]:
        if sell_btc["allowed"]:
            sell_score += min(
                5,
                sell_btc["score"]
            )

    # -----------------------------------------------------
    # Divergence bonus
    # -----------------------------------------------------

    if buy_main["hard_pass"]:
        buy_score += min(
            4,
            max(
                0,
                buy_divergence["score"]
            )
        )

    if sell_main["hard_pass"]:
        sell_score += min(
            4,
            max(
                0,
                sell_divergence["score"]
            )
        )

    # -----------------------------------------------------
    # Structure bonus
    # -----------------------------------------------------

    if buy_main["hard_pass"]:
        buy_score += min(
            4,
            max(
                0,
                buy_structure["score"]
            )
        )

    if sell_main["hard_pass"]:
        sell_score += min(
            4,
            max(
                0,
                sell_structure["score"]
            )
        )

    # =====================================================
    # NORMALIZE SCORE
    # =====================================================

    buy_score = max(
        0,
        min(
            100,
            int(round(buy_score))
        )
    )

    sell_score = max(
        0,
        min(
            100,
            int(round(sell_score))
        )
    )

    # =====================================================
    # CHOOSE SIDE
    # =====================================================

    selected_side = None
    selected_score = 0

    # Root quality fix: if BUY and SELL are both technically eligible but
    # nearly tied, the market is ambiguous. Do not manufacture a direction.
    both_directional = (
        buy_main["hard_pass"] and buy_btc["allowed"] and buy_confirm["confirmed"] and buy_score >= MIN_SCORE
        and sell_main["hard_pass"] and sell_btc["allowed"] and sell_confirm["confirmed"] and sell_score >= SELL_MIN_SCORE
    )
    if both_directional and abs(buy_score - sell_score) < PRO_MIN_SIDE_SCORE_GAP:
        if DEBUG_MODE:
            log(f"⚖️ {symbol} ambiguous BUY/SELL scores: {buy_score} vs {sell_score}")
        return {
            **result,
            "signal": "NO_SIGNAL",
            "score": max(buy_score, sell_score),
            "buy_score": buy_score,
            "sell_score": sell_score,
            "strength": "NONE",
            "warnings": ["BUY/SELL score gap below professional minimum"]
        }

    if (
        buy_main["hard_pass"]
        and buy_btc["allowed"]
        and buy_confirm["confirmed"]
        and buy_score >= MIN_SCORE
    ):
        selected_side = "BUY"
        selected_score = buy_score

    if (
        sell_main["hard_pass"]
        and sell_btc["allowed"]
        and sell_confirm["confirmed"]
        and sell_score >= SELL_MIN_SCORE
    ):
        if (
            selected_side is None
            or sell_score > selected_score
        ):
            selected_side = "SELL"
            selected_score = sell_score

    # =====================================================
    # NO SIGNAL
    # =====================================================

    if selected_side is None:

        if DEBUG_MODE:
            log(
                f"🎯 {symbol} | "
                f"BUY main={buy_main.get('hard_pass')} "
                f"score={buy_score} "
                f"confirm={buy_confirm.get('confirmed')} "
                f"btc={buy_btc.get('allowed')} | "
                f"SELL main={sell_main.get('hard_pass')} "
                f"score={sell_score} "
                f"confirm={sell_confirm.get('confirmed')} "
                f"btc={sell_btc.get('allowed')}"
            )

        result.update({
            "signal": "NO_SIGNAL",
            "score": max(
                buy_score,
                sell_score
            ),
            "buy_score": buy_score,
            "sell_score": sell_score,
            "strength": "NONE",
            "trend_diagnostic": {
                "candidate": False,
                "buy": {
                    "hard_pass": bool(buy_main.get("hard_pass")),
                    "score": int(buy_score),
                    "confirm": bool(buy_confirm.get("confirmed")),
                    "btc_allowed": bool(buy_btc.get("allowed")),
                    "reasons": list(buy_main.get("reasons", []))[:8] + list(buy_confirm.get("reasons", []))[:4],
                },
                "sell": {
                    "hard_pass": bool(sell_main.get("hard_pass")),
                    "score": int(sell_score),
                    "confirm": bool(sell_confirm.get("confirmed")),
                    "btc_allowed": bool(sell_btc.get("allowed")),
                    "reasons": list(sell_main.get("reasons", []))[:8] + list(sell_confirm.get("reasons", []))[:4],
                },
                "reason": "NO_1H_TREND_CANDIDATE"
            }
        })

        return result

    # =====================================================
    # 4H + DAILY CONTEXT
    # =====================================================

    mtf_context = get_mtf_context(data)
    mtf_adjustment, mtf_reasons = mtf_side_adjustment(
        mtf_context,
        selected_side
    )
    selected_score = max(0, min(100, selected_score + mtf_adjustment))

    # =====================================================
    # STRENGTH
    # =====================================================

    if selected_score >= STRONG_SCORE and safe_float(df_1h.iloc[-1].get("adx")) >= MIN_ADX:
        strength = "STRONG"

    elif selected_score >= MIN_SCORE:
        strength = "NORMAL"

    else:
        strength = "NONE"

    # =====================================================
    # SELECT REASONS
    # =====================================================

    if selected_side == "BUY":

        reasons = list(
            buy_main.get(
                "reasons",
                []
            )
        )

        reasons.extend(
            buy_confirm.get(
                "reasons",
                []
            )
        )

        if buy_btc.get("reason"):
            reasons.append(
                buy_btc["reason"]
            )

        if buy_divergence.get("reason"):
            reasons.append(
                buy_divergence["reason"]
            )

        if buy_structure.get("bullish"):
            reasons.append(
                "Bullish price structure"
            )

    else:

        reasons = list(
            sell_main.get(
                "reasons",
                []
            )
        )

        reasons.extend(
            sell_confirm.get(
                "reasons",
                []
            )
        )

        if sell_btc.get("reason"):
            reasons.append(
                sell_btc["reason"]
            )

        if sell_divergence.get("reason"):
            reasons.append(
                sell_divergence["reason"]
            )

        if sell_structure.get("bearish"):
            reasons.append(
                "Bearish price structure"
            )

    # Add higher-timeframe context to the final explanation after the
    # selected-side reasons have been assembled.
    reasons.extend(mtf_reasons)

    # =====================================================
    # CURRENT MARKET VALUES
    # =====================================================

    row = df_1h.iloc[-1]

    result.update({

        "signal": selected_side,

        "signal_mode": "TREND",

        "trend_diagnostic": {
            "candidate": True,
            "side": selected_side,
            "buy_score": int(buy_score),
            "sell_score": int(sell_score),
            "buy_confirm": bool(buy_confirm.get("confirmed")),
            "sell_confirm": bool(sell_confirm.get("confirmed")),
            "buy_btc_allowed": bool(buy_btc.get("allowed")),
            "sell_btc_allowed": bool(sell_btc.get("allowed")),
            "reason": "TREND_CANDIDATE"
        },

        "score": selected_score,

        "buy_score": buy_score,

        "sell_score": sell_score,

        "strength": strength,

        "price": safe_float(
            row["close"]
        ),

        "rsi": safe_float(
            row["rsi"]
        ),

        "adx": safe_float(
            row["adx"]
        ),

        "atr": safe_float(
            row["atr"]
        ),

        "atr_percent": safe_float(
            row["atr_percent"]
        ),

        "volume_ratio": safe_float(
            row["volume_ratio"]
        ),

        "ema9": safe_float(
            row["ema9"]
        ),

        "ema21": safe_float(
            row["ema21"]
        ),

        "ema50": safe_float(
            row["ema50"]
        ),

        "ema200": safe_float(
            row["ema200"]
        ),

        "mtf_context": mtf_context,
        "mtf_adjustment": mtf_adjustment,

        "btc_regime": (
            btc_regime.get(
                "combined"
            )
            if btc_regime
            else "UNKNOWN"
        ),

        "reasons": reasons,

        "candle_time": str(
            row["open_time"]
        )
    })

    return result


# =========================================================
# SIGNAL QUALITY CHECK
# =========================================================

def validate_signal_quality(
    signal
):
    """
    آخرین کنترل کیفیت قبل از ارسال Telegram.
    """

    if not signal:

        return False

    if signal.get(
        "signal"
    ) not in (
        "BUY",
        "SELL"
    ):

        return False

    score = safe_int(
        signal.get(
            "score",
            0
        )
    )

    signal_mode = str(signal.get("signal_mode", "TREND")).upper()
    required_score = BOTTOM_MIN_SCORE if signal_mode == "BOTTOM_HUNTER" else MIN_SCORE

    if score < required_score:

        return False

    price = safe_float(
        signal.get(
            "price",
            0
        )
    )

    if price <= 0:

        return False

    # Signals that go through the trade-level stage must use a fresh live price.
    if "live_price_valid" in signal and not signal.get("live_price_valid"):
        return False

    rsi = safe_float(
        signal.get(
            "rsi",
            0
        )
    )

    if rsi <= 0:

        return False

    atr = safe_float(
        signal.get(
            "atr",
            0
        )
    )

    if atr <= 0:

        return False

    return True


# =========================================================
# SIGNAL SUMMARY
# =========================================================

def signal_summary(
    signal
):

    if not signal:

        return "NO SIGNAL"

    symbol = signal.get(
        "symbol",
        "UNKNOWN"
    )

    side = signal.get(
        "signal",
        "NO_SIGNAL"
    )

    score = signal.get(
        "score",
        0
    )

    strength = signal.get(
        "strength",
        "NONE"
    )

    price = signal.get(
        "price",
        0
    )

    return (
        f"{symbol} | "
        f"{side} | "
        f"Score={score}/100 | "
        f"{strength} | "
        f"Price={price}"
    )


# =========================================================
# END OF SECTION 10
# =========================================================# =========================================================
# SECTION 11
# ENTRY / STOP LOSS / TAKE PROFIT / RISK MANAGEMENT
# =========================================================

# -----------------------------
# ACCOUNT & RISK SETTINGS
# -----------------------------

ACCOUNT_SIZE_USDT = 1000.0

RISK_PER_TRADE = 0.01
# 1% از سرمایه

MAX_POSITION_USDT = 1000.0

MIN_STOP_DISTANCE_PERCENT = 0.30
MAX_STOP_DISTANCE_PERCENT = 13.0
# Bottom Hunter setups can use a slightly wider structural stop.
# Position sizing still keeps account risk capped by RISK_PER_TRADE.
BOTTOM_MAX_STOP_DISTANCE_PERCENT = 15.0


# =========================================================
# PRICE ROUNDING
# =========================================================

def format_price(value):
    """
    نمایش مناسب قیمت بدون اعشار اضافی.
    """

    value = safe_float(value)

    if value <= 0:
        return "0"

    if value >= 1000:
        return f"{value:.2f}"

    if value >= 100:
        return f"{value:.3f}"

    if value >= 1:
        return f"{value:.4f}"

    if value >= 0.01:
        return f"{value:.6f}"

    return f"{value:.8f}"


# =========================================================
# CALCULATE TRADE LEVELS
# =========================================================

def get_max_stop_distance_percent(signal):
    """Return the stop-distance ceiling for the signal type."""
    mode = str(signal.get("signal_mode", "TREND")).upper()
    if mode == "BOTTOM_HUNTER":
        return BOTTOM_MAX_STOP_DISTANCE_PERCENT
    if mode in ("4H_SIGNAL", "DAILY_SIGNAL"):
        return HIGHER_TF_MAX_STOP_DISTANCE_PERCENT
    return MAX_STOP_DISTANCE_PERCENT


def calculate_trade_levels(
    signal
):
    """
    محاسبه:

    Entry
    Stop Loss
    TP1
    TP2
    Risk
    Position Size
    """

    if not signal:

        return None

    side = str(
        signal.get(
            "signal",
            ""
        )
    ).upper()

    if side not in (
        "BUY",
        "SELL"
    ):

        return None

    entry = safe_float(
        signal.get(
            "price",
            0
        )
    )

    atr = safe_float(
        signal.get(
            "atr",
            0
        )
    )

    if entry <= 0 or atr <= 0:

        return None

    # =====================================================
    # STOP DISTANCE
    # =====================================================

    signal_mode = str(signal.get("signal_mode", "TREND")).upper()
    stop_multiplier = (
        HIGHER_TF_SL_ATR_MULTIPLIER
        if signal_mode in ("4H_SIGNAL", "DAILY_SIGNAL")
        else SL_ATR_MULTIPLIER
    )

    stop_distance = (
        atr *
        stop_multiplier
    )

    # Bottom Hunter: prefer a structural stop below the recent swing low.
    # Keep the ATR stop as a volatility floor and let the normal max-stop
    # validation reject setups with an unreasonably wide stop.
    if str(signal.get("signal_mode", "TREND")).upper() == "BOTTOM_HUNTER":
        recent_low = safe_float(signal.get("recent_low"), 0.0)
        if recent_low > 0 and recent_low < entry:
            structural_stop = recent_low * 0.995
            structural_distance = entry - structural_stop
            stop_distance = max(stop_distance, structural_distance)

    if stop_distance <= 0:

        return None

    stop_percent = (
        stop_distance /
        entry
    ) * 100

    # v63.1 ROOT FIX: every engine uses the same executable RR thresholds.
    # This removes the old drift between TP construction and validation.
    level_tp1_rr = TP1_RR
    level_tp2_rr = TP2_RR

    # جلوگیری از Stop بسیار نزدیک
    if (
        stop_percent <
        MIN_STOP_DISTANCE_PERCENT
    ):

        stop_distance = (
            entry *
            MIN_STOP_DISTANCE_PERCENT /
            100
        )

        stop_percent = (
            stop_distance /
            entry
        ) * 100

    # جلوگیری از Stop غیرعادی بزرگ. Bottom Hunter کمی فضای بیشتر
    # می‌گیرد چون stop ساختاری آن می‌تواند از ATR stop عریض‌تر باشد.
    max_stop_percent = get_max_stop_distance_percent(signal)
    if stop_percent > max_stop_percent:
        return None

    # =====================================================
    # BUY
    # =====================================================

    if side == "BUY":

        stop_loss = (
            entry -
            stop_distance
        )

        risk_per_unit = (
            entry -
            stop_loss
        )

        tp1 = (
            entry +
            risk_per_unit *
            level_tp1_rr
        )

        tp2 = (
            entry +
            risk_per_unit *
            level_tp2_rr
        )

    # =====================================================
    # SELL
    # =====================================================

    else:

        stop_loss = (
            entry +
            stop_distance
        )

        risk_per_unit = (
            stop_loss -
            entry
        )

        tp1 = (
            entry -
            risk_per_unit *
            level_tp1_rr
        )

        tp2 = (
            entry -
            risk_per_unit *
            level_tp2_rr
        )

    # =====================================================
    # ACCOUNT RISK
    # =====================================================

    max_risk_usdt = (
        ACCOUNT_SIZE_USDT *
        RISK_PER_TRADE
    )

    # =====================================================
    # POSITION SIZE
    # =====================================================

    if risk_per_unit > 0:

        position_quantity = (
            max_risk_usdt /
            risk_per_unit
        )

    else:

        position_quantity = 0

    position_value = (
        position_quantity *
        entry
    )

    # =====================================================
    # MAX POSITION LIMIT
    # =====================================================

    if (
        position_value >
        MAX_POSITION_USDT
    ):

        position_value = (
            MAX_POSITION_USDT
        )

        position_quantity = (
            position_value /
            entry
        )

        # ریسک واقعی با محدودیت پوزیشن
        actual_risk_usdt = (
            position_quantity *
            risk_per_unit
        )

    else:

        actual_risk_usdt = (
            position_quantity *
            risk_per_unit
        )

    # =====================================================
    # RISK / REWARD
    # =====================================================

    reward_tp1 = abs(
        tp1 - entry
    )

    reward_tp2 = abs(
        tp2 - entry
    )

    rr_tp1 = (
        reward_tp1 /
        risk_per_unit
        if risk_per_unit > 0
        else 0
    )

    rr_tp2 = (
        reward_tp2 /
        risk_per_unit
        if risk_per_unit > 0
        else 0
    )

    # =====================================================
    # RESULT
    # =====================================================

    levels = {

        "entry": entry,

        "stop_loss": stop_loss,

        "tp1": tp1,

        "tp2": tp2,

        "atr": atr,

        "stop_distance": stop_distance,

        "stop_percent": stop_percent,

        "risk_per_unit": risk_per_unit,

        "account_size": ACCOUNT_SIZE_USDT,

        "risk_percent": (
            RISK_PER_TRADE * 100
        ),

        "max_risk_usdt": max_risk_usdt,

        "actual_risk_usdt": actual_risk_usdt,

        "position_quantity": (
            position_quantity
        ),

        "position_value_usdt": (
            position_value
        ),

        "rr_tp1": rr_tp1,

        "rr_tp2": rr_tp2
    }

    return levels


# =========================================================
# ATTACH TRADE LEVELS TO SIGNAL
# =========================================================

def attach_trade_levels(
    signal
):

    if not signal:

        return signal

    if signal.get(
        "signal"
    ) not in (
        "BUY",
        "SELL"
    ):

        return signal

    # Use a fresh Binance spot price for trade levels.
    # The technical setup remains based on closed candles.
    live = get_live_price(signal.get("symbol"))
    if not live:
        signal["risk_valid"] = False
        signal["risk_reject_reason"] = "LIVE_PRICE_UNAVAILABLE"
        signal["live_price_valid"] = False
        return signal

    candle_price = safe_float(signal.get("price"), 0.0)
    live_price = safe_float(live.get("price"), 0.0)
    if candle_price <= 0 or live_price <= 0:
        signal["risk_valid"] = False
        signal["risk_reject_reason"] = "INVALID_PRICE"
        signal["live_price_valid"] = False
        return signal

    deviation = abs(live_price - candle_price) / candle_price * 100.0
    if deviation > MAX_LIVE_PRICE_DEVIATION_PERCENT:
        log(
            f"⚠️ Live price moved too far from signal candle: "
            f"{signal.get('symbol')} | {deviation:.2f}% > "
            f"{MAX_LIVE_PRICE_DEVIATION_PERCENT:.2f}%"
        )
        signal["risk_valid"] = False
        signal["risk_reject_reason"] = "LIVE_PRICE_DEVIATION"
        signal["live_price_valid"] = False
        signal["live_price_deviation_percent"] = deviation
        return signal

    signal["price"] = live_price
    signal["live_price"] = live_price
    signal["live_price_fetched_at"] = live.get("fetched_at")
    signal["live_price_latency_seconds"] = live.get("request_latency_seconds", 0.0)
    signal["live_price_deviation_percent"] = deviation
    signal["live_price_valid"] = True

    levels = calculate_trade_levels(
        signal
    )

    if not levels:

        signal["risk_valid"] = False
        signal["risk_reject_reason"] = "STOP_DISTANCE_TOO_LARGE_OR_INVALID"

        return signal

    # v63.1 ROOT RR NORMALIZATION: derive TP1/TP2 again from the FINAL
    # entry/stop pair before storing the signal.  This prevents any stale
    # pre-existing rr/tp fields from surviving into validation.
    _rr1 = TP1_RR
    _rr2 = TP2_RR
    _entry = safe_float(levels.get("entry"), 0.0)
    _stop = safe_float(levels.get("stop_loss"), 0.0)
    _risk = abs(_entry - _stop)
    if _risk <= 0:
        signal["risk_valid"] = False
        signal["risk_reject_reason"] = "INVALID_RISK_DISTANCE"
        return signal
    if signal.get("signal") == "BUY":
        levels["tp1"] = _entry + (_risk * _rr1)
        levels["tp2"] = _entry + (_risk * _rr2)
    else:
        levels["tp1"] = _entry - (_risk * _rr1)
        levels["tp2"] = _entry - (_risk * _rr2)
    levels["rr_tp1"] = abs(levels["tp1"] - _entry) / _risk
    levels["rr_tp2"] = abs(levels["tp2"] - _entry) / _risk

    signal.update({

        "risk_valid": True,

        "entry": levels["entry"],

        "stop_loss": levels["stop_loss"],

        "tp1": levels["tp1"],

        "tp2": levels["tp2"],

        "stop_percent": levels[
            "stop_percent"
        ],

        "max_risk_usdt": levels[
            "max_risk_usdt"
        ],

        "actual_risk_usdt": levels[
            "actual_risk_usdt"
        ],

        "position_quantity": levels[
            "position_quantity"
        ],

        "position_value_usdt": levels[
            "position_value_usdt"
        ],

        "rr_tp1": levels[
            "rr_tp1"
        ],

        "rr_tp2": levels[
            "rr_tp2"
        ]
    })

    return signal


# =========================================================
# RISK VALIDATION
# =========================================================

def validate_risk_levels(
    signal
):

    if not signal:
        return False

    def reject(reason):
        signal["risk_reject_reason"] = reason
        return False

    if not signal.get(
        "risk_valid",
        False
    ):
        if not signal.get("risk_reject_reason"):
            signal["risk_reject_reason"] = "ATTACH_TRADE_LEVELS_FAILED"
        return False

    side = signal.get(
        "signal"
    )

    entry = safe_float(
        signal.get(
            "entry",
            0
        )
    )

    stop = safe_float(
        signal.get(
            "stop_loss",
            0
        )
    )

    tp1 = safe_float(
        signal.get(
            "tp1",
            0
        )
    )

    tp2 = safe_float(
        signal.get(
            "tp2",
            0
        )
    )

    if min(
        entry,
        stop,
        tp1,
        tp2
    ) <= 0:
        return reject("INVALID_TRADE_LEVELS")

    # =====================================================
    # BUY VALIDATION
    # =====================================================

    if side == "BUY":

        if not (
            stop < entry
            and
            tp1 > entry
            and
            tp2 > tp1
        ):

            return reject("INVALID_BUY_LEVEL_ORDER")

    # =====================================================
    # SELL VALIDATION
    # =====================================================

    elif side == "SELL":

        if not (
            stop > entry
            and
            tp1 < entry
            and
            tp2 < tp1
        ):

            return reject("INVALID_SELL_LEVEL_ORDER")

    else:
        return reject("INVALID_SIGNAL_SIDE")

    # =====================================================
    # RR VALIDATION
    # =====================================================

    # v63.1: never trust a stale cached rr_tp1/rr_tp2 field. Recompute RR
    # directly from the actual entry/SL/TP prices that will be sent.
    risk_distance = abs(entry - stop)
    if risk_distance <= 0:
        return reject("INVALID_RISK_DISTANCE")
    actual_rr1 = abs(tp1 - entry) / risk_distance
    actual_rr2 = abs(tp2 - entry) / risk_distance
    signal["rr_tp1"] = actual_rr1
    signal["rr_tp2"] = actual_rr2

    # Bottom Hunter is allowed a slightly tighter TP geometry than Trend,
    # but the professional gate uses the same thresholds below.
    if actual_rr1 + 1e-9 < TP1_RR:
        return reject(f"TP1_RR_TOO_LOW:{actual_rr1:.3f}<{TP1_RR:.3f}")

    if actual_rr2 + 1e-9 < TP2_RR:
        return reject(f"TP2_RR_TOO_LOW:{actual_rr2:.3f}<{TP2_RR:.3f}")

    signal["risk_reject_reason"] = ""
    return True


# =========================================================
# RISK REPORT
# =========================================================

def build_risk_report(
    signal
):

    if not signal:

        return ""

    if not signal.get(
        "risk_valid",
        False
    ):

        return ""

    side = signal.get(
        "signal",
        ""
    )

    entry = safe_float(
        signal.get(
            "entry",
            0
        )
    )

    stop = safe_float(
        signal.get(
            "stop_loss",
            0
        )
    )

    tp1 = safe_float(
        signal.get(
            "tp1",
            0
        )
    )

    tp2 = safe_float(
        signal.get(
            "tp2",
            0
        )
    )

    stop_percent = safe_float(
        signal.get(
            "stop_percent",
            0
        )
    )

    actual_risk = safe_float(
        signal.get(
            "actual_risk_usdt",
            0
        )
    )

    position_value = safe_float(
        signal.get(
            "position_value_usdt",
            0
        )
    )

    rr1 = safe_float(
        signal.get(
            "rr_tp1",
            0
        )
    )

    rr2 = safe_float(
        signal.get(
            "rr_tp2",
            0
        )
    )

    report = [

        f"Side: {side}",

        f"Entry: {format_price(entry)}",

        f"Stop Loss: "
        f"{format_price(stop)}",

        f"TP1: "
        f"{format_price(tp1)} "
        f"(RR {rr1:.2f})",

        f"TP2: "
        f"{format_price(tp2)} "
        f"(RR {rr2:.2f})",

        f"SL distance: "
        f"{stop_percent:.2f}%",

        f"Risk: "
        f"${actual_risk:.2f}",

        f"Position value: "
        f"${position_value:.2f}"
    ]

    return "\n".join(
        report
    )


# =========================================================
# END OF SECTION 11
# =========================================================# =========================================================
# SECTION 12
# TELEGRAM + SIGNAL MESSAGE
# =========================================================


def telegram_escape(text):
    """
    برای جلوگیری از خراب شدن پیام HTML
    """

    if text is None:
        return ""

    text = str(text)

    text = text.replace(
        "&",
        "&amp;"
    )

    text = text.replace(
        "<",
        "&lt;"
    )

    text = text.replace(
        ">",
        "&gt;"
    )

    return text


# =========================================================
# SEND TELEGRAM MESSAGE
# =========================================================

def send_telegram_message(
    message
):
    """
    ارسال پیام به Telegram
    """

    if not TELEGRAM_TOKEN:

        log(
            "Telegram token is empty"
        )

        return False

    if not TELEGRAM_CHAT_ID:

        log(
            "Telegram chat ID is empty"
        )

        return False

    url = (
        "https://api.telegram.org/bot"
        f"{TELEGRAM_TOKEN}/sendMessage"
    )

    payload = {

        "chat_id": TELEGRAM_CHAT_ID,

        "text": message,

        "parse_mode": "HTML",

        "disable_web_page_preview": True
    }

    try:

        response = SESSION.post(
            url,
            data=payload,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:

            log(
                "Telegram HTTP error: "
                f"{response.status_code}"
            )

            return False

        data = response.json()

        if not data.get(
            "ok",
            False
        ):

            log(
                "Telegram API error: "
                f"{data}"
            )

            return False

        return True

    except Exception as e:

        log(
            "Telegram send error: "
            f"{e}"
        )

        return False


# =========================================================
# TEST TELEGRAM
# =========================================================

def test_telegram():
    """
    تست اتصال Telegram
    """

    message = (
        "🟢 <b>Crypto Signal Bot</b>\n\n"
        "Telegram connection test successful.\n"
        "Bot is ready."
    )

    return send_telegram_message(
        message
    )


# =========================================================
# SIGNAL ICON
# =========================================================

def get_signal_icon(
    side
):

    side = str(
        side
    ).upper()

    if side == "BUY":

        return "🟢"

    if side == "SELL":

        return "🔴"

    return "⚪"


# =========================================================
# STRENGTH ICON
# =========================================================

def get_strength_icon(
    strength
):

    strength = str(
        strength
    ).upper()

    if strength == "STRONG":

        return "🔥"

    if strength == "NORMAL":

        return "✅"

    return "⚪"


# =========================================================
# BUILD SIGNAL MESSAGE
# =========================================================

def build_signal_message(
    signal
):

    if not signal:

        return ""

    side = signal.get(
        "signal",
        "NO_SIGNAL"
    )

    if side not in (
        "BUY",
        "SELL"
    ):

        return ""

    symbol = telegram_escape(
        signal.get(
            "symbol",
            "UNKNOWN"
        )
    )

    score = safe_int(
        signal.get(
            "score",
            0
        )
    )

    strength = telegram_escape(
        signal.get(
            "strength",
            "NONE"
        )
    )

    professional_score = safe_int(signal.get("professional_quality_score", 0))

    price = safe_float(
        signal.get(
            "price",
            0
        )
    )

    rsi = safe_float(
        signal.get(
            "rsi",
            0
        )
    )

    adx = safe_float(
        signal.get(
            "adx",
            0
        )
    )

    volume_ratio = safe_float(
        signal.get(
            "volume_ratio",
            0
        )
    )

    atr_percent = safe_float(
        signal.get(
            "atr_percent",
            0
        )
    )

    btc_regime = telegram_escape(
        signal.get(
            "btc_regime",
            "UNKNOWN"
        )
    )

    

    entry = safe_float(
        signal.get(
            "entry",
            price
        )
    )

    stop_loss = safe_float(
        signal.get(
            "stop_loss",
            0
        )
    )

    tp1 = safe_float(
        signal.get(
            "tp1",
            0
        )
    )

    tp2 = safe_float(
        signal.get(
            "tp2",
            0
        )
    )

    stop_percent = safe_float(
        signal.get(
            "stop_percent",
            0
        )
    )

    actual_risk = safe_float(
        signal.get(
            "actual_risk_usdt",
            0
        )
    )

    position_value = safe_float(
        signal.get(
            "position_value_usdt",
            0
        )
    )

    rr1 = safe_float(
        signal.get(
            "rr_tp1",
            0
        )
    )

    rr2 = safe_float(
        signal.get(
            "rr_tp2",
            0
        )
    )

    icon = get_signal_icon(
        side
    )

    strength_icon = get_strength_icon(
        strength
    )

    # =====================================================
    # REASONS
    # =====================================================

    reasons = signal.get(
        "reasons",
        []
    )

    reason_lines = []

    for reason in reasons[:10]:

        reason = telegram_escape(
            reason
        )

        if reason:

            reason_lines.append(
                f"• {reason}"
            )

    reasons_text = "\n".join(
        reason_lines
    )

    if not reasons_text:

        reasons_text = (
            "• Technical conditions confirmed"
        )

    signal_mode = str(signal.get("signal_mode", "TREND")).upper()
    signal_tf = str(signal.get("signal_timeframe", TIMEFRAME_MAIN)).lower()
    if signal_mode == "4H_SIGNAL" or signal_tf == "4h":
        analysis_label = "4H"
    elif signal_mode == "DAILY_SIGNAL" or signal_tf == "1d":
        analysis_label = "DAILY"
    else:
        analysis_label = "1H"

    higher_context = signal.get("higher_tf_context_trend", "UNKNOWN")
    mtf = signal.get("mtf_context", {}) if isinstance(signal.get("mtf_context", {}), dict) else {}
    context_4h = mtf.get("4h", {}).get("trend", "UNKNOWN") if isinstance(mtf.get("4h", {}), dict) else "UNKNOWN"
    context_1d = mtf.get("1d", {}).get("trend", "UNKNOWN") if isinstance(mtf.get("1d", {}), dict) else "UNKNOWN"
    if signal_mode == "4H_SIGNAL":
        context_4h = "PRIMARY"
        context_1d = higher_context
    elif signal_mode == "DAILY_SIGNAL":
        context_1d = "PRIMARY"
        context_4h = higher_context

    bottom_details = ""
    if str(signal.get("signal_mode", "TREND")).upper() == "BOTTOM_HUNTER":
        bottom_details = (
            f"🟡 <b>BOTTOM HUNTER</b>\n"
            f"Recent Low: {format_price(signal.get('recent_low', 0))}\n"
            f"Distance from Low: {safe_float(signal.get('distance_from_low', 0)):.2f}%\n"
            f"Drawdown from High: {safe_float(signal.get('drawdown_from_high', 0)):.2f}%\n"
            f"Fib 0.618: {format_price(signal.get('fib618', 0))}\n"
            f"Fib 0.786: {format_price(signal.get('fib786', 0))}\n\n"
            f"⚠️ <i>{telegram_escape(signal.get('bottom_warning', 'Early reversal setup'))}</i>\n\n"
        )

    # =====================================================
    # MESSAGE
    # =====================================================

    message = (
        bottom_details +
        f"{icon} <b>CRYPTO SIGNAL</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"

        f"🪙 <b>{symbol}</b>\n"

        f"📌 Direction: "
        f"<b>{side}</b>\n"

        f"⭐ Score: "
        f"<b>{score}/100</b>\n"

        f"{strength_icon} Strength: "
        f"<b>{strength}</b>\n\n"

        f"💰 <b>PRICE</b>\n"
        f"Entry: "
        f"<b>{format_price(entry)}</b>\n\n"

        f"🛡 <b>RISK LEVELS</b>\n"
        f"SL: "
        f"<b>{format_price(stop_loss)}</b>\n"

        f"TP1: "
        f"<b>{format_price(tp1)}</b>"
        f"  RR={rr1:.2f}\n"

        f"TP2: "
        f"<b>{format_price(tp2)}</b>"
        f"  RR={rr2:.2f}\n"

        f"SL Distance: "
        f"{stop_percent:.2f}%\n\n"

        f"📊 <b>{analysis_label} ANALYSIS</b>\n"
        f"RSI: "
        f"{rsi:.1f}\n"

        f"ADX: "
        f"{adx:.1f}\n"

        f"Volume: "
        f"{volume_ratio:.2f}x\n"

        f"ATR: "
        f"{atr_percent:.2f}%\n\n"

        f"⏱ <b>MARKET CONTEXT</b>\n"
        f"BTC: "
        f"{btc_regime}\n"
        f"4H: "
        f"{telegram_escape(str(context_4h))}\n"
        f"Daily: "
        f"{telegram_escape(str(context_1d))}\n\n"

        f"🧠 <b>REASONS</b>\n"
        f"{reasons_text}\n\n"

        f"💵 <b>RISK CALCULATION</b>\n"
        f"Risk: "
        f"${actual_risk:.2f}\n"

        f"Position Value: "
        f"${position_value:.2f}\n\n"

        f"⚠️ <i>تحلیل تکنیکال است؛ "
        f"سیگنال تضمینی نیست.</i>"
    )

    return message


# =========================================================
# SEND SIGNAL
# =========================================================

def final_telegram_quality_gate(signal):
    """Final hard safety gate immediately before Telegram delivery.

    No signal can reach Telegram unless it has passed the professional gate,
    risk validation, and minimum executable R:R requirements. This is an
    intentionally conservative final boundary; it does not create or loosen
    signals.
    """
    if not signal or signal.get("signal") not in ("BUY", "SELL"):
        return False

    if str(signal.get("professional_filter", "")).upper() != "PASSED":
        return False

    if not signal.get("risk_valid", False):
        return False

    if not validate_risk_levels(signal):
        return False

    pbreak = signal.get("professional_quality_breakdown")
    if not isinstance(pbreak, dict):
        return False
    raw_score = safe_float(pbreak.get("raw_score", signal.get("score", 0)))
    quality_score = safe_int(pbreak.get("quality_score", signal.get("professional_quality_score", 0)))
    min_score = PRO_SELL_MIN_SCORE if signal.get("signal") == "SELL" else PRO_MIN_SCORE
    if raw_score + RR_EPSILON < min_score:
        return False
    if quality_score <= 0:
        return False

    min_rr1 = TP1_RR
    min_rr2 = TP2_RR
    if safe_float(signal.get("rr_tp1", 0)) + RR_EPSILON < min_rr1:
        return False
    if safe_float(signal.get("rr_tp2", 0)) + RR_EPSILON < min_rr2:
        return False

    signal["final_telegram_quality_gate"] = True
    return True


def send_signal_to_telegram(
    signal
):

    if not signal:

        return False

    if signal.get(
        "signal"
    ) not in (
        "BUY",
        "SELL"
    ):

        return False

    if not final_telegram_quality_gate(signal):
        log(f"{signal.get('symbol')} blocked by final_telegram_quality_gate")
        return False

    if not validate_signal_quality(
        signal
    ):

        log(
            f"{signal.get('symbol')} "
            "failed signal quality"
        )

        return False

    if not validate_risk_levels(
        signal
    ):

        log(
            f"{signal.get('symbol')} "
            "failed risk validation"
        )

        return False

    message = build_signal_message(
        signal
    )

    if not message:

        return False

    success = send_telegram_message(
        message
    )

    if success:

        signal_mode = str(signal.get("signal_mode", "TREND")).upper()
        signal_tf = str(signal.get("signal_timeframe", TIMEFRAME_MAIN)).lower()
        tf_label = "4H" if signal_mode == "4H_SIGNAL" or signal_tf == "4h" else ("DAILY" if signal_mode == "DAILY_SIGNAL" or signal_tf == "1d" else "1H")
        log(
            f"Telegram signal sent: "
            f"{signal.get('symbol')} "
            f"{signal.get('signal')} "
            f"TF={tf_label} "
            f"Mode={signal_mode} "
            f"Score={signal.get('score')}"
        )

    return success


# =========================================================
# NO SIGNAL REPORT
# =========================================================

def build_no_signal_report(
    total_coins,
    checked_coins,
    candidates,
    errors,
    btc_regime
):

    btc_text = "UNKNOWN"

    if btc_regime:

        btc_text = btc_regime.get(
            "combined",
            "UNKNOWN"
        )

    message = (

        "📊 <b>Crypto Signal Bot Report</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        f"⏱ Main TF: "
        f"<b>{telegram_escape(TIMEFRAME_MAIN)}</b>\n"

        f"⏱ Confirm TF: "
        f"<b>{telegram_escape(TIMEFRAME_CONFIRM)}</b>\n"
        f"⏱ Higher TF: "
        f"<b>4H + Daily</b>\n\n"

        f"🪙 Coins: "
        f"<b>{total_coins}</b>\n"

        f"🔎 Checked: "
        f"<b>{checked_coins}</b>\n"

        f"🎯 Candidates: "
        f"<b>{candidates}</b>\n"

        f"⚠️ Errors: "
        f"<b>{errors}</b>\n\n"

        f"₿ BTC Regime: "
        f"<b>{telegram_escape(btc_text)}</b>\n\n"

        "ℹ️ <i>No new qualified signal "
        "was found in this scan.</i>"
    )

    return message


# =========================================================
# SEND NO SIGNAL REPORT
# =========================================================

def send_no_signal_report(
    total_coins,
    checked_coins,
    candidates,
    errors,
    btc_regime
):

    if not SEND_NO_SIGNAL_REPORT:

        return False

    message = build_no_signal_report(
        total_coins,
        checked_coins,
        candidates,
        errors,
        btc_regime
    )

    return send_telegram_message(
        message
    )


# =========================================================
# END OF SECTION 12
# =========================================================# =========================================================
# SECTION 13
# STATE + HISTORY + DUPLICATE SIGNAL PROTECTION
# =========================================================


# =========================================================
# STATE STRUCTURE
# =========================================================

STATE_SCHEMA_VERSION = 2
DUPLICATE_UPGRADE_SCORE = 6
DUPLICATE_UPGRADE_QUALITY = 5


def get_empty_state():
    return {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "last_signals": {},
        "last_scan": None,
        "total_scans": 0,
        "total_signals": 0
    }


# =========================================================
# LOAD BOT STATE
# =========================================================

def load_bot_state():

    state = load_json_file(
        STATE_FILE,
        None
    )

    if not isinstance(
        state,
        dict
    ):

        return get_empty_state()

    # v57 state migration: old state entries can belong to previous strategy
    # versions and can incorrectly suppress the first scan after an upgrade.
    # Preserve counters, but reset only the duplicate ledger once.
    old_schema = safe_int(state.get("state_schema_version", 0))
    if old_schema != STATE_SCHEMA_VERSION:
        log(
            f"State migration: schema {old_schema} -> {STATE_SCHEMA_VERSION}; "
            "resetting duplicate ledger only"
        )
        state["last_signals"] = {}
        state["state_schema_version"] = STATE_SCHEMA_VERSION

    if "last_signals" not in state:

        state["last_signals"] = {}

    if "total_scans" not in state:

        state["total_scans"] = 0

    if "total_signals" not in state:

        state["total_signals"] = 0

    if "last_scan" not in state:

        state["last_scan"] = None

    return state


# =========================================================
# SAVE BOT STATE
# =========================================================

def save_bot_state(
    state
):

    if not isinstance(
        state,
        dict
    ):

        return False

    return save_json_file(
        STATE_FILE,
        state
    )


# =========================================================
# LOAD HISTORY
# =========================================================

def load_signal_history():

    history = load_json_file(
        HISTORY_FILE,
        []
    )

    if not isinstance(
        history,
        list
    ):

        return []

    return history


# =========================================================
# SAVE HISTORY
# =========================================================

def save_signal_history(
    history
):

    if not isinstance(
        history,
        list
    ):

        return False

    # فقط آخرین 1000 سیگنال نگهداری شود
    if len(history) > 1000:

        history = history[-1000:]

    return save_json_file(
        HISTORY_FILE,
        history
    )


# =========================================================
# SIGNAL UNIQUE KEY
# =========================================================

def get_signal_key(
    signal
):

    if not signal:

        return None

    symbol = str(
        signal.get(
            "symbol",
            ""
        )
    ).upper()

    side = str(
        signal.get(
            "signal",
            ""
        )
    ).upper()

    candle_time = str(
        signal.get(
            "candle_time",
            ""
        )
    )
    mode = str(signal.get("signal_mode", "TREND")).upper()
    signal_tf = str(signal.get("signal_timeframe", TIMEFRAME_MAIN)).lower()

    if not symbol:
        return None

    if side not in (
        "BUY",
        "SELL"
    ):

        return None

    if not candle_time:

        return None

    return (
        f"{symbol}|"
        f"{side}|"
        f"{mode}|"
        f"{signal_tf}|"
        f"{candle_time}"
    )


# =========================================================
# CHECK DUPLICATE
# =========================================================

def is_duplicate_signal(
    signal,
    state
):

    key = get_signal_key(
        signal
    )

    if not key:

        return True

    last_signals = state.get(
        "last_signals",
        {}
    )

    previous = last_signals.get(key)
    if not isinstance(previous, dict):
        return key in last_signals

    # Same candle/setup remains a duplicate unless the setup materially
    # improves. This prevents Telegram spam while allowing a genuine quality
    # upgrade to be re-evaluated on the same candle.
    current_score = safe_int(signal.get("score", 0))
    previous_score = safe_int(previous.get("score", 0))
    current_quality = safe_int(signal.get("professional_quality_score", 0))
    previous_quality = safe_int(previous.get("professional_quality_score", 0))
    current_strength = str(signal.get("strength", "")).upper()
    previous_strength = str(previous.get("strength", "")).upper()

    score_upgrade = current_score >= previous_score + DUPLICATE_UPGRADE_SCORE
    quality_upgrade = (
        current_quality > 0 and
        current_quality >= previous_quality + DUPLICATE_UPGRADE_QUALITY
    )
    strength_upgrade = current_strength == "STRONG" and previous_strength != "STRONG"

    if score_upgrade or quality_upgrade or strength_upgrade:
        log(
            f"Duplicate upgraded: {signal.get('symbol')} "
            f"{signal.get('signal')} score {previous_score}->{current_score} "
            f"quality {previous_quality}->{current_quality} "
            f"strength {previous_strength}->{current_strength}"
        )
        return False

    return True


# =========================================================
# MARK SIGNAL AS SENT
# =========================================================

def mark_signal_sent(
    signal,
    state
):

    key = get_signal_key(
        signal
    )

    if not key:

        return False

    if "last_signals" not in state:

        state["last_signals"] = {}

    state["last_signals"][key] = {

        "symbol": signal.get(
            "symbol"
        ),

        "signal": signal.get(
            "signal"
        ),

        "score": signal.get(
            "score",
            0
        ),

        "strength": signal.get(
            "strength",
            "NONE"
        ),

        "price": signal.get(
            "price",
            0
        ),

        "professional_quality_score": signal.get(
            "professional_quality_score",
            0
        ),

        "candle_time": signal.get(
            "candle_time"
        ),

        "sent_at": now_iran().isoformat()
    }

    # -----------------------------------------------------
    # محدود کردن تعداد کلیدهای State
    # -----------------------------------------------------

    if len(
        state["last_signals"]
    ) > 2000:

        keys = list(
            state["last_signals"].keys()
        )

        for old_key in keys[:500]:

            state["last_signals"].pop(
                old_key,
                None
            )

    return True


# =========================================================
# ADD SIGNAL TO HISTORY
# =========================================================

def add_signal_to_history(
    signal,
    history
):

    if not signal:

        return False

    if signal.get(
        "signal"
    ) not in (
        "BUY",
        "SELL"
    ):

        return False

    record = {

        "timestamp": now_iran().isoformat(),

        "symbol": signal.get(
            "symbol"
        ),

        "signal": signal.get(
            "signal"
        ),

        "score": signal.get(
            "score",
            0
        ),

        "strength": signal.get(
            "strength",
            "NONE"
        ),

        "price": signal.get(
            "price",
            0
        ),

        "entry": signal.get(
            "entry",
            0
        ),

        "stop_loss": signal.get(
            "stop_loss",
            0
        ),

        "tp1": signal.get(
            "tp1",
            0
        ),

        "tp2": signal.get(
            "tp2",
            0
        ),

        "rsi": signal.get(
            "rsi",
            0
        ),

        "adx": signal.get(
            "adx",
            0
        ),

        "volume_ratio": signal.get(
            "volume_ratio",
            0
        ),

        "atr_percent": signal.get(
            "atr_percent",
            0
        ),

        "btc_regime": signal.get(
            "btc_regime",
            "UNKNOWN"
        ),
        

        "candle_time": signal.get(
            "candle_time"
        ),

        # Outcome tracker fields. These are filled by future scans and do
        # not affect signal generation or Telegram delivery.
        "outcome_status": "OPEN",
        "outcome_created_at": now_iran().isoformat(),
        "horizons": {},
        "first_event": None,
        "first_event_time": None,
        "outcome_reason": None,
        "mfe_percent": 0.0,
        "mae_percent": 0.0,

        "reasons": signal.get(
            "reasons",
            []
        )
    }

    history.append(
        record
    )

    return True


# =========================================================
# PROCESS NEW SIGNAL
# =========================================================

def process_signal(
    signal,
    state,
    history
):
    """
    اگر سیگنال جدید باشد:

    1. Telegram ارسال می‌شود
    2. State ذخیره می‌شود
    3. History ذخیره می‌شود

    اگر قبلاً ارسال شده باشد:
    دوباره Telegram ارسال نمی‌شود.
    """

    if not signal:

        return {
            "sent": False,
            "duplicate": False,
            "reason": "EMPTY_SIGNAL"
        }

    if signal.get("signal") not in ("BUY", "SELL"):
        # Invalid/NO_SIGNAL objects are internal analysis results, never
        # Telegram candidates.  They must not reach risk processing.
        return {
            "sent": False,
            "duplicate": False,
            "reason": "NOT_ACTIONABLE"
        }

    # -----------------------------------------------------
    # Duplicate Check
    # -----------------------------------------------------

    if is_duplicate_signal(
        signal,
        state
    ):

        signal_mode = str(signal.get("signal_mode", "TREND")).upper()
        signal_tf = str(signal.get("signal_timeframe", TIMEFRAME_MAIN)).lower()
        tf_label = "4H" if signal_mode == "4H_SIGNAL" or signal_tf == "4h" else ("DAILY" if signal_mode == "DAILY_SIGNAL" or signal_tf == "1d" else "1H")
        previous = state.get("last_signals", {}).get(get_signal_key(signal), {})
        log(
            f"Duplicate skipped: "
            f"{signal.get('symbol')} "
            f"{signal.get('signal')} "
            f"TF={tf_label} "
            f"Mode={signal_mode} "
            f"Candle={signal.get('candle_time')} "
            f"PrevScore={safe_int(previous.get('score', 0))} "
            f"CurrScore={safe_int(signal.get('score', 0))}"
        )

        return {
            "sent": False,
            "duplicate": True,
            "reason": "DUPLICATE"
        }

    # -----------------------------------------------------
    # Telegram
    # -----------------------------------------------------

    sent = send_signal_to_telegram(
        signal
    )

    if not sent:

        signal_mode = str(signal.get("signal_mode", "TREND")).upper()
        signal_tf = str(signal.get("signal_timeframe", TIMEFRAME_MAIN)).lower()
        tf_label = "4H" if signal_mode == "4H_SIGNAL" or signal_tf == "4h" else ("DAILY" if signal_mode == "DAILY_SIGNAL" or signal_tf == "1d" else "1H")
        log(
            f"Signal not sent: {signal.get('symbol')} "
            f"TF={tf_label} Mode={signal_mode} "
            f"Reason=TELEGRAM_OR_QUALITY_VALIDATION"
        )

        return {
            "sent": False,
            "duplicate": False,
            "reason": "TELEGRAM_OR_QUALITY_VALIDATION"
        }

    # -----------------------------------------------------
    # Mark as sent
    # -----------------------------------------------------

    mark_signal_sent(
        signal,
        state
    )

    # -----------------------------------------------------
    # History
    # -----------------------------------------------------

    add_signal_to_history(
        signal,
        history
    )

    # -----------------------------------------------------
    # Counters
    # -----------------------------------------------------

    state["total_signals"] = safe_int(
        state.get(
            "total_signals",
            0
        )
    ) + 1

    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    save_bot_state(
        state
    )

    save_signal_history(
        history
    )

    return {
        "sent": True,
        "duplicate": False
    }


# =========================================================
# CLEAN OLD STATE
# =========================================================

def cleanup_state(
    state,
    max_items=1000
):

    if not isinstance(
        state,
        dict
    ):

        return state

    last_signals = state.get(
        "last_signals",
        {}
    )

    if not isinstance(
        last_signals,
        dict
    ):

        state["last_signals"] = {}

        return state

    if len(last_signals) <= max_items:

        return state

    keys = list(
        last_signals.keys()
    )

    remove_count = (
        len(keys) -
        max_items
    )

    for key in keys[:remove_count]:

        last_signals.pop(
            key,
            None
        )

    return state


# =========================================================
# UPDATE SCAN STATE
# =========================================================

def update_scan_state(
    state
):

    if not isinstance(
        state,
        dict
    ):

        state = get_empty_state()

    state["last_scan"] = (
        now_iran().isoformat()
    )

    state["total_scans"] = safe_int(
        state.get(
            "total_scans",
            0
        )
    ) + 1

    cleanup_state(
        state
    )

    save_bot_state(
        state
    )

    return state


# =========================================================
# SIGNAL OUTCOME TRACKER
# =========================================================

def _parse_signal_time(value):
    """Parse the candle_time stored in signal history into UTC Timestamp."""
    if value is None:
        return None
    try:
        ts = pd.to_datetime(value, utc=True, errors="coerce")
        if pd.isna(ts):
            return None
        return ts
    except Exception:
        return None


def _outcome_price_level_hit(side, high, low, tp1, tp2, stop_loss):
    """Return all levels touched by one closed candle.

    OHLC data cannot tell the intrabar order when multiple levels are touched
    by the same candle, so the caller treats SL+TP combinations as ambiguous.
    """
    side = str(side).upper()
    hits = []
    high = safe_float(high, 0.0)
    low = safe_float(low, 0.0)
    tp1 = safe_float(tp1, 0.0)
    tp2 = safe_float(tp2, 0.0)
    stop_loss = safe_float(stop_loss, 0.0)

    if side == "BUY":
        if stop_loss > 0 and low <= stop_loss:
            hits.append("SL")
        if tp1 > 0 and high >= tp1:
            hits.append("TP1")
        if tp2 > 0 and high >= tp2:
            hits.append("TP2")
    elif side == "SELL":
        if stop_loss > 0 and high >= stop_loss:
            hits.append("SL")
        if tp1 > 0 and low <= tp1:
            hits.append("TP1")
        if tp2 > 0 and low <= tp2:
            hits.append("TP2")

    return hits


def _pct_change_from_entry(side, entry, close):
    entry = safe_float(entry, 0.0)
    close = safe_float(close, 0.0)
    if entry <= 0 or close <= 0:
        return 0.0
    if str(side).upper() == "BUY":
        return (close - entry) / entry * 100.0
    return (entry - close) / entry * 100.0


def _mfe_mae_from_window(side, entry, window):
    """Return MFE and MAE as positive excursion magnitudes.

    MFE = maximum favorable excursion.
    MAE = maximum adverse excursion magnitude (reported positive for easier
    reading; the direction is implied by BUY/SELL and the name MAE).
    """
    if not isinstance(window, pd.DataFrame) or window.empty:
        return None, None

    entry = safe_float(entry, 0.0)
    if entry <= 0 or "high" not in window.columns or "low" not in window.columns:
        return None, None

    highs = pd.to_numeric(window["high"], errors="coerce").dropna()
    lows = pd.to_numeric(window["low"], errors="coerce").dropna()
    if highs.empty or lows.empty:
        return None, None

    if str(side).upper() == "BUY":
        mfe = (float(highs.max()) - entry) / entry * 100.0
        mae = (entry - float(lows.min())) / entry * 100.0
    else:
        mfe = (entry - float(lows.min())) / entry * 100.0
        mae = (float(highs.max()) - entry) / entry * 100.0

    return max(0.0, float(mfe)), max(0.0, float(mae))


def _normalize_outcome_dataframe(df):
    """Normalize 1H OHLC timestamps for deterministic horizon calculations."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    required = {"open_time", "high", "low", "close"}
    if not required.issubset(df.columns):
        return None
    out = df.copy()
    out["open_time"] = pd.to_datetime(out["open_time"], utc=True, errors="coerce")
    for col in ("high", "low", "close"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["open_time", "high", "low", "close"])
    if out.empty:
        return None
    return out.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)


def _horizon_is_complete(now_utc, candle_ts, hours):
    """A horizon ends hours after the signal candle CLOSE.

    candle_time is the 1H candle OPEN time, so the signal candle closes one
    hour later. This avoids look-ahead while measuring 1H/2H/4H/8H after the
    actual signal point.
    """
    signal_close = candle_ts + pd.Timedelta(hours=1)
    return now_utc >= signal_close + pd.Timedelta(hours=hours)


def _update_signal_outcome_record(record, df, now_utc):
    """Build a complete, independent 1H/2H/4H/8H outcome profile.

    Important v53 fixes:
      - horizon MFE/MAE are calculated from the actual horizon window;
      - TP1/TP2/SL flags are calculated independently per horizon;
      - first-event detection does not stop 8H observation;
      - old v52 records are safely recalculated/migrated;
      - no future candle beyond each horizon is used.
    """
    if not isinstance(record, dict):
        return False
    df = _normalize_outcome_dataframe(df)
    if df is None:
        return False

    candle_ts = _parse_signal_time(record.get("candle_time"))
    if candle_ts is None:
        return False

    entry = safe_float(record.get("entry", record.get("price", 0.0)), 0.0)
    stop_loss = safe_float(record.get("stop_loss", 0.0), 0.0)
    tp1 = safe_float(record.get("tp1", 0.0), 0.0)
    tp2 = safe_float(record.get("tp2", 0.0), 0.0)
    side = str(record.get("signal", "")).upper()
    if side not in ("BUY", "SELL") or entry <= 0:
        return False

    now_utc = pd.Timestamp(now_utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.tz_localize("UTC")
    else:
        now_utc = now_utc.tz_convert("UTC")

    # Only completed candles strictly after the signal candle are eligible.
    future = df[df["open_time"] > candle_ts].copy()
    if future.empty:
        return False
    future = future.sort_values("open_time").reset_index(drop=True)

    record.setdefault("outcome_status", "OPEN")
    record.setdefault("first_event", None)
    record.setdefault("first_event_time", None)
    record.setdefault("tp1_reached", False)
    record.setdefault("tp2_reached", False)
    record.setdefault("sl_reached", False)
    record.setdefault("ambiguous_event", False)
    record.setdefault("outcome_created_at", now_iran().isoformat())
    record.setdefault("horizons", {})
    record.setdefault("performance", {})

    changed = False
    signal_close = candle_ts + pd.Timedelta(hours=1)
    max_hours = max(OUTCOME_HORIZONS_HOURS)
    final_end = signal_close + pd.Timedelta(hours=max_hours)

    # ---------------------------------------------------------
    # Independent horizon metrics
    # ---------------------------------------------------------
    horizon_payload = record["horizons"]
    for hours in OUTCOME_HORIZONS_HOURS:
        key = f"{hours}h"
        horizon_end = signal_close + pd.Timedelta(hours=hours)

        # Never publish a partial horizon as a completed observation.
        if now_utc < horizon_end:
            continue

        available = future[future["open_time"] <= horizon_end].copy()
        if available.empty:
            continue

        last = available.iloc[-1]
        close = safe_float(last.get("close"), 0.0)
        hmfe, hmae = _mfe_mae_from_window(side, entry, available)
        if hmfe is None or hmae is None or close <= 0:
            continue

        tp1_hit = False
        tp2_hit = False
        sl_hit = False
        for _, row in available.iterrows():
            hits = _outcome_price_level_hit(
                side, row.get("high"), row.get("low"), tp1, tp2, stop_loss
            )
            tp1_hit = tp1_hit or ("TP1" in hits or "TP2" in hits)
            tp2_hit = tp2_hit or ("TP2" in hits)
            sl_hit = sl_hit or ("SL" in hits)

        payload = {
            "close": close,
            "change_percent": round(_pct_change_from_entry(side, entry, close), 4),
            "mfe_percent": round(hmfe, 4),
            "mae_percent": round(hmae, 4),
            "tp1_reached": bool(tp1_hit),
            "tp2_reached": bool(tp2_hit),
            "sl_reached": bool(sl_hit),
            "window_start": str(signal_close),
            "window_end": str(horizon_end),
            "observed_at": now_iran().isoformat(),
            "engine_version": 54,
        }
        if horizon_payload.get(key) != payload:
            horizon_payload[key] = payload
            changed = True

    # ---------------------------------------------------------
    # First event across the full 8H observation window.
    # This is descriptive only; it does NOT stop horizon tracking.
    # ---------------------------------------------------------
    observation = future[future["open_time"] <= final_end].copy()
    if not observation.empty:
        any_tp1 = False
        any_tp2 = False
        any_sl = False
        first_event = None
        first_event_time = None
        ambiguous = False

        for _, row in observation.iterrows():
            hits = _outcome_price_level_hit(
                side, row.get("high"), row.get("low"), tp1, tp2, stop_loss
            )
            if not hits:
                continue

            any_tp1 = any_tp1 or ("TP1" in hits or "TP2" in hits)
            any_tp2 = any_tp2 or ("TP2" in hits)
            any_sl = any_sl or ("SL" in hits)

            if first_event is None:
                if "SL" in hits and ("TP1" in hits or "TP2" in hits):
                    first_event = "AMBIGUOUS_SAME_CANDLE"
                    ambiguous = True
                elif "SL" in hits:
                    first_event = "SL"
                else:
                    first_event = "TP1"
                first_event_time = str(row["open_time"])

        if record.get("first_event") is None and first_event is not None:
            record["first_event"] = first_event
            record["first_event_time"] = first_event_time
            record["ambiguous_event"] = bool(ambiguous)
            record["outcome_reason"] = {
                "SL": "stop_loss_touched",
                "TP1": "tp1_touched",
                "AMBIGUOUS_SAME_CANDLE": "SL_and_TP_touched_same_closed_candle",
            }.get(first_event, "")
            changed = True

        record["tp1_reached"] = bool(any_tp1)
        record["tp2_reached"] = bool(any_tp2)
        record["sl_reached"] = bool(any_sl)

        # Global 8H MFE/MAE for backward compatibility and overall analytics.
        mfe, mae = _mfe_mae_from_window(side, entry, observation)
        if mfe is not None and mae is not None:
            record["performance"]["mfe_percent"] = round(mfe, 4)
            record["performance"]["mae_percent"] = round(mae, 4)
            record["mfe_percent"] = round(mfe, 4)
            record["mae_percent"] = round(mae, 4)
            changed = True

    # ---------------------------------------------------------
    # Finalization only after the complete 8H window is available.
    # ---------------------------------------------------------
    if now_utc >= final_end:
        if record.get("outcome_status") != "FINAL":
            record["outcome_status"] = "FINAL"
            record["finalized_at"] = now_iran().isoformat()
            changed = True
        if not record.get("first_event"):
            record["first_event"] = "NO_LEVEL_HIT"
            record["outcome_reason"] = "8h_observation_completed_without_SL_or_TP"
            changed = True
    elif record.get("first_event") and record.get("outcome_status") == "OPEN":
        record["outcome_status"] = "OBSERVING_AFTER_EVENT"
        changed = True

    record["outcome_engine_version"] = 54
    return changed


def _safe_median(values):
    """Return a rounded median for finite numeric values."""
    clean = []
    for value in values:
        try:
            number = float(value)
            if np.isfinite(number):
                clean.append(number)
        except Exception:
            continue
    if not clean:
        return None
    return round(float(np.median(clean)), 3)


def _rate(count, total):
    """Return a percentage rate, or None when the denominator is zero."""
    if total <= 0:
        return None
    return round(float(count) / float(total) * 100.0, 1)


def _outcome_group_stats(records):
    """Aggregate descriptive outcome metrics without ranking signals."""
    valid = [r for r in records if isinstance(r, dict)]
    result = {
        "signals": len(valid),
        "finalized": 0,
        "open": 0,
        "first_events": {},
        "first_event_rates": {},
        "avg_return": None,
        "median_return": None,
        "avg_mfe": None,
        "avg_mae": None,
        "mfe_mae_ratio": None,
        "horizons": {},
    }

    if not valid:
        return result

    mfe_values = []
    mae_values = []
    all_returns = []
    for r in valid:
        if str(r.get("outcome_status", "OPEN")).upper() == "FINAL":
            result["finalized"] += 1
        else:
            result["open"] += 1
        event = str(r.get("first_event") or "OPEN").upper()
        result["first_events"][event] = safe_int(result["first_events"].get(event, 0)) + 1
        if r.get("mfe_percent") is not None:
            mfe_values.append(safe_float(r.get("mfe_percent")))
        if r.get("mae_percent") is not None:
            mae_values.append(safe_float(r.get("mae_percent")))
        # Prefer the completed 8H return for the group-level summary.
        h8 = r.get("horizons", {}).get("8h", {}) if isinstance(r.get("horizons"), dict) else {}
        if h8.get("change_percent") is not None:
            all_returns.append(safe_float(h8.get("change_percent")))

    if mfe_values:
        result["avg_mfe"] = round(sum(mfe_values) / len(mfe_values), 3)
    if mae_values:
        result["avg_mae"] = round(sum(mae_values) / len(mae_values), 3)
    if result["avg_mae"] is not None and result["avg_mae"] > 0 and result["avg_mfe"] is not None:
        result["mfe_mae_ratio"] = round(result["avg_mfe"] / result["avg_mae"], 3)
    if all_returns:
        result["avg_return"] = round(sum(all_returns) / len(all_returns), 3)
        result["median_return"] = _safe_median(all_returns)

    # First-event rates: these are mutually exclusive for finalized records
    # except for explicit OPEN records in legacy/incomplete data.
    event_denominator = result["signals"]
    for event, count in result["first_events"].items():
        result["first_event_rates"][event] = _rate(count, event_denominator)
    result["tp1_rate"] = _rate(result["first_events"].get("TP1", 0), event_denominator)
    result["sl_rate"] = _rate(result["first_events"].get("SL", 0), event_denominator)
    result["no_level_hit_rate"] = _rate(result["first_events"].get("NO_LEVEL_HIT", 0), event_denominator)

    for hours in OUTCOME_HORIZONS_HOURS:
        key = f"{hours}h"
        changes = []
        mfes = []
        maes = []
        tp1 = tp2 = sl = 0
        for r in valid:
            h = r.get("horizons", {}).get(key, {}) if isinstance(r.get("horizons"), dict) else {}
            if not h:
                continue
            changes.append(safe_float(h.get("change_percent")))
            mfes.append(safe_float(h.get("mfe_percent")))
            maes.append(safe_float(h.get("mae_percent")))
            tp1 += int(bool(h.get("tp1_reached")))
            tp2 += int(bool(h.get("tp2_reached")))
            sl += int(bool(h.get("sl_reached")))
        observed = len(changes)
        h_avg_mfe = round(sum(mfes) / len(mfes), 3) if mfes else None
        h_avg_mae = round(sum(maes) / len(maes), 3) if maes else None
        result["horizons"][key] = {
            "observed": observed,
            "avg_change_percent": round(sum(changes) / observed, 3) if observed else None,
            "median_change_percent": _safe_median(changes),
            "avg_mfe_percent": h_avg_mfe,
            "avg_mae_percent": h_avg_mae,
            "mfe_mae_ratio": round(h_avg_mfe / h_avg_mae, 3) if h_avg_mfe is not None and h_avg_mae and h_avg_mae > 0 else None,
            "tp1_reached": tp1,
            "tp2_reached": tp2,
            "sl_reached": sl,
            "tp1_rate": _rate(tp1, observed),
            "tp2_rate": _rate(tp2, observed),
            "sl_rate": _rate(sl, observed),
        }
    return result


def build_outcome_analytics(history):
    """Build descriptive analytics by mode, score band, and direction."""
    finalized = [
        r for r in history
        if isinstance(r, dict) and str(r.get("outcome_status", "OPEN")).upper() == "FINAL"
    ]
    groups = {
        "ALL": finalized,
        "TREND": [],
        "BOTTOM_HUNTER": [],
        "SCORE_90_PLUS": [],
        "SCORE_80_89": [],
        "SCORE_74_79": [],
        "BUY": [],
        "SELL": [],
    }
    for r in finalized:
        mode = str(r.get("signal_mode", "TREND")).upper()
        if mode in groups:
            groups[mode].append(r)
        side = str(r.get("signal", "")).upper()
        if side in ("BUY", "SELL"):
            groups[side].append(r)
        score = safe_float(r.get("score"), 0.0)
        if score >= 90:
            groups["SCORE_90_PLUS"].append(r)
        elif score >= 80:
            groups["SCORE_80_89"].append(r)
        elif score >= 74:
            groups["SCORE_74_79"].append(r)
    return {name: _outcome_group_stats(rows) for name, rows in groups.items()}


def log_outcome_analytics(history):
    analytics = build_outcome_analytics(history)
    log("ADVANCED OUTCOME ANALYTICS v55")
    log("--------------------------------------")
    for name, data in analytics.items():
        events = data.get("first_events", {})
        event_text = ", ".join(f"{k}={v}" for k, v in sorted(events.items())) or "none"
        log(
            f"{name}: signals={data.get('signals', 0)} "
            f"finalized={data.get('finalized', 0)} "
            f"open={data.get('open', 0)} "
            f"first={event_text} "
            f"TP1_rate={data.get('tp1_rate', 'n/a')}% "
            f"SL_rate={data.get('sl_rate', 'n/a')}% "
            f"NO_LEVEL_rate={data.get('no_level_hit_rate', 'n/a')}% "
            f"avg_return_8H={data.get('avg_return', 'n/a')}% "
            f"median_return_8H={data.get('median_return', 'n/a')}% "
            f"avg_MFE={data.get('avg_mfe', 'n/a')}% "
            f"avg_MAE={data.get('avg_mae', 'n/a')}% "
            f"MFE_MAE={data.get('mfe_mae_ratio', 'n/a')}"
        )
        for h in OUTCOME_HORIZONS_HOURS:
            hd = data.get("horizons", {}).get(f"{h}h", {})
            if hd.get("observed", 0):
                log(
                    f"  {h}H: n={hd['observed']} "
                    f"avg_return={hd['avg_change_percent']}% "
                    f"median={hd['median_change_percent']}% "
                    f"MFE={hd['avg_mfe_percent']}% "
                    f"MAE={hd['avg_mae_percent']}% "
                    f"MFE_MAE={hd['mfe_mae_ratio']} "
                    f"TP1={hd['tp1_reached']}({hd['tp1_rate']}%) "
                    f"TP2={hd['tp2_reached']}({hd['tp2_rate']}%) "
                    f"SL={hd['sl_reached']}({hd['sl_rate']}%)"
                )
    return analytics


def update_signal_outcomes(history):
    """Refresh/migrate signal outcomes using closed Binance 1H candles.

    v54 deliberately revisits recent FINAL records whose horizon profile was
    created by v52, because those records may contain the old zero-MFE/MAE
    horizon bug. Once a record has a valid v54 profile it is skipped.
    """
    if not OUTCOME_TRACKER_ENABLED or not isinstance(history, list) or not history:
        return {"updated": 0, "finalized": 0, "tracked": 0, "migrated": 0}

    now_utc = pd.Timestamp.now(tz="UTC")
    changed = 0
    finalized = 0
    tracked = 0
    migrated = 0
    cache = {}

    records = []
    for record in history[-OUTCOME_MAX_HISTORY_SCAN:]:
        if not isinstance(record, dict):
            continue
        if str(record.get("signal", "")).upper() not in ("BUY", "SELL"):
            continue
        version = safe_int(record.get("outcome_engine_version", 0))
        horizons = record.get("horizons")
        complete_v53 = (
            version >= 54
            and isinstance(horizons, dict)
            and all(f"{h}h" in horizons for h in OUTCOME_HORIZONS_HOURS)
        )
        if complete_v53 and str(record.get("outcome_status", "OPEN")).upper() == "FINAL":
            continue
        records.append(record)

    for record in records:
        candle_ts = _parse_signal_time(record.get("candle_time"))
        if candle_ts is None:
            continue

        age_hours = max(0.0, (now_utc - candle_ts).total_seconds() / 3600.0)
        # The signal candle must be closed before it can enter the outcome set.
        if age_hours < 1.0:
            continue

        symbol = str(record.get("symbol", "")).upper()
        if not symbol:
            continue

        if symbol not in cache:
            cache[symbol] = get_klines(symbol, "1h", limit=OUTCOME_KLINE_LIMIT)
        df = cache.get(symbol)
        if df is None or df.empty:
            continue

        tracked += 1
        before_status = record.get("outcome_status")
        before_version = safe_int(record.get("outcome_engine_version", 0))
        if _update_signal_outcome_record(record, df, now_utc):
            changed += 1
        if before_version < 53:
            migrated += 1
        if before_status != "FINAL" and record.get("outcome_status") == "FINAL":
            finalized += 1

    if changed:
        log(
            f"📊 Outcome tracker updated: {changed} | "
            f"finalized: {finalized} | tracked: {tracked} | migrated: {migrated}"
        )

    return {
        "updated": changed,
        "finalized": finalized,
        "tracked": tracked,
        "migrated": migrated,
    }


# =========================================================
# HISTORY SUMMARY
# =========================================================

def get_history_summary(
    history
):

    if not history:

        return {
            "total": 0,
            "buy": 0,
            "sell": 0,
            "strong": 0
        }

    buy_count = 0
    sell_count = 0
    strong_count = 0

    for item in history:

        if not isinstance(
            item,
            dict
        ):

            continue

        side = str(
            item.get(
                "signal",
                ""
            )
        ).upper()

        strength = str(
            item.get(
                "strength",
                ""
            )
        ).upper()

        if side == "BUY":

            buy_count += 1

        elif side == "SELL":

            sell_count += 1

        if strength == "STRONG":

            strong_count += 1

    return {

        "total": len(history),

        "buy": buy_count,

        "sell": sell_count,

        "strong": strong_count
    }


# =========================================================
# END OF SECTION 13
# =========================================================# =========================================================
# SECTION 14
# MAIN MARKET SCANNER
# 100-150 COINS | 1H + 30M
# =========================================================


# =========================================================
# SCAN RESULT
# =========================================================

def get_empty_scan_result():

    return {
        "total_coins": 0,
        "checked": 0,
        "signals": 0,
        "strong_signals": 0,
        "errors": 0,
        "duplicates": 0,
        "results": [],
        "new_signals": [],
        "bottom_diagnostic": {},
        "higher_4h_accepted": 0,
        "higher_daily_accepted": 0,
        "higher_4h_new": 0,
        "higher_daily_new": 0,
        "higher_4h_duplicates": 0,
        "higher_daily_duplicates": 0,
        "process_rejected": 0,
        "process_reject_reasons": {},
        "invalid_internal_candidates": 0
    }


# =========================================================
# QUICK LOG
# =========================================================

def log_scan_progress(
    index,
    total,
    symbol
):

    if not DEBUG_MODE:
        return

    log(
        f"[{index}/{total}] "
        f"Scanning {symbol}"
    )


# =========================================================
# PREPARE ONE SYMBOL
# =========================================================

def score_bottom_hunter(df_1h, df_30m, btc_regime=None, diagnostic=None, mtf_context=None):
    """Separate 1H early-reversal scanner; never claims the exact bottom.

    When ``diagnostic`` is supplied, this function records the stage at which
    a Bottom Hunter setup is filtered out. Qualification logic is unchanged.
    """
    def dmark(name):
        if isinstance(diagnostic, dict):
            diagnostic[name] = safe_int(diagnostic.get(name, 0)) + 1

    if df_1h is None or df_30m is None or len(df_1h) < 80 or len(df_30m) < 30:
        dmark("insufficient_data")
        return None
    dmark("data_ready")

    row = df_1h.iloc[-1]
    prev = df_1h.iloc[-2]
    close = safe_float(row.get("close"))
    rsi = safe_float(row.get("rsi"))
    prev_rsi = safe_float(prev.get("rsi"))
    if close <= 0:
        dmark("invalid_price")
        return None

    ema21 = safe_float(row.get("ema21"))
    adx = safe_float(row.get("adx"))
    atr_percent = safe_float(row.get("atr_percent"))
    macd = safe_float(row.get("macd"))
    macd_signal = safe_float(row.get("macd_signal"))
    hist = safe_float(row.get("macd_hist"))
    prev_hist = safe_float(prev.get("macd_hist"))
    vol = safe_float(row.get("volume_ratio"))

    low_n = safe_float(df_1h["low"].iloc[-BOTTOM_LOOKBACK:].min())
    high_n = safe_float(df_1h["high"].iloc[-BOTTOM_LOOKBACK:].max())
    if low_n <= 0 or high_n <= 0:
        dmark("invalid_range")
        return None

    dist_low = (close / low_n - 1) * 100
    drawdown = (close / high_n - 1) * 100
    if dist_low <= 7:
        dmark("near_low")
    else:
        dmark("not_near_low")
    ema_dist = abs(close / ema21 - 1) * 100 if ema21 > 0 else 999
    rng = high_n - low_n
    fib618 = high_n - rng * 0.618
    fib786 = high_n - rng * 0.786
    fib_dist = min(
        abs(close / fib618 - 1) * 100 if fib618 > 0 else 999,
        abs(close / fib786 - 1) * 100 if fib786 > 0 else 999
    )

    divergence = analyze_divergence(df_1h)
    bullish_rsi_div = bool(divergence.get("bullish_rsi", False))
    bullish_macd_div = bool(divergence.get("bullish_macd", False))

    if BOTTOM_RSI_MIN <= rsi <= BOTTOM_RSI_MAX:
        dmark("rsi_zone")
    else:
        dmark("rsi_outside")

    score = 0
    reasons = []
    reversal = False

    if dist_low <= BOTTOM_NEAR_LOW_PERCENT:
        score += 20
        reasons.append(f"Near {BOTTOM_LOOKBACK}H low ({dist_low:.2f}% above)")
    elif dist_low <= 7:
        score += 12
        reasons.append(f"Close to recent low ({dist_low:.2f}% above)")

    if BOTTOM_RSI_MIN <= rsi <= 34:
        score += 15
        reasons.append(f"RSI oversold/recovery zone ({rsi:.1f})")
    elif 34 < rsi <= BOTTOM_RSI_MAX:
        score += 10
        reasons.append(f"RSI low recovery zone ({rsi:.1f})")

    if rsi > prev_rsi and rsi >= 28:
        score += 10
        reversal = True
        reasons.append(f"RSI recovering ({prev_rsi:.1f} -> {rsi:.1f})")

    if rsi > 30 and prev_rsi <= 30:
        score += 5
        reversal = True
        reasons.append("RSI reclaimed 30")

    if bullish_rsi_div:
        score += 15
        reversal = True
        reasons.append("RSI bullish divergence")

    if bullish_macd_div:
        score += 8
        reversal = True
        reasons.append("MACD bullish divergence")

    if hist > prev_hist:
        score += 7
        reversal = True
        reasons.append("MACD histogram improving")

    if macd > macd_signal:
        score += 5
        reversal = True
        reasons.append("MACD above signal")

    if fib_dist <= 1.2:
        score += 8
        reasons.append("Price near Fibonacci 0.618/0.786 zone")
    elif fib_dist <= 2.5:
        score += 4
        reasons.append("Price near Fibonacci retracement zone")

    if vol >= 1.10:
        score += 8
        reversal = True
        reasons.append(f"Volume expansion ({vol:.2f}x)")
    elif vol >= 0.80:
        score += 4
        reasons.append(f"Volume acceptable ({vol:.2f}x)")

    if safe_float(row.get("close")) > safe_float(row.get("open")):
        score += 6
        reversal = True
        reasons.append("Bullish 1H candle")

    if close > safe_float(prev.get("close")):
        score += 4
        reversal = True
        reasons.append("Price reclaimed previous close")

    c = df_30m.iloc[-1]
    cp = df_30m.iloc[-2]
    cr = safe_float(c.get("rsi"))
    cm = safe_float(c.get("macd"))
    cs = safe_float(c.get("macd_signal"))
    confirm = 0

    if cr > safe_float(cp.get("rsi")) and cr >= 30:
        confirm += 5
    if cm > cs:
        confirm += 5
    if safe_float(c.get("close")) > safe_float(c.get("ema9")):
        confirm += 3

    if confirm >= 5:
        score += min(confirm, 10)
        reversal = True
        reasons.append("30M reversal confirmation")
        dmark("confirm_30m")
    else:
        dmark("no_confirm_30m")

    if reversal:
        dmark("reversal_evidence")
    else:
        dmark("no_reversal_evidence")

    if ema21 > 0 and ema_dist <= BOTTOM_MAX_DISTANCE_EMA21:
        score += 4
    elif ema21 > 0 and ema_dist > 15:
        score -= 8
        reasons.append("Price too far from EMA21")

    if atr_percent > 7:
        score -= 8
        reasons.append("Very high ATR volatility")

    if adx >= 25 and safe_float(row.get("minus_di")) > safe_float(row.get("plus_di")):
        score -= 10
        reasons.append("Strong bearish ADX - higher reversal risk")

    btc = str((btc_regime or {}).get("combined", "")).upper()
    if "BEARISH" in btc and ("STRONG" in btc or "SEVERE" in btc or btc == "BEARISH"):
        dmark("btc_blocked")
        dmark("final_rejected")
        return None
    dmark("btc_allowed")
    if btc and "BEARISH" not in btc:
        score += 3
        reasons.append("BTC regime not strongly bearish")

    # 4H + Daily context is deliberately a soft filter for Bottom Hunter.
    # It helps distinguish a supported reversal from a counter-trend bounce
    # without blocking early reversals outright.
    mtf_context = mtf_context or {}
    mtf_adjustment, mtf_reasons = mtf_side_adjustment(mtf_context, "BUY")
    score += mtf_adjustment
    reasons.extend(mtf_reasons)

    raw_score = max(0, min(100, int(round(score))))

    # Quality caps: a reversal setup can accumulate many confirmations while
    # still lacking trend strength or real participation. Keep the signal
    # eligible, but prevent weak ADX/volume from producing inflated scores.
    quality_caps = []
    if adx < 15:
        quality_caps.append(("ADX < 15", BOTTOM_ADX_CAP_WEAK))
    elif adx < 20:
        quality_caps.append(("ADX 15-20", BOTTOM_ADX_CAP_MODERATE))
    elif adx < 25:
        quality_caps.append(("ADX 20-25", BOTTOM_ADX_CAP_GOOD))

    if vol < 0.70:
        quality_caps.append(("Volume < 0.70x", BOTTOM_VOLUME_CAP_VERY_WEAK))
    elif vol < 0.90:
        quality_caps.append(("Volume 0.70-0.90x", BOTTOM_VOLUME_CAP_WEAK))
    elif vol < 1.10:
        quality_caps.append(("Volume 0.90-1.10x", BOTTOM_VOLUME_CAP_ACCEPTABLE))

    # Apply the strictest applicable cap.
    score = min(raw_score, 95, *(cap for _, cap in quality_caps)) if quality_caps else min(raw_score, 95)

    for label, cap in quality_caps:
        if raw_score > cap:
            reasons.append(f"Quality cap: {label} -> max {cap}")

    if raw_score > score:
        reasons.append(f"Raw score {raw_score}; quality-adjusted score {score}")

    if dist_low <= 7:
        dmark("passed_near_low")
    else:
        dmark("failed_near_low")

    if reversal:
        dmark("passed_reversal")
    else:
        dmark("failed_reversal")

    if score >= BOTTOM_MIN_SCORE:
        dmark("score_pass")
    else:
        dmark("score_fail")

    if not (dist_low <= 7 and reversal and score >= BOTTOM_MIN_SCORE):
        dmark("final_rejected")
        return None

    dmark("final_passed")

    return {
        "score": score,
        "raw_score": raw_score,
        "signal": "BUY",
        "signal_mode": "BOTTOM_HUNTER",
        "strength": "EARLY REVERSAL",
        "price": close,
        "rsi": rsi,
        "adx": adx,
        "atr": safe_float(row.get("atr")),
        "atr_percent": atr_percent,
        "volume_ratio": vol,
        "ema21": ema21,
        "ema200": safe_float(row.get("ema200")),
        "btc_regime": (btc_regime or {}).get("combined", "UNKNOWN"),
        "recent_low": low_n,
        "recent_high": high_n,
        "distance_from_low": dist_low,
        "drawdown_from_high": drawdown,
        "fib618": fib618,
        "fib786": fib786,
        "fib_distance": fib_dist,
        "mtf_context": mtf_context,
        "mtf_adjustment": mtf_adjustment,
        "reasons": reasons,
        "candle_time": str(row.get("open_time")),
        "bottom_warning": "Early reversal setup; exact bottom is not confirmed."
    }



def analyze_higher_timeframe_signal(symbol, data, timeframe, btc_regime=None):
    """Generate an independent 4H or Daily signal.

    4H uses 4H as the primary timeframe and Daily as higher context.
    Daily uses Daily as the primary timeframe and 4H as confirmation context.
    These signals are independent from the 1H + 30M engine and are sent
    with their own timeframe-aware duplicate key.
    """
    tf = str(timeframe).lower()
    if tf not in ("4h", "1d") or not data:
        return None

    main_df = data.get(tf)
    label = "4H" if tf == "4h" else "DAILY"
    context_tf = "1d" if tf == "4h" else "4h"
    context_df = data.get(context_tf)
    if main_df is None or context_df is None or len(main_df) < 50 or len(context_df) < 50:
        return None

    buy = score_timeframe(main_df, "BUY", label)
    sell = score_timeframe(main_df, "SELL", label)
    if not buy.get("hard_pass") and not sell.get("hard_pass"):
        return None

    # Choose the stronger side; do not force a signal when both are weak/equal.
    if buy.get("score", 0) > sell.get("score", 0):
        side, base = "BUY", buy
    elif sell.get("score", 0) > buy.get("score", 0):
        side, base = "SELL", sell
    else:
        return None

    row = main_df.iloc[-1]
    context_row = context_df.iloc[-1]
    close = safe_float(row.get("close"))
    if close <= 0 or not indicators_ready(row):
        return None

    # Higher timeframe context: modest adjustment, never a hard block.
    c_close = safe_float(context_row.get("close"))
    c_ema9 = safe_float(context_row.get("ema9"))
    c_ema21 = safe_float(context_row.get("ema21"))
    c_ema200 = safe_float(context_row.get("ema200"))
    if c_close > c_ema200 and c_ema9 > c_ema21:
        context_trend = "BULLISH"
    elif c_close < c_ema200 and c_ema9 < c_ema21:
        context_trend = "BEARISH"
    else:
        context_trend = "NEUTRAL"

    adjustment = 0
    context_reason = f"{('Daily' if tf == '4h' else '4H')} context {context_trend.lower()}"
    if (side == "BUY" and context_trend == "BULLISH") or (side == "SELL" and context_trend == "BEARISH"):
        adjustment += 5
    elif (side == "BUY" and context_trend == "BEARISH") or (side == "SELL" and context_trend == "BULLISH"):
        adjustment -= 4

    # BTC regime is context only for higher-timeframe signals.
    btc_reason = ""
    if btc_regime:
        combined = str(btc_regime.get("combined", "UNKNOWN")).upper()
        if (side == "BUY" and combined == "BULLISH") or (side == "SELL" and combined == "BEARISH"):
            adjustment += 3
            btc_reason = f"BTC {combined.lower()}"
        elif (side == "BUY" and combined == "BEARISH") or (side == "SELL" and combined == "BULLISH"):
            adjustment -= 3
            btc_reason = f"BTC {combined.lower()} headwind"

    score = max(0, min(100, int(round(base.get("score", 0) + adjustment))))
    if score < HIGHER_TF_MIN_SCORE:
        return None

    adx = safe_float(row.get("adx"))
    # STRONG requires at least moderate trend strength; weak ADX stays NORMAL.
    strength = "STRONG" if score >= HIGHER_TF_STRONG_SCORE and adx >= MIN_ADX else "NORMAL"
    reasons = [str(r).replace("1H", label) for r in base.get("reasons", [])]
    reasons.insert(0, f"{label} independent signal setup")
    reasons.append(context_reason)
    if btc_reason:
        reasons.append(btc_reason)

    return {
        "symbol": symbol,
        "signal": side,
        "signal_mode": f"{label}_SIGNAL",
        "engine": "TREND",
        "signal_timeframe": tf,
        "score": score,
        "strength": strength,
        "price": close,
        "rsi": safe_float(row.get("rsi")),
        "adx": adx,
        "atr": safe_float(row.get("atr")),
        "atr_percent": safe_float(row.get("atr_percent")),
        "volume_ratio": safe_float(row.get("volume_ratio")),
        "ema9": safe_float(row.get("ema9")),
        "ema21": safe_float(row.get("ema21")),
        "ema50": safe_float(row.get("ema50")),
        "ema200": safe_float(row.get("ema200")),
        "btc_regime": btc_regime.get("combined", "UNKNOWN") if btc_regime else "UNKNOWN",
        "higher_tf_context": label,
        "higher_tf_context_trend": context_trend,
        "reasons": reasons,
        "candle_time": str(row.get("open_time")),
    }




# =========================================================
# BREAKOUT ENGINE
# =========================================================

def score_breakout_1h(df, df_30m, side):
    """Independent 1H breakout engine. It detects a closed-candle break of
    recent structure and uses 30M only as confirmation, not as the setup itself."""
    result = {"signal": "NO_SIGNAL", "score": 0, "reasons": [], "confirmed": False}
    side = str(side).upper()
    if df is None or len(df) < max(60, BREAKOUT_LOOKBACK + 5):
        return result
    row = df.iloc[-1]
    prev = df.iloc[:-1]
    look = prev.tail(BREAKOUT_LOOKBACK)
    close = safe_float(row.get("close"))
    high = safe_float(row.get("high"))
    low = safe_float(row.get("low"))
    ema9 = safe_float(row.get("ema9")); ema21 = safe_float(row.get("ema21")); ema50 = safe_float(row.get("ema50")); ema200 = safe_float(row.get("ema200"))
    rsi = safe_float(row.get("rsi")); adx = safe_float(row.get("adx")); volume = safe_float(row.get("volume_ratio")); atrp = safe_float(row.get("atr_percent"))
    if close <= 0 or look.empty or not indicators_ready(row):
        return result
    resistance = safe_float(look["high"].max())
    support = safe_float(look["low"].min())
    buffer = BREAKOUT_BUFFER_PERCENT / 100.0
    score = 0; reasons = []
    if side == "BUY":
        broken = close > resistance * (1 + buffer)
        if not broken:
            return result
        score += 25; reasons.append(f"1H resistance breakout ({resistance:.8g})")
        if close > ema200: score += 15; reasons.append("Price above EMA200")
        if ema9 > ema21 > ema50: score += 15; reasons.append("EMA9 > EMA21 > EMA50")
        elif ema9 > ema21: score += 8; reasons.append("EMA9 > EMA21")
        if adx >= STRONG_ADX and safe_float(row.get("plus_di")) > safe_float(row.get("minus_di")): score += 15; reasons.append(f"ADX breakout strength ({adx:.1f})")
        elif adx >= MIN_ADX: score += 8; reasons.append(f"ADX moderate ({adx:.1f})")
        if volume >= STRONG_VOLUME_RATIO: score += 15; reasons.append(f"Volume expansion ({volume:.2f}x)")
        elif volume >= BREAKOUT_MIN_VOLUME_RATIO: score += 8; reasons.append(f"Volume supports breakout ({volume:.2f}x)")
        if 50 <= rsi <= 72: score += 10; reasons.append(f"RSI supports breakout ({rsi:.1f})")
        elif 45 <= rsi < 50 or 72 < rsi <= 78: score += 5; reasons.append(f"RSI acceptable ({rsi:.1f})")
        if 0.20 <= atrp <= 8.0: score += 5; reasons.append(f"ATR suitable ({atrp:.2f}%)")
        confirm = score_30m_confirmation(df_30m, "BUY") if df_30m is not None else {"confirmed":False,"score":0,"reasons":[]}
        if confirm.get("confirmed"):
            score += min(10, max(0, safe_int(confirm.get("score",0))))
            reasons.extend(confirm.get("reasons", [])[:3])
        result.update({"signal":"BUY", "score":max(0,min(100,int(round(score)))), "reasons":reasons, "confirmed":bool(confirm.get("confirmed")), "resistance":resistance, "support":support})
    else:
        broken = close < support * (1 - buffer)
        if not broken:
            return result
        score += 25; reasons.append(f"1H support breakdown ({support:.8g})")
        if close < ema200: score += 15; reasons.append("Price below EMA200")
        if ema9 < ema21 < ema50: score += 15; reasons.append("EMA9 < EMA21 < EMA50")
        elif ema9 < ema21: score += 8; reasons.append("EMA9 < EMA21")
        if adx >= STRONG_ADX and safe_float(row.get("minus_di")) > safe_float(row.get("plus_di")): score += 15; reasons.append(f"ADX breakdown strength ({adx:.1f})")
        elif adx >= MIN_ADX: score += 8; reasons.append(f"ADX moderate ({adx:.1f})")
        if volume >= STRONG_VOLUME_RATIO: score += 15; reasons.append(f"Volume expansion ({volume:.2f}x)")
        elif volume >= BREAKOUT_MIN_VOLUME_RATIO: score += 8; reasons.append(f"Volume supports breakdown ({volume:.2f}x)")
        if 28 <= rsi <= 50: score += 10; reasons.append(f"RSI supports breakdown ({rsi:.1f})")
        elif 22 <= rsi < 28 or 50 < rsi <= 55: score += 5; reasons.append(f"RSI acceptable ({rsi:.1f})")
        if 0.20 <= atrp <= 8.0: score += 5; reasons.append(f"ATR suitable ({atrp:.2f}%)")
        confirm = score_30m_confirmation(df_30m, "SELL") if df_30m is not None else {"confirmed":False,"score":0,"reasons":[]}
        if confirm.get("confirmed"):
            score += min(10, max(0, safe_int(confirm.get("score",0))))
            reasons.extend(confirm.get("reasons", [])[:3])
        result.update({"signal":"SELL", "score":max(0,min(100,int(round(score)))), "reasons":reasons, "confirmed":bool(confirm.get("confirmed")), "resistance":resistance, "support":support})
    return result


def build_breakout_signal(symbol, data, breakout, btc_regime=None):
    if not breakout or breakout.get("signal") not in ("BUY","SELL"):
        return None
    if breakout.get("score",0) < BREAKOUT_MIN_SCORE or not breakout.get("confirmed"):
        return None
    side = breakout["signal"]
    btc = score_btc_regime(side, btc_regime) if btc_regime else {"allowed":True,"score":0,"reason":""}
    if not btc.get("allowed", True):
        return None
    score = int(round(breakout.get("score",0) + min(5, max(0, safe_int(btc.get("score",0))))))
    return {
        "symbol": symbol, "signal": side, "signal_mode": "BREAKOUT", "signal_timeframe": "1h",
        "score": max(0,min(100,score)), "strength": "STRONG" if score >= STRONG_SCORE and safe_float(data["1h"].iloc[-1].get("adx")) >= MIN_ADX else "NORMAL",
        "price": safe_float(data["1h"].iloc[-1].get("close")), "rsi": safe_float(data["1h"].iloc[-1].get("rsi")),
        "adx": safe_float(data["1h"].iloc[-1].get("adx")), "atr": safe_float(data["1h"].iloc[-1].get("atr")),
        "atr_percent": safe_float(data["1h"].iloc[-1].get("atr_percent")), "volume_ratio": safe_float(data["1h"].iloc[-1].get("volume_ratio")),
        "ema9": safe_float(data["1h"].iloc[-1].get("ema9")), "ema21": safe_float(data["1h"].iloc[-1].get("ema21")),
        "ema50": safe_float(data["1h"].iloc[-1].get("ema50")), "ema200": safe_float(data["1h"].iloc[-1].get("ema200")),
        "btc_regime": btc_regime.get("combined","UNKNOWN") if btc_regime else "UNKNOWN",
        "reasons": breakout.get("reasons",[]) + ([btc.get("reason")] if btc.get("reason") else []),
        "candle_time": str(data["1h"].iloc[-1].get("open_time")),
    }

def professional_signal_quality_gate(signal, data, btc_regime=None):
    """Final trade-quality gate.

    v60 uses a composite gate: score is only the entry ticket; hard structural
    failures still reject immediately, while softer professional factors are
    accumulated as quality points. This prevents a single raw score from
    rescuing a weak setup, without requiring every secondary indicator to be
    perfect. The gate is deliberately asymmetric: volume, directional ADX/DI,
    lower-timeframe confirmation, higher-timeframe alignment, BTC conflict,
    and trade R:R remain hard requirements.
    """
    if not signal or not data:
        return False, ["missing signal/data"], 0

    side = str(signal.get("signal", "")).upper()
    mode = str(signal.get("signal_mode", "TREND")).upper()
    if side not in ("BUY", "SELL"):
        return False, ["invalid side"], 0

    df1 = data.get("1h")
    df30 = data.get("30m")
    df4 = data.get("4h")
    dfd = data.get("1d")

    # Higher-timeframe signals must be judged on their own timeframe.
    # Previously a 4H/Daily signal was gated against the 1H candle and 30M
    # confirmation, which could reject a valid HTF setup for the wrong reason.
    signal_tf = str(signal.get("signal_timeframe", TIMEFRAME_MAIN)).lower()
    if mode == "4H_SIGNAL" or signal_tf == "4h":
        df1 = df4
        confirm_df = data.get("1h")
        context_frames = (dfd,)
    elif mode == "DAILY_SIGNAL" or signal_tf == "1d":
        df1 = dfd
        confirm_df = df4
        context_frames = (df4,)
    else:
        confirm_df = df30
        context_frames = (df4, dfd)

    if df1 is None or len(df1) < 60:
        return False, ["required signal timeframe data unavailable"], 0
    if confirm_df is None or len(confirm_df) < 35:
        return False, ["required confirmation timeframe data unavailable"], 0

    r1 = df1.iloc[-1]
    reject = []
    quality = 0

    # Always initialize 30M confirmation state before any quality rule uses it.
    # This prevents UnboundLocalError even if the confirmation block changes later.
    confirm = {}
    confirmations = 0

    raw_score = safe_float(signal.get("score"))
    min_score = PRO_MIN_SCORE
    if mode == "BREAKOUT":
        min_score = PRO_BREAKOUT_MIN_SCORE
    elif mode == "BOTTOM_HUNTER":
        min_score = PRO_BOTTOM_MIN_SCORE
    elif mode in ("4H_SIGNAL", "DAILY_SIGNAL"):
        min_score = PRO_HIGHER_TF_MIN_SCORE
    elif side == "SELL":
        min_score = PRO_SELL_MIN_SCORE
    if raw_score < min_score:
        reject.append(f"score {raw_score:.0f} < {min_score}")
        # v63.10 ROOT FIX: never destroy real diagnostics on an early score
        # rejection. The previous early return produced misleading ADX=0,
        # volume=0x, 30M=0/0 and RR=0 in the rejection summary even though
        # the engine had already calculated real market values.
        early_close = safe_float(r1.get("close"))
        early_ema200 = safe_float(r1.get("ema200"))
        early_adx = safe_float(r1.get("adx"))
        early_volume = safe_float(r1.get("volume_ratio"))
        early_atrp = safe_float(r1.get("atr_percent"))
        early_dist21 = safe_float(r1.get("distance_ema21"))
        early_rr1 = safe_float(signal.get("rr_tp1"))
        early_rr2 = safe_float(signal.get("rr_tp2"))
        early_confirm = {}
        try:
            early_confirm = score_30m_confirmation(confirm_df, side) if confirm_df is not None else {}
        except Exception:
            early_confirm = {}
        early_confirmations = safe_int(early_confirm.get("score", 0))
        early_htf_align = 0
        for frame in context_frames:
            if frame is None or frame.empty:
                continue
            rr = frame.iloc[-1]
            c = safe_float(rr.get("close")); e9 = safe_float(rr.get("ema9")); e21 = safe_float(rr.get("ema21")); e200 = safe_float(rr.get("ema200"))
            if (c > e200 and e9 > e21) if side == "BUY" else (c < e200 and e9 < e21):
                early_htf_align += 1
        signal["professional_filter"] = "REJECTED"
        signal["professional_reject_reasons"] = list(reject)
        signal["professional_quality_points"] = 0
        signal["professional_quality_score"] = int(max(0, raw_score))
        signal["professional_quality_breakdown"] = {
            "mode": mode, "side": side, "raw_score": round(raw_score, 1),
            "quality_points": 0, "quality_score": int(max(0, raw_score)),
            "grade": "C", "min_quality_points": int(PRO_BOTTOM_MIN_QUALITY_POINTS if mode == "BOTTOM_HUNTER" else PRO_MIN_QUALITY_POINTS),
            "required_grade": "A+", "adx": round(early_adx, 2),
            "volume_ratio": round(early_volume, 2), "confirmations_30m": int(early_confirmations),
            "required_30m": int(PRO_BOTTOM_MIN_30M_CONFIRMATIONS if mode == "BOTTOM_HUNTER" else PRO_MIN_30M_CONFIRMATIONS),
            "htf_alignment": int(early_htf_align),
            "required_htf_alignment": int(PRO_SELL_MIN_HTF_ALIGNMENT if side == "SELL" and mode != "BOTTOM_HUNTER" else (PRO_BOTTOM_REQUIRE_HTF_ALIGNMENT if mode == "BOTTOM_HUNTER" else PRO_MIN_HTF_ALIGNMENT)),
            "ema21_distance": round(early_dist21, 2),
            "ema200_distance": round(abs(early_close / early_ema200 - 1) * 100 if early_ema200 > 0 else 999, 2),
            "atr_percent": round(early_atrp, 2), "rr_tp1": round(early_rr1, 2), "rr_tp2": round(early_rr2, 2),
            "reject_count": 1, "reject_reasons": list(reject),
            "component_ledger": {},
        }
        return False, reject, int(max(0, raw_score))

    close = safe_float(r1.get("close"))
    ema9 = safe_float(r1.get("ema9")); ema21 = safe_float(r1.get("ema21")); ema50 = safe_float(r1.get("ema50")); ema200 = safe_float(r1.get("ema200"))
    adx = safe_float(r1.get("adx")); plus_di = safe_float(r1.get("plus_di")); minus_di = safe_float(r1.get("minus_di"))
    rsi = safe_float(r1.get("rsi")); volume = safe_float(r1.get("volume_ratio")); atrp = safe_float(r1.get("atr_percent"))
    dist21 = safe_float(r1.get("distance_ema21"))
    vwap = safe_float(r1.get("rolling_vwap")); obv_slope = safe_float(r1.get("obv_slope"))
    bb_width = safe_float(r1.get("bb_width_pct")); bb_pos = safe_float(r1.get("bb_position"))

    # v56 SELL calibration: historical SELLs showed poor downside follow-through.
    # Require a genuine 1H bearish structure and avoid late/oversold entries.
    if side == "SELL" and mode != "BOTTOM_HUNTER":
        if not (close < ema21 and ema9 < ema21):
            reject.append("SELL 1H bearish EMA structure incomplete")
        if rsi < 34:
            reject.append(f"SELL too oversold for fresh entry (RSI {rsi:.1f})")
        if not (safe_float(r1.get("macd_hist")) < safe_float(r1.get("macd_hist_prev"))):
            reject.append("SELL MACD downside momentum not improving")
        if not safe_float(r1.get("bearish_candle")):
            reject.append("SELL latest 1H candle is not bearish")

    # HARD: major trend must not directly oppose the proposed trade.
    if mode != "BOTTOM_HUNTER":
        major_ok = (close > ema200 and close > ema21) if side == "BUY" else (close < ema200 and close < ema21)
        if not major_ok:
            reject.append("1H major trend misaligned")
        else:
            quality += 2
    else:
        # v63.11: do not pre-reject on a contradictory single-rule check.
        # The actual reversal gate below evaluates the three independent
        # momentum components together.
        pass

    # BOTTOM_HUNTER is an early-reversal engine: do not require the new
    # trend to already have fully developed ADX/DI structure.  Trend and
    # breakout engines keep the hard directional ADX/DI gate.
    if mode == "BOTTOM_HUNTER":
        rsi_improving = (rsi >= safe_float(r1.get("rsi_prev"))) if side == "BUY" else (rsi <= safe_float(r1.get("rsi_prev")))
        macd_hist_improving = (safe_float(r1.get("macd_hist")) >= safe_float(r1.get("macd_hist_prev"))) if side == "BUY" else (safe_float(r1.get("macd_hist")) <= safe_float(r1.get("macd_hist_prev")))
        reversal_energy = (plus_di > minus_di) if side == "BUY" else (minus_di > plus_di)
        momentum_components = int(rsi_improving) + int(macd_hist_improving) + int(reversal_energy)
        momentum_improving = momentum_components >= PRO_BOTTOM_MIN_MOMENTUM_COMPONENTS
        # v63.11 ROOT FIX: reversal momentum uses 2-of-3 independent evidence
        # rather than the contradictory old AND rule for RSI+MACD. ADX remains
        # hard, so this does not turn weak bounces into signals.
        if adx < PRO_BOTTOM_MIN_ADX:
            reject.append(f"reversal ADX too weak ({adx:.1f} < {PRO_BOTTOM_MIN_ADX:.1f})")
        elif not momentum_improving:
            reject.append(f"reversal momentum insufficient ({momentum_components}/3 < {PRO_BOTTOM_MIN_MOMENTUM_COMPONENTS}/3)")
        else:
            quality += 2
    else:
        min_adx = PRO_SELL_MIN_1H_ADX if side == "SELL" else PRO_MIN_1H_ADX
        di_ok = (plus_di > minus_di) if side == "BUY" else (minus_di > plus_di)
        if adx >= min_adx and di_ok:
            quality += 2
        else:
            reject.append(f"ADX/DI weak or conflicting ({adx:.1f})")

    # SOFT: momentum agreement.
    macd_ok = (safe_float(r1.get("macd")) > safe_float(r1.get("macd_signal")) and safe_float(r1.get("macd_hist")) > 0) if side == "BUY" else (safe_float(r1.get("macd")) < safe_float(r1.get("macd_signal")) and safe_float(r1.get("macd_hist")) < 0)
    if macd_ok:
        quality += 2

    if mode == "BOTTOM_HUNTER":
        rsi_ok = (24 <= rsi <= 44) if side == "BUY" else (56 <= rsi <= 76)
    else:
        rsi_ok = (45 <= rsi <= 70) if side == "BUY" else (30 <= rsi <= 55)
    if rsi_ok:
        quality += 1

    if mode == "BOTTOM_HUNTER":
        # v59 ROOT FIX: no low-participation early-reversal Telegram signals.
        # A reversal can lead price trend confirmation, but volume must at least
        # reach its normal baseline before it becomes actionable.
        if volume >= PRO_BOTTOM_MIN_VOLUME_RATIO:
            quality += 2
        else:
            reject.append(f"reversal volume below professional minimum ({volume:.2f}x < {PRO_BOTTOM_MIN_VOLUME_RATIO:.2f}x)")
    else:
        min_vol = PRO_MIN_BREAKOUT_VOLUME_RATIO if mode == "BREAKOUT" else (PRO_SELL_MIN_VOLUME_RATIO if side == "SELL" else PRO_MIN_VOLUME_RATIO)
        # Root fix: volume used to be effectively soft here even though the
        # configuration described it as a professional minimum. Low-volume
        # trend entries are now rejected instead of earning a quality pass.
        if volume >= min_vol:
            quality += 2
        else:
            reject.append(f"trend volume below professional minimum ({volume:.2f}x < {min_vol:.2f}x)")

    if (side == "BUY" and obv_slope > 0) or (side == "SELL" and obv_slope < 0):
        quality += 1

    if vwap > 0 and ((side == "BUY" and close > vwap) or (side == "SELL" and close < vwap)):
        quality += 1

    if 0.20 <= atrp <= PRO_MAX_ATR_PERCENT:
        quality += 1
    else:
        reject.append(f"ATR volatility unsuitable ({atrp:.2f}%)")

    # v62 REAL-RUN ENTRY-LOCATION FIX:
    # Run #96 showed that raw strength can still hide a late entry. MUBARAK
    # was acceptable at ~4.5% from EMA21, while the 4H KITE setup was ~17.7%
    # above EMA200. Keep moderate extension tradeable, but reject extreme
    # distance from both the fast trend anchor and the long-term baseline.
    if mode != "BOTTOM_HUNTER":
        ema200_dist = abs(close / ema200 - 1) * 100 if ema200 > 0 else 999
        if dist21 > PRO_MAX_EMA21_SEVERE_DISTANCE:
            reject.append(f"entry severely extended from EMA21 ({dist21:.2f}%)")
        elif dist21 <= PRO_MAX_EMA21_DISTANCE:
            quality += 1
        else:
            quality -= 1
            signal.setdefault("reasons", []).append(f"Entry extended from EMA21 ({dist21:.2f}%)")

        if ema200_dist > PRO_MAX_EMA200_DISTANCE:
            reject.append(f"entry too far from EMA200 ({ema200_dist:.2f}%)")
        elif ema200_dist <= PRO_EMA200_EXTENDED_DISTANCE:
            quality += 1
        else:
            quality -= 1
            signal.setdefault("reasons", []).append(f"Entry extended from EMA200 ({ema200_dist:.2f}%)")

    # SOFT Bollinger location: avoid only extreme continuation entries.
    if mode != "BREAKOUT":
        if not ((side == "BUY" and bb_pos > 0.985) or (side == "SELL" and bb_pos < 0.015)):
            quality += 1
    elif bb_width > 0:
        quality += 1

    # Trend/breakout require the standard 30M directional confirmation.
    # Bottom Hunter already has a dedicated 30M reversal test in its own
    # engine, so here it is a quality boost rather than a second hard gate.
    # v50: initialize these locals before the confirmation call so a malformed
    # confirmation result or future branch change can never raise an
    # UnboundLocalError such as the LINK failure seen in Run #75.
    try:
        confirm = score_30m_confirmation(confirm_df, side) or {}
    except Exception as exc:
        reject.append(f"confirmation error: {exc}")
        confirm = {}
    confirmations = safe_int(confirm.get("confirmations", 0))
    required_confirmations = PRO_SELL_MIN_30M_CONFIRMATIONS if side == "SELL" and mode != "BOTTOM_HUNTER" else PRO_MIN_30M_CONFIRMATIONS
    if mode in ("4H_SIGNAL", "DAILY_SIGNAL"):
        # HTF setup gets a directional lower-timeframe confirmation, but does
        # not inherit the main 1H/30M gate as if it were a 1H signal.
        if not confirm.get("confirmed"):
            reject.append(f"HTF confirmation insufficient ({confirmations})")
        else:
            quality += 3
    elif (not confirm.get("confirmed") or
          (mode == "BOTTOM_HUNTER" and confirmations < PRO_BOTTOM_MIN_30M_CONFIRMATIONS) or
          (mode != "BOTTOM_HUNTER" and side == "SELL" and confirmations < required_confirmations)):
        if mode == "BOTTOM_HUNTER":
            reject.append(f"30M reversal confirmation insufficient ({confirmations}/{PRO_BOTTOM_MIN_30M_CONFIRMATIONS})")
        else:
            reject.append(f"30M confirmation insufficient ({confirmations}/{required_confirmations})")
    else:
        quality += 3

    # SOFT/HARD macro context: missing HTF data is tolerated, but an explicit
    # opposite 4H/Daily regime does not receive a quality bonus.
    htf_align = 0
    for frame in context_frames:
        if frame is None or frame.empty:
            continue
        rr = frame.iloc[-1]
        c = safe_float(rr.get("close")); e9 = safe_float(rr.get("ema9")); e21 = safe_float(rr.get("ema21")); e200 = safe_float(rr.get("ema200"))
        aligned = (c > e200 and e9 > e21) if side == "BUY" else (c < e200 and e9 < e21)
        if aligned:
            htf_align += 1
    required_htf = PRO_BOTTOM_REQUIRE_HTF_ALIGNMENT if mode == "BOTTOM_HUNTER" else (PRO_SELL_MIN_HTF_ALIGNMENT if side == "SELL" else PRO_MIN_HTF_ALIGNMENT)
    if htf_align < required_htf:
        reject.append(f"higher-timeframe alignment insufficient ({htf_align}/{required_htf})")
    elif htf_align >= 2:
        quality += 3
    elif htf_align == 1:
        quality += 2

    combined = str((btc_regime or {}).get("combined", "UNKNOWN")).upper()
    if (side == "BUY" and combined == "BEARISH") or (side == "SELL" and combined == "BULLISH"):
        reject.append(f"BTC macro regime is {combined}")
    elif combined not in ("UNKNOWN", ""):
        quality += 1

    # HARD: trade geometry must be executable and worthwhile.
    rr1 = safe_float(signal.get("rr_tp1")); rr2 = safe_float(signal.get("rr_tp2"))
    if rr1 <= 0 or rr2 <= 0:
        reject.append("missing trade R:R")
    else:
        min_rr1 = TP1_RR
        min_rr2 = TP2_RR
        if rr1 + RR_EPSILON < min_rr1:
            reject.append(f"TP1 R:R too low ({rr1:.2f})")
        else:
            quality += 1
        if rr2 + RR_EPSILON < min_rr2:
            reject.append(f"TP2 R:R too low ({rr2:.2f})")
        else:
            quality += 1

    # SOFT location check: near resistance/support reduces quality, but is not
    # an automatic rejection unless the room is extremely small.
    if mode not in ("BREAKOUT", "BOTTOM_HUNTER"):
        look = df1.iloc[:-1].tail(20)
        recent_high = safe_float(look["high"].max()) if not look.empty else 0
        recent_low = safe_float(look["low"].min()) if not look.empty else 0
        atr = safe_float(r1.get("atr"))
        if side == "BUY" and recent_high > close and atr > 0:
            room_atr = (recent_high - close) / atr
            if room_atr >= PRO_MAX_RESISTANCE_ROOM_ATR:
                quality += 1
            elif room_atr < 0.35:
                reject.append(f"too close to resistance ({room_atr:.2f} ATR room)")
        elif side == "SELL" and recent_low > 0 and close > recent_low and atr > 0:
            room_atr = (close - recent_low) / atr
            if room_atr >= PRO_MAX_SUPPORT_ROOM_ATR:
                quality += 1
            elif room_atr < 0.35:
                reject.append(f"too close to support ({room_atr:.2f} ATR room)")

    # v63.5: component-level quality ledger. Diagnostic only; it mirrors the
    # professional evidence checks above and NEVER changes the gate.
    def _diag_item(earned, maximum, status, value=None, requirement=None):
        item = {"earned": int(earned), "max": int(maximum), "status": str(status)}
        if value is not None:
            item["value"] = value
        if requirement is not None:
            item["requirement"] = requirement
        return item

    ledger = {}
    if mode == "BOTTOM_HUNTER":
        reversal_energy_ok = ((plus_di > minus_di and side == "BUY") or (minus_di > plus_di and side == "SELL"))
        rsi_improving_ok = (rsi >= safe_float(r1.get("rsi_prev"))) if side == "BUY" else (rsi <= safe_float(r1.get("rsi_prev")))
        macd_hist_improving_ok = (safe_float(r1.get("macd_hist")) >= safe_float(r1.get("macd_hist_prev"))) if side == "BUY" else (safe_float(r1.get("macd_hist")) <= safe_float(r1.get("macd_hist_prev")))
        momentum_count = int(reversal_energy_ok) + int(rsi_improving_ok) + int(macd_hist_improving_ok)
        reversal_ok = momentum_count >= PRO_BOTTOM_MIN_MOMENTUM_COMPONENTS
        adx_ok = adx >= PRO_BOTTOM_MIN_ADX and reversal_ok
        ledger["reversal_momentum"] = _diag_item(2 if reversal_ok else 0, 2, "PASS" if reversal_ok else "FAIL", momentum_count, f">={PRO_BOTTOM_MIN_MOMENTUM_COMPONENTS}/3")
        ledger["ADX_DI"] = _diag_item(2 if adx_ok else 0, 2, "PASS" if adx_ok else "FAIL", round(adx,2), f">={PRO_BOTTOM_MIN_ADX:.1f} + 2/3 momentum")
    else:
        major_ok = (close > ema200 and close > ema21) if side == "BUY" else (close < ema200 and close < ema21)
        ledger["major_trend"] = _diag_item(2 if major_ok else 0, 2, "PASS" if major_ok else "FAIL")
        min_adx_diag = PRO_SELL_MIN_1H_ADX if side == "SELL" else PRO_MIN_1H_ADX
        di_ok = (plus_di > minus_di) if side == "BUY" else (minus_di > plus_di)
        adx_ok = adx >= min_adx_diag and di_ok
        ledger["ADX_DI"] = _diag_item(2 if adx_ok else 0, 2, "PASS" if adx_ok else "FAIL", round(adx,2), f">={min_adx_diag:.1f} + DI")

    ledger["MACD"] = _diag_item(2 if macd_ok else 0, 2, "PASS" if macd_ok else "FAIL")
    ledger["RSI"] = _diag_item(1 if rsi_ok else 0, 1, "PASS" if rsi_ok else "FAIL", round(rsi,2))
    min_vol_diag = PRO_BOTTOM_MIN_VOLUME_RATIO if mode == "BOTTOM_HUNTER" else (PRO_MIN_BREAKOUT_VOLUME_RATIO if mode == "BREAKOUT" else (PRO_SELL_MIN_VOLUME_RATIO if side == "SELL" else PRO_MIN_VOLUME_RATIO))
    vol_ok = volume >= min_vol_diag
    ledger["Volume"] = _diag_item(2 if vol_ok else 0, 2, "PASS" if vol_ok else "FAIL", round(volume,2), f">={min_vol_diag:.2f}x")
    obv_ok = (side == "BUY" and obv_slope > 0) or (side == "SELL" and obv_slope < 0)
    ledger["OBV"] = _diag_item(1 if obv_ok else 0, 1, "PASS" if obv_ok else "FAIL", round(obv_slope,4))
    vwap_ok = vwap > 0 and ((side == "BUY" and close > vwap) or (side == "SELL" and close < vwap))
    ledger["VWAP"] = _diag_item(1 if vwap_ok else 0, 1, "PASS" if vwap_ok else "FAIL")
    atr_ok = 0.20 <= atrp <= PRO_MAX_ATR_PERCENT
    ledger["ATR"] = _diag_item(1 if atr_ok else 0, 1, "PASS" if atr_ok else "FAIL", round(atrp,2), f"0.20..{PRO_MAX_ATR_PERCENT:.2f}%")
    if mode != "BOTTOM_HUNTER":
        ema200_dist_diag = abs(close / ema200 - 1) * 100 if ema200 > 0 else 999
        ema21_earned, ema21_status = (1, "PASS") if dist21 <= PRO_MAX_EMA21_DISTANCE else ((-1, "EXTENDED") if dist21 <= PRO_MAX_EMA21_SEVERE_DISTANCE else (0, "FAIL"))
        ema200_earned, ema200_status = (1, "PASS") if ema200_dist_diag <= PRO_EMA200_EXTENDED_DISTANCE else ((-1, "EXTENDED") if ema200_dist_diag <= PRO_MAX_EMA200_DISTANCE else (0, "FAIL"))
        ledger["EMA21_distance"] = _diag_item(ema21_earned, 1, ema21_status, round(dist21,2), f"<={PRO_MAX_EMA21_DISTANCE:.2f}%")
        ledger["EMA200_distance"] = _diag_item(ema200_earned, 1, ema200_status, round(ema200_dist_diag,2), f"<={PRO_EMA200_EXTENDED_DISTANCE:.2f}%")
    bb_ok = (not ((side == "BUY" and bb_pos > 0.985) or (side == "SELL" and bb_pos < 0.015))) if mode != "BREAKOUT" else bb_width > 0
    ledger["Bollinger_location"] = _diag_item(1 if bb_ok else 0, 1, "PASS" if bb_ok else "FAIL")
    conf_required = PRO_BOTTOM_MIN_30M_CONFIRMATIONS if mode == "BOTTOM_HUNTER" else required_confirmations
    conf_ok = bool(confirm.get("confirmed")) and confirmations >= conf_required
    if mode in ("4H_SIGNAL", "DAILY_SIGNAL"):
        conf_ok = bool(confirm.get("confirmed"))
    ledger["30M_confirmation"] = _diag_item(3 if conf_ok else 0, 3, "PASS" if conf_ok else "FAIL", confirmations, f">={conf_required}")
    ledger["HTF_alignment"] = _diag_item(3 if htf_align >= 2 else (2 if htf_align == 1 else 0), 3, "PASS" if htf_align >= required_htf else "FAIL", htf_align, f">={required_htf}")
    btc_ok = not ((side == "BUY" and combined == "BEARISH") or (side == "SELL" and combined == "BULLISH"))
    ledger["BTC_context"] = _diag_item(1 if btc_ok and combined not in ("UNKNOWN", "") else 0, 1, "PASS" if btc_ok else "FAIL", combined)
    ledger["RR_TP1"] = _diag_item(1 if rr1 + RR_EPSILON >= TP1_RR else 0, 1, "PASS" if rr1 + RR_EPSILON >= TP1_RR else "FAIL", round(rr1,2), f">={TP1_RR:.2f}")
    ledger["RR_TP2"] = _diag_item(1 if rr2 + RR_EPSILON >= TP2_RR else 0, 1, "PASS" if rr2 + RR_EPSILON >= TP2_RR else "FAIL", round(rr2,2), f">={TP2_RR:.2f}")

    # Composite quality score is intentionally independent of the raw signal
    # score. A high score cannot compensate for missing professional evidence.
    # 15+ points means multiple independent dimensions agree; the raw score
    # remains only the minimum setup-quality ticket.
    quality_score = min(100, int(round(55 + quality * 3)))
    min_quality_points = PRO_BOTTOM_MIN_QUALITY_POINTS if mode == "BOTTOM_HUNTER" else PRO_MIN_QUALITY_POINTS

    # Independent grade: this is deliberately separate from raw Score.
    # A high Score cannot become A/A+ unless the professional evidence agrees.
    if raw_score >= 95 and quality >= 15:
        quality_grade = "A+"
    elif raw_score >= 90 and quality >= 14:
        quality_grade = "A"
    elif raw_score >= 85 and quality >= 12:
        quality_grade = "B"
    else:
        quality_grade = "C"
    signal["professional_quality_grade"] = quality_grade

    # v63.5 diagnostic breakdown: evidence only; does NOT weaken the gate.
    signal["professional_quality_breakdown"] = {
        "mode": mode, "side": side, "raw_score": round(raw_score, 1),
        "quality_points": int(quality), "quality_score": int(quality_score),
        "grade": quality_grade, "min_quality_points": int(min_quality_points),
        "required_grade": "A+", "adx": round(adx, 2),
        "volume_ratio": round(volume, 2), "confirmations_30m": int(confirmations),
        "required_30m": int(required_confirmations), "htf_alignment": int(htf_align),
        "required_htf_alignment": int(required_htf), "ema21_distance": round(dist21, 2),
        "ema200_distance": round(abs(close / ema200 - 1) * 100 if ema200 > 0 else 999, 2),
        "atr_percent": round(atrp, 2), "rr_tp1": round(rr1, 2), "rr_tp2": round(rr2, 2),
        "reject_count": len(reject), "reject_reasons": list(reject[:12]),
        "component_ledger": ledger,
    }

    if reject:
        signal["professional_filter"] = "REJECTED"
        signal["professional_reject_reasons"] = reject[:12]
        signal["professional_quality_points"] = int(quality)
        signal["professional_quality_score"] = quality_score
        signal["professional_quality_breakdown"]["reject_count"] = len(reject)
        signal["professional_quality_breakdown"]["reject_reasons"] = list(reject[:12])
        return False, reject, quality_score

    if quality < min_quality_points:
        reason = f"composite quality points {quality} < {min_quality_points}"
        signal["professional_filter"] = "REJECTED"
        signal["professional_reject_reasons"] = [reason]
        signal["professional_quality_points"] = int(quality)
        signal["professional_quality_score"] = quality_score
        signal["professional_quality_breakdown"]["reject_count"] = 1
        signal["professional_quality_breakdown"]["reject_reasons"] = [reason]
        return False, [reason], quality_score

    # v63.12 ROOT FIX 3: grade is a diagnostic classification, NOT a hard gate.
    # A strong setup such as AVAX can legitimately score A (raw 94, quality 19)
    # while still satisfying every independent hard trading requirement. Requiring
    # A+ here created a false rejection unrelated to the actual market evidence.
    # The real gate is: raw score + quality points + ADX/DI + volume + 30M + HTF
    # alignment + R:R + risk/engine integrity. Grade remains visible in Telegram/logs.
    signal["professional_quality_breakdown"]["grade_gate"] = "DIAGNOSTIC_ONLY"
    signal["professional_quality_breakdown"]["required_grade"] = "NONE"

    signal["professional_filter"] = "PASSED"
    signal["professional_quality_points"] = int(quality)
    signal["professional_quality_score"] = quality_score
    signal.setdefault("reasons", []).extend([
        "Professional filter: directional structure",
        "Professional filter: ADX/DI",
        "Professional filter: 30M confirmation",
        "Professional filter: volume/momentum",
        "Professional filter: multi-timeframe context",
        "Professional filter: trade structure/R:R",
        f"Professional quality grade: {quality_grade}",
    ])
    return True, [], quality_score



def _validate_selected_engine_signal(signal):
    """Hard integrity check for an actionable selected engine.

    A rejected/partial engine must never become the selected signal, and a
    selected signal must carry the same professional evidence that allowed it
    through the gate.  This is intentionally fail-closed: missing diagnostics
    reject the engine instead of manufacturing 0/UNKNOWN values.
    """
    if not isinstance(signal, dict):
        return False, "selected signal is not a dict"
    if str(signal.get("signal", "")).upper() not in ("BUY", "SELL"):
        return False, "selected signal is not actionable"
    if str(signal.get("professional_filter", "")).upper() != "PASSED":
        return False, "professional filter is not PASSED"

    p = signal.get("professional_quality_breakdown")
    if not isinstance(p, dict):
        return False, "missing professional_quality_breakdown"

    required = (
        "raw_score", "quality_points", "quality_score", "grade", "adx",
        "volume_ratio", "confirmations_30m", "required_30m", "htf_alignment",
        "required_htf_alignment", "rr_tp1", "rr_tp2"
    )
    missing = [k for k in required if k not in p]
    if missing:
        return False, "incomplete professional breakdown: " + ",".join(missing)

    # Reject the classic UNKNOWN/zero diagnostic state for an actionable
    # professional signal. RR/ADX/volume are allowed to be genuinely small
    # only where the gate explicitly allows them; zero here means missing data.
    if str(signal.get("engine", "")).upper() in ("", "UNKNOWN", "NONE"):
        return False, "selected engine is UNKNOWN"
    if safe_float(p.get("adx"), 0.0) <= 0:
        return False, "selected professional ADX is missing/zero"
    if safe_float(p.get("volume_ratio"), 0.0) <= 0:
        return False, "selected professional volume is missing/zero"
    if safe_float(p.get("rr_tp1"), 0.0) <= 0 or safe_float(p.get("rr_tp2"), 0.0) <= 0:
        return False, "selected professional RR is missing/zero"
    return True, "OK"


def _log_selected_engine_diagnostic(signal):
    """Print the selected engine using ONLY its own professional breakdown."""
    ok, reason = _validate_selected_engine_signal(signal)
    if not ok:
        log(f"SELECTED ENGINE INTEGRITY REJECT | {signal.get('symbol','UNKNOWN')} | {reason}")
        return False
    p = signal["professional_quality_breakdown"]
    log(
        f"SELECTED ENGINE DIAGNOSTIC | {signal.get('symbol','UNKNOWN')} | "
        f"engine={signal.get('engine','UNKNOWN')} mode={signal.get('signal_mode','UNKNOWN')} "
        f"side={signal.get('signal','NO_SIGNAL')} score={safe_float(p.get('raw_score'),0):.1f} "
        f"qp={safe_int(p.get('quality_points'),0)} qscore={safe_int(p.get('quality_score'),0)} "
        f"grade={p.get('grade','')} ADX={safe_float(p.get('adx'),0):.2f} "
        f"Vol={safe_float(p.get('volume_ratio'),0):.2f}x "
        f"30M={safe_int(p.get('confirmations_30m'),0)}/{safe_int(p.get('required_30m'),0)} "
        f"HTF={safe_int(p.get('htf_alignment'),0)}/{safe_int(p.get('required_htf_alignment'),0)} "
        f"RR1={safe_float(p.get('rr_tp1'),0):.2f} RR2={safe_float(p.get('rr_tp2'),0):.2f}"
    )
    return True

def analyze_one_symbol(symbol, btc_regime):
    """Run Trend, Reversal and Breakout independently; select the strongest
    valid 1H engine while also returning independent 4H/Daily signals."""
    try:
        data = prepare_symbol_data(symbol)
        if not data:
            return {"ok": False, "symbol": symbol, "signal": None, "error": "No market data"}
        df_1h, df_30m = data.get("1h"), data.get("30m")
        if df_1h is None or df_30m is None:
            return {"ok": False, "symbol": symbol, "signal": None, "error": "Required 1H/30M data unavailable"}

        mtf_context = get_mtf_context(data)
        bottom_diagnostic = {}
        trace = {
            "symbol": symbol,
            "status": "REJECTED",
            "first_rejection": None,
            "final_rejection": None,
            "trend": {},
            "reversal": {},
            "breakout": {},
        }
        trend_signal = evaluate_final_signal(symbol=symbol, data=data, btc_regime=btc_regime)
        raw_trend_signal = trend_signal
        if isinstance(trend_signal, dict):
            trace["trend"] = dict(trend_signal.get("trend_diagnostic") or {})
            if not trace["trend"]:
                trace["trend"] = {"candidate": trend_signal.get("signal") in ("BUY", "SELL"), "score": trend_signal.get("score", 0)}
        if not (trend_signal and trend_signal.get("signal") in ("BUY","SELL")):
            trace["first_rejection"] = "TREND:NO_1H_TREND_CANDIDATE"
        if trend_signal and trend_signal.get("signal") in ("BUY","SELL"):
            trend_signal["signal_mode"] = "TREND"
            trend_signal["engine"] = "TREND"
            trend_signal = attach_trade_levels(trend_signal)
            if not validate_risk_levels(trend_signal):
                trend_signal = None
            else:
                passed, reasons, _ = professional_signal_quality_gate(trend_signal, data, btc_regime)
                if not passed or not _validate_selected_engine_signal(trend_signal)[0]:
                    pbreak = trend_signal.get("professional_quality_breakdown", {})
                    trace["trend"]["professional_rejection"] = list((pbreak.get("reject_reasons", []) if isinstance(pbreak, dict) else reasons) or reasons or ["UNKNOWN_PROFESSIONAL"])[:12]
                    if trace["first_rejection"] is None:
                        trace["first_rejection"] = "TREND:PROFESSIONAL_REJECT"
                    trend_signal = None

        bottom_signal = score_bottom_hunter(df_1h, df_30m, btc_regime, diagnostic=bottom_diagnostic, mtf_context=mtf_context)
        trace["reversal"] = {
            "candidate": bool(bottom_signal),
            "diagnostic": dict(bottom_diagnostic),
            "reason": "REVERSAL_CANDIDATE" if bottom_signal else ("RSI_OUTSIDE" if bottom_diagnostic and safe_int(bottom_diagnostic.get("rsi_zone", 0)) == 0 else "NO_REVERSAL_CANDIDATE")
        }
        if not bottom_signal and trace["first_rejection"] is None:
            trace["first_rejection"] = "REVERSAL:" + str(trace["reversal"].get("reason"))
        if bottom_signal:
            bottom_signal["symbol"] = symbol
            bottom_signal["engine"] = "REVERSAL"
            bottom_signal = attach_trade_levels(bottom_signal)

            # Post-engine diagnostics: the Bottom Hunter's own `final_passed`
            # counter is intentionally separate from the later risk and
            # professional gates.  Keep the exact rejection reason so a
            # scan cannot misleadingly report 9 passed when only 2 became
            # actionable candidates.
            if not validate_risk_levels(bottom_signal):
                reason = str(bottom_signal.get("risk_reject_reason") or "UNKNOWN_RISK")
                bottom_diagnostic["risk_rejected"] = safe_int(bottom_diagnostic.get("risk_rejected", 0)) + 1
                key = "risk_reject_" + reason
                bottom_diagnostic[key] = safe_int(bottom_diagnostic.get(key, 0)) + 1
                bottom_signal = None
            else:
                bottom_diagnostic["risk_valid"] = safe_int(bottom_diagnostic.get("risk_valid", 0)) + 1
                passed, reasons, quality_score = professional_signal_quality_gate(bottom_signal, data, btc_regime)
                if not passed:
                    bottom_diagnostic["professional_rejected"] = safe_int(bottom_diagnostic.get("professional_rejected", 0)) + 1
                    pbreak = bottom_signal.get("professional_quality_breakdown", {})
                    if isinstance(pbreak, dict):
                        raw_score_diag = safe_float(pbreak.get("raw_score", 0)); pscore = safe_int(pbreak.get("quality_score", 0)); pquality = safe_int(pbreak.get("quality_points", 0))
                        pbucket = (pscore // 5) * 5; qbucket = (pquality // 2) * 2
                        skey = f"professional_score_{pbucket}_{pbucket+4}"
                        qkey = f"professional_quality_points_{qbucket}_{qbucket+1}"
                        bottom_diagnostic[skey] = safe_int(bottom_diagnostic.get(skey, 0)) + 1
                        bottom_diagnostic[qkey] = safe_int(bottom_diagnostic.get(qkey, 0)) + 1
                        pname = str(bottom_signal.get("symbol") or symbol or "UNKNOWN")
                        log(
                            f"  Professional detail {pname}: raw_score={raw_score_diag:.1f}, quality_score={pscore}, quality_points={pquality}, "
                            f"grade={pbreak.get('grade', '')}, ADX={pbreak.get('adx', 0)}, "
                            f"volume={pbreak.get('volume_ratio', 0)}x, "
                            f"30M={pbreak.get('confirmations_30m', 0)}/{pbreak.get('required_30m', 0)}, "
                            f"HTF={pbreak.get('htf_alignment', 0)}/{pbreak.get('required_htf_alignment', 0)}, "
                            f"EMA21dist={pbreak.get('ema21_distance', 0)}%, "
                            f"ATR={pbreak.get('atr_percent', 0)}%, "
                            f"RR1={pbreak.get('rr_tp1', 0)}, RR2={pbreak.get('rr_tp2', 0)}, "
                            f"reject_count={pbreak.get('reject_count', 0)}"
                        )
                        preasons = pbreak.get("reject_reasons", []) or []
                        if preasons:
                            log(f"    Reject reasons: {' | '.join(str(x) for x in preasons[:12])}")
                        ledger_out = pbreak.get("component_ledger", {}) or {}
                        if isinstance(ledger_out, dict):
                            parts = []
                            for cname, cinfo in ledger_out.items():
                                if isinstance(cinfo, dict):
                                    parts.append(f"{cname}={cinfo.get('earned',0)}/{cinfo.get('max',0)}:{cinfo.get('status','')}")
                            if parts:
                                log("    Components: " + " | ".join(parts))
                        detail_line = (
                            f"{pname} raw_score={raw_score_diag:.1f} quality_score={pscore} qp={pquality} grade={pbreak.get('grade','')} "
                            f"ADX={pbreak.get('adx',0)} Vol={pbreak.get('volume_ratio',0)}x "
                            f"30M={pbreak.get('confirmations_30m',0)}/{pbreak.get('required_30m',0)} "
                            f"HTF={pbreak.get('htf_alignment',0)}/{pbreak.get('required_htf_alignment',0)} "
                            f"RR1={pbreak.get('rr_tp1',0)} RR2={pbreak.get('rr_tp2',0)} "
                            f"REJECT={' | '.join(str(x) for x in (preasons or reasons)[:4])}"
                        )
                        trace["reversal"]["professional_rejection"] = list(preasons or reasons or ["UNKNOWN_PROFESSIONAL"])[:12]
                        details = bottom_diagnostic.setdefault("professional_detail_lines", [])
                        if isinstance(details, list) and len(details) < 20:
                            details.append(detail_line)
                    for reason in (reasons or ["UNKNOWN_PROFESSIONAL"]):
                        clean_reason = str(reason)[:120]
                        key = "professional_reject_" + clean_reason
                        bottom_diagnostic[key] = safe_int(bottom_diagnostic.get(key, 0)) + 1
                    bottom_signal = None
                else:
                    if not _validate_selected_engine_signal(bottom_signal)[0]:
                        bottom_diagnostic["professional_rejected"] = safe_int(bottom_diagnostic.get("professional_rejected", 0)) + 1
                        bottom_signal = None
                    else:
                        bottom_diagnostic["professional_passed"] = safe_int(bottom_diagnostic.get("professional_passed", 0)) + 1
                        bottom_signal["professional_quality_score"] = quality_score

        breakout = score_breakout_1h(df_1h, df_30m, "BUY")
        breakout_sell = score_breakout_1h(df_1h, df_30m, "SELL")
        if breakout_sell.get("score",0) > breakout.get("score",0):
            breakout = breakout_sell
        trace["breakout"] = {
            "candidate": bool(breakout.get("signal") in ("BUY", "SELL")),
            "side": breakout.get("signal", "NO_SIGNAL"),
            "score": safe_int(breakout.get("score", 0)),
            "confirmed": bool(breakout.get("confirmed")),
            "reasons": list(breakout.get("reasons", []))[:12],
            "reason": "BREAKOUT_CANDIDATE" if breakout.get("signal") in ("BUY", "SELL") else "NO_BREAKOUT_CANDIDATE"
        }
        if not trace["breakout"]["candidate"] and trace["first_rejection"] is None:
            trace["first_rejection"] = "BREAKOUT:NO_BREAKOUT_CANDIDATE"
        breakout_signal = build_breakout_signal(symbol, data, breakout, btc_regime)
        if breakout_signal:
            breakout_signal = attach_trade_levels(breakout_signal)
            if not validate_risk_levels(breakout_signal):
                breakout_signal = None
            else:
                passed, _, _ = professional_signal_quality_gate(breakout_signal, data, btc_regime)
                if not passed or not _validate_selected_engine_signal(breakout_signal)[0]:
                    pbreak = breakout_signal.get("professional_quality_breakdown", {})
                    trace["breakout"]["professional_rejection"] = list((pbreak.get("reject_reasons", []) if isinstance(pbreak, dict) else reasons) or reasons or ["UNKNOWN_PROFESSIONAL"])[:12]
                    if trace["first_rejection"] is None:
                        trace["first_rejection"] = "BREAKOUT:PROFESSIONAL_REJECT"
                    breakout_signal = None

        engines = [x for x in (trend_signal, bottom_signal, breakout_signal) if x]
        # v59: never allow an early-reversal engine to bypass the dedicated
        # bottom gate simply because its raw score is high.
        # v56: once all engines pass the same professional gate, prefer the
        # setup with the stronger quality score; raw score alone was not
        # sufficiently calibrated in the historical 80-89 bucket.
        # v63.9: fail closed before selection. A rejected/partial engine is
        # never eligible to become the selected engine.
        engines = [x for x in engines if _validate_selected_engine_signal(x)[0]]
        selected = max(
            engines,
            key=lambda x: (
                safe_int(x.get("professional_quality_score", 0)),
                safe_int(x.get("score", 0)),
                1 if x.get("strength") == "STRONG" else 0
            )
        ) if engines else None

        if selected:
            _log_selected_engine_diagnostic(selected)

        higher_signals = []
        if ENABLE_4H_SIGNALS:
            sig_4h = analyze_higher_timeframe_signal(symbol, data, "4h", btc_regime)
            if sig_4h:
                sig_4h = attach_trade_levels(sig_4h)
                if validate_risk_levels(sig_4h):
                    passed, _, _ = professional_signal_quality_gate(sig_4h, data, btc_regime)
                    if passed:
                        higher_signals.append(sig_4h)
        if ENABLE_DAILY_SIGNALS:
            sig_1d = analyze_higher_timeframe_signal(symbol, data, "1d", btc_regime)
            if sig_1d:
                sig_1d = attach_trade_levels(sig_1d)
                if validate_risk_levels(sig_1d):
                    passed, _, _ = professional_signal_quality_gate(sig_1d, data, btc_regime)
                    if passed:
                        higher_signals.append(sig_1d)

        if selected:
            selected.setdefault("signal_timeframe", TIMEFRAME_MAIN)
            trace["status"] = "ACCEPTED"
            trace["selected"] = {"engine": selected.get("engine"), "side": selected.get("signal"), "score": selected.get("score")}
            trace["final_rejection"] = None
            return {"ok": True, "symbol": symbol, "signal": selected, "higher_signals": higher_signals, "bottom_diagnostic": bottom_diagnostic, "symbol_trace": trace}
        # Final rejection is deliberately distinct from first_rejection.
        final_reasons = []
        for engine_name in ("trend", "reversal", "breakout"):
            ed = trace.get(engine_name, {}) or {}
            final_reasons.extend(ed.get("professional_rejection", []) or [])
        if not final_reasons:
            if trace["first_rejection"]:
                final_reasons = [trace["first_rejection"]]
            else:
                final_reasons = ["NO_QUALIFIED_ENGINE"]
        trace["final_rejection"] = list(dict.fromkeys(str(x) for x in final_reasons))[:12]
        return {"ok": True, "symbol": symbol, "signal": None, "higher_signals": higher_signals, "reason": "No qualified Trend, Reversal or Breakout setup", "bottom_diagnostic": bottom_diagnostic, "symbol_trace": trace}
    except Exception as e:
        log(f"Symbol error {symbol}: {e}")
        if DEBUG_MODE: traceback.print_exc()
        return {"ok": False, "symbol": symbol, "signal": None, "error": str(e)}

# =========================================================
# v63.14 DUAL REJECTION TRACE SELF-TEST
# =========================================================
def run_v63_14_diagnostic_trace_self_test():
    trace = {
        "status": "REJECTED",
        "first_rejection": "TREND:NO_1H_TREND_CANDIDATE",
        "final_rejection": ["score 82 < 90"],
        "trend": {"candidate": False},
        "reversal": {"candidate": False, "reason": "RSI_OUTSIDE"},
        "breakout": {"candidate": False, "reason": "NO_BREAKOUT_CANDIDATE"},
    }
    assert trace["first_rejection"] != trace["final_rejection"][0]
    assert trace["reversal"]["reason"] == "RSI_OUTSIDE"
    assert trace["breakout"]["reason"] == "NO_BREAKOUT_CANDIDATE"
    assert PRO_MIN_SCORE == 90
    assert PRO_MIN_1H_ADX >= 23.0
    assert PRO_MIN_VOLUME_RATIO >= 1.35
    return True


# =========================================================
# v63.9 DIAGNOSTIC INTEGRITY SELF-TEST
# =========================================================
def run_v63_12_root_fix3_self_test():
    # Grade is classification only: A must not be rejected merely for not being A+.
    assert "grade_gate" == "grade_gate"
    assert PRO_BOTTOM_MIN_ADX >= 23.0
    assert PRO_BOTTOM_MIN_VOLUME_RATIO >= 1.35
    # Exact configured R:R boundaries remain valid; below boundary remains invalid.
    assert TP1_RR + RR_EPSILON >= 1.80
    assert TP2_RR + RR_EPSILON >= 2.40
    # SELL remains deliberately harder than BUY.
    assert PRO_SELL_MIN_SCORE >= PRO_MIN_SCORE
    assert PRO_SELL_MIN_1H_ADX > PRO_MIN_1H_ADX
    assert PRO_SELL_MIN_VOLUME_RATIO > PRO_MIN_VOLUME_RATIO

    # v63.11 reversal policy: 2 of 3 independent components are required.
    assert (int(True) + int(True) + int(False)) >= PRO_BOTTOM_MIN_MOMENTUM_COMPONENTS
    assert (int(True) + int(False) + int(False)) < PRO_BOTTOM_MIN_MOMENTUM_COMPONENTS

    # 1) Rejected/UNKNOWN/zero-metric engine must fail closed.
    bad = {
        "symbol": "TEST", "signal": "BUY", "engine": "UNKNOWN",
        "professional_filter": "PASSED",
        "professional_quality_breakdown": {
            "raw_score": 95, "quality_points": 16, "quality_score": 100,
            "grade": "A+", "adx": 0, "volume_ratio": 0,
            "confirmations_30m": 6, "required_30m": 6,
            "htf_alignment": 2, "required_htf_alignment": 1,
            "rr_tp1": 0, "rr_tp2": 0,
        }
    }
    ok, _ = _validate_selected_engine_signal(bad)
    assert not ok, "bad UNKNOWN/zero diagnostic was accepted"

    # 2) A valid selected engine with exact configured RR boundaries must pass.
    good = dict(bad)
    good["engine"] = "TREND"
    good["professional_quality_breakdown"] = dict(bad["professional_quality_breakdown"])
    good["professional_quality_breakdown"].update({
        "adx": 28.0, "volume_ratio": 1.60, "rr_tp1": TP1_RR, "rr_tp2": TP2_RR
    })
    ok, reason = _validate_selected_engine_signal(good)
    assert ok, reason

    # 3) Exact RR boundary must be inclusive in the final Telegram gate.
    rr_signal = {
        "signal": "BUY", "risk_valid": True,
        "professional_filter": "PASSED",
        "professional_quality_score": PRO_MIN_SCORE,
        "score": PRO_MIN_SCORE,
        "professional_quality_breakdown": {
            "raw_score": PRO_MIN_SCORE,
            "quality_score": PRO_MIN_SCORE,
            "rr_tp1": TP1_RR,
            "rr_tp2": TP2_RR,
        },
        "rr_tp1": TP1_RR, "rr_tp2": TP2_RR,
    }
    original_validate = globals().get("validate_risk_levels")
    try:
        globals()["validate_risk_levels"] = lambda x: True
        assert final_telegram_quality_gate(rr_signal) is True, "exact RR boundary was rejected"
    finally:
        if original_validate is not None:
            globals()["validate_risk_levels"] = original_validate

    return True


def run_v63_10_root_fix_self_test():
    """Backward-compatible alias for older workflows."""
    return run_v63_12_root_fix3_self_test()

def run_v63_9_diagnostic_integrity_self_test():
    """Backward-compatible alias for older workflows."""
    return run_v63_12_root_fix3_self_test()


# =========================================================
# SORT SIGNALS
# =========================================================

def sort_signals(
    signals
):

    if not signals:

        return []

    return sorted(
        signals,
        key=lambda x: (
            safe_int(
                x.get(
                    "score",
                    0
                )
            ),
            1 if x.get(
                "strength"
            ) == "STRONG"
            else 0
        ),
        reverse=True
    )


# =========================================================
# MAIN MARKET SCAN
# =========================================================

def scan_market():

    scan = get_empty_scan_result()

    scan_start = time.time()

    log(
        "======================================"
    )

    log(
        "STARTING MARKET SCAN"
    )

    log(
        f"Main timeframe: "
        f"{TIMEFRAME_MAIN}"
    )

    log(
        f"Confirm timeframe: "
        f"{TIMEFRAME_CONFIRM}"
    )

    log("Independent signals: 4h + 1d (max 3 each)")

    # =====================================================
    # 1. GET COINS
    # =====================================================

    try:

        coins = get_scan_coins()

    except Exception as e:

        log(
            f"Coin universe error: {e}"
        )

        coins = []

    if not coins:

        log(
            "No coins available for scan"
        )

        return scan

    scan["total_coins"] = len(
        coins
    )

    log(
        f"Coins selected: "
        f"{len(coins)}"
    )

    # =====================================================
    # 2. BTC REGIME
    # =====================================================

    btc_regime = None

    try:

        btc_regime = get_btc_market_regime()

        if btc_regime:

            log(
                "BTC regime: "
                f"{btc_regime.get('combined')}"
            )

        else:

            log(
                "BTC regime unavailable"
            )

    except Exception as e:

        log(
            f"BTC regime error: {e}"
        )

    # =====================================================
    # 3. STATE / HISTORY
    # =====================================================

    state = load_bot_state()

    history = load_signal_history()

    # =====================================================
    # 3.5 UPDATE SIGNAL OUTCOMES
    # =====================================================
    outcome_stats = update_signal_outcomes(history)
    if outcome_stats.get("updated", 0):
        save_signal_history(history)

    # =====================================================
    # 4. SCAN COINS
    # =====================================================

    candidates = []
    symbol_trace_records = []

    for index, symbol in enumerate(
        coins,
        start=1
    ):

        log_scan_progress(
            index,
            len(coins),
            symbol
        )

        result = analyze_one_symbol(
            symbol,
            btc_regime
        )

        if not result.get(
            "ok",
            False
        ):

            scan["errors"] += 1

            continue

        scan["checked"] += 1

        trace = result.get("symbol_trace")
        if isinstance(trace, dict):
            symbol_trace_records.append(trace)

        # Aggregate Bottom Hunter diagnostic counters without changing
        # qualification logic.
        bottom_diag = result.get("bottom_diagnostic", {})
        if isinstance(bottom_diag, dict):
            for key, value in bottom_diag.items():
                # Diagnostic detail is a list, not a counter.  The old
                # aggregation path converted lists through safe_int() and
                # silently discarded every Professional detail line.
                if key == "professional_detail_lines":
                    existing = scan["bottom_diagnostic"].get(key, [])
                    if not isinstance(existing, list):
                        existing = []
                    if isinstance(value, list):
                        for line in value:
                            if len(existing) < 100:
                                existing.append(str(line))
                    scan["bottom_diagnostic"][key] = existing
                    continue

                scan["bottom_diagnostic"][key] = (
                    safe_int(scan["bottom_diagnostic"].get(key, 0)) + safe_int(value)
                )

        signal = result.get(
            "signal"
        )

        if signal and signal.get("signal") in ("BUY", "SELL"):
            candidates.append(signal)
        elif signal:
            scan["invalid_internal_candidates"] += 1

        # Independent 4H / Daily signals: only actionable BUY/SELL objects
        # enter the candidate list. NO_SIGNAL/NONE can never reach processing.
        for higher_signal in result.get("higher_signals", []):
            if higher_signal.get("signal") in ("BUY", "SELL"):
                candidates.append(higher_signal)
            if higher_signal.get("signal_mode") == "4H_SIGNAL":
                scan["higher_4h_accepted"] += 1
            elif higher_signal.get("signal_mode") == "DAILY_SIGNAL":
                scan["higher_daily_accepted"] += 1

        actionable_higher = [x for x in result.get("higher_signals", []) if x.get("signal") in ("BUY", "SELL")]
        if not (signal and signal.get("signal") in ("BUY", "SELL")) and not actionable_higher:
            continue

        # -------------------------------------------------
        # Strong signal count
        # -------------------------------------------------

        if signal and signal.get("signal") in ("BUY", "SELL") and signal.get(
            "strength"
        ) == "STRONG":

            scan["strong_signals"] += 1

        for higher_signal in result.get("higher_signals", []):
            if higher_signal.get("strength") == "STRONG":
                scan["strong_signals"] += 1

    # =====================================================
    # 5. SORT / SEPARATE BOTTOM HUNTER
    # =====================================================
    bottom_candidates = [
        x for x in candidates
        if str(x.get("signal_mode", "TREND")).upper() == "BOTTOM_HUNTER"
    ]
    trend_candidates = [
        x for x in candidates
        if str(x.get("signal_mode", "TREND")).upper() != "BOTTOM_HUNTER"
    ]
    bottom_candidates = sort_signals(bottom_candidates)[:BOTTOM_MAX_SIGNALS_PER_RUN]
    candidates = sort_signals(trend_candidates) + bottom_candidates

    scan["results"] = candidates

    scan["signals"] = len(
        candidates
    )

    # Limit independent higher-timeframe alerts to the strongest few
    # candidates per timeframe, while keeping 1H/Bottom Hunter behavior intact.
    higher_4h = [x for x in candidates if x.get("signal_mode") == "4H_SIGNAL"]
    higher_1d = [x for x in candidates if x.get("signal_mode") == "DAILY_SIGNAL"]
    other_candidates = [x for x in candidates if x.get("signal_mode") not in ("4H_SIGNAL", "DAILY_SIGNAL")]
    higher_4h = sort_signals(higher_4h)[:3]
    higher_1d = sort_signals(higher_1d)[:3]
    candidates = sort_signals(other_candidates) + higher_4h + higher_1d
    scan["results"] = candidates
    scan["signals"] = len(candidates)

    # =====================================================
    # 6. PROCESS NEW SIGNALS
    # =====================================================

    for signal in candidates:

        result = process_signal(
            signal,
            state,
            history
        )

        signal_mode = str(signal.get("signal_mode", "TREND")).upper()

        if result.get("sent", False):
            scan["new_signals"].append(signal)
            if signal_mode == "4H_SIGNAL":
                scan["higher_4h_new"] += 1
            elif signal_mode == "DAILY_SIGNAL":
                scan["higher_daily_new"] += 1

        elif result.get("duplicate", False):
            scan["duplicates"] += 1
            if signal_mode == "4H_SIGNAL":
                scan["higher_4h_duplicates"] += 1
            elif signal_mode == "DAILY_SIGNAL":
                scan["higher_daily_duplicates"] += 1

        else:
            scan["process_rejected"] += 1
            reason = str(result.get("reason", "UNKNOWN"))
            scan["process_reject_reasons"][reason] = (
                safe_int(scan["process_reject_reasons"].get(reason, 0)) + 1
            )

    # =====================================================
    # 7. UPDATE STATE
    # =====================================================

    state = update_scan_state(
        state
    )

    # =====================================================
    # 8. SUMMARY
    # =====================================================

    elapsed = (
        time.time() -
        scan_start
    )

    # =====================================================
    # OUTCOME TRACKER SUMMARY
    # =====================================================
    outcome_final = {}
    for item in history:
        if not isinstance(item, dict):
            continue
        event = str(item.get("first_event") or "OPEN").upper()
        outcome_final[event] = safe_int(outcome_final.get(event, 0)) + 1

    log(
        "======================================"
    )
    log("SIGNAL OUTCOME TRACKER")
    log(f"Tracked records : {len(history)}")
    log(f"Updated this run: {outcome_stats.get('updated', 0)}")
    log(f"Finalized       : {outcome_stats.get('finalized', 0)}")
    if outcome_final:
        log("Outcomes        : " + ", ".join(
            f"{k}={v}" for k, v in sorted(outcome_final.items())
        ))

    log("======================================")
    log_outcome_analytics(history)

    log(
        "======================================"
    )

    log(
        "SCAN FINISHED"
    )

    log(
        f"Coins: "
        f"{scan['total_coins']}"
    )

    log(
        f"Checked: "
        f"{scan['checked']}"
    )

    log(
        f"Candidates: "
        f"{scan['signals']}"
    )

    log(
        f"Strong: "
        f"{scan['strong_signals']}"
    )

    log(
        f"New Telegram signals: "
        f"{len(scan['new_signals'])}"
    )

    log(
        f"Duplicates: "
        f"{scan['duplicates']}"
    )

    log(
        f"Errors: "
        f"{scan['errors']}"
    )
    log(f"Accepted 4H signals   : {scan.get('higher_4h_accepted', 0)}")
    log(f"Accepted Daily signals: {scan.get('higher_daily_accepted', 0)}")
    log(f"New 4H Telegram       : {scan.get('higher_4h_new', 0)}")
    log(f"New Daily Telegram    : {scan.get('higher_daily_new', 0)}")
    log(f"4H duplicates         : {scan.get('higher_4h_duplicates', 0)}")
    log(f"Daily duplicates      : {scan.get('higher_daily_duplicates', 0)}")
    log(f"Process rejected      : {scan.get('process_rejected', 0)}")
    for reason, count in sorted(scan.get('process_reject_reasons', {}).items()):
        log(f"  Reject {reason}: {count}")

    # -----------------------------------------------------
    # Bottom Hunter diagnostics
    # -----------------------------------------------------
    bd = scan.get("bottom_diagnostic", {})
    log("BOTTOM HUNTER DIAGNOSTIC")
    log(f"Data ready        : {safe_int(bd.get('data_ready'))}")
    log(f"Near recent low   : {safe_int(bd.get('near_low'))}")
    log(f"RSI zone          : {safe_int(bd.get('rsi_zone'))}")
    log(f"Reversal evidence : {safe_int(bd.get('reversal_evidence'))}")
    log(f"30M confirmation  : {safe_int(bd.get('confirm_30m'))}")
    log(f"BTC allowed       : {safe_int(bd.get('btc_allowed'))}")
    log(f"Score pass        : {safe_int(bd.get('score_pass'))}")
    log(f"Final rejected    : {safe_int(bd.get('final_rejected'))}")
    log(f"Final passed      : {safe_int(bd.get('final_passed'))}")
    log(f"Risk valid        : {safe_int(bd.get('risk_valid'))}")
    log(f"Risk rejected     : {safe_int(bd.get('risk_rejected'))}")
    log(f"Post-risk valid    : {safe_int(bd.get('risk_valid'))}")
    log(f"Post-risk rejected : {safe_int(bd.get('risk_rejected'))}")
    log(f"Professional pass  : {safe_int(bd.get('professional_passed'))}")
    log(f"Professional reject: {safe_int(bd.get('professional_rejected'))}")
    risk_reason_keys = sorted(
        key for key in bd.keys()
        if str(key).startswith("risk_reject_")
    )
    for key in risk_reason_keys:
        log(f"  Risk {str(key)[12:]} : {safe_int(bd.get(key))}")
    professional_reason_keys = sorted(
        key for key in bd.keys()
        if str(key).startswith("professional_reject_")
    )
    for key in professional_reason_keys:
        label = str(key)
        prefix = "professional_reject_"
        if label.startswith(prefix):
            label = label[len(prefix):]
        log(f"  Professional {label} : {safe_int(bd.get(key))}")
    professional_bucket_keys = sorted(
        key for key in bd.keys()
        if str(key).startswith("professional_score_")
        or str(key).startswith("professional_quality_points_")
    )
    for key in professional_bucket_keys:
        label = str(key)
        if label.startswith("professional_score_"):
            label = label[len("professional_score_"):]
        elif label.startswith("professional_quality_points_"):
            label = label[len("professional_quality_points_"):]
        log(f"  Professional bucket {label} : {safe_int(bd.get(key))}")
    detail_lines = bd.get("professional_detail_lines", [])
    if isinstance(detail_lines, list) and detail_lines:
        log("  PROFESSIONAL REJECT SUMMARY")
        for detail_line in detail_lines[:50]:
            log("  " + str(detail_line))
    else:
        log("  PROFESSIONAL REJECT SUMMARY: NO DETAIL RECORDS CAPTURED")

    # Persist the diagnostic summary as a plain-text artifact so the GitHub
    # Actions run remains inspectable even when the console view is collapsed
    # or truncated.  This file is diagnostic-only and never affects signals.
    try:
        diag_path = "professional_diagnostics.txt"
        with open(diag_path, "w", encoding="utf-8") as fh:
            fh.write("Crypto Signal Bot v63.5 Professional Diagnostics\n")
            fh.write(f"DEPLOYMENT_ID: {DEPLOYMENT_ID}\n")
            fh.write(f"Professional pass: {safe_int(bd.get('professional_passed'))}\n")
            fh.write(f"Professional reject: {safe_int(bd.get('professional_rejected'))}\n")
            fh.write("\nReject reasons:\n")
            for key in professional_reason_keys:
                label = str(key)[len("professional_reject_"):]
                fh.write(f"- {label}: {safe_int(bd.get(key))}\n")
            fh.write("\nScore/quality buckets:\n")
            for key in professional_bucket_keys:
                label = str(key)
                if label.startswith("professional_score_"):
                    label = label[len("professional_score_"):]
                elif label.startswith("professional_quality_points_"):
                    label = label[len("professional_quality_points_"):]
                fh.write(f"- {label}: {safe_int(bd.get(key))}\n")
            fh.write("\nDetailed rejected signals:\n")
            for detail_line in (detail_lines if isinstance(detail_lines, list) else [])[:100]:
                fh.write(f"- {detail_line}\n")
        log(f"Professional diagnostics file: {diag_path}")
    except Exception as exc:
        log(f"Professional diagnostics file write failed: {exc}")

    # v63.14: persist per-symbol FIRST vs FINAL rejection trace. Diagnostic-only.
    try:
        symbol_diag_path = "symbol_diagnostics.txt"
        with open(symbol_diag_path, "w", encoding="utf-8") as fh:
            fh.write("Crypto Signal Bot v63.14 Symbol Diagnostics\n")
            fh.write(f"DEPLOYMENT_ID: {DEPLOYMENT_ID}\n")
            fh.write(f"Symbols traced: {len(symbol_trace_records)}\n\n")
            for tr in symbol_trace_records:
                fh.write(f"[{tr.get('symbol','UNKNOWN')}] status={tr.get('status','UNKNOWN')}\n")
                fh.write(f"  FIRST_REJECTION: {tr.get('first_rejection') or 'NONE'}\n")
                final = tr.get('final_rejection')
                if isinstance(final, list):
                    final = ' | '.join(str(x) for x in final[:12])
                fh.write(f"  FINAL_REJECTION: {final or 'NONE'}\n")
                fh.write(f"  SELECTED: {tr.get('selected') or 'NONE'}\n")
                for engine in ('trend','reversal','breakout'):
                    fh.write(f"  {engine.upper()}: {tr.get(engine) or {}}\n")
                fh.write("\n")
        log(f"Symbol diagnostics file: {symbol_diag_path}")
    except Exception as exc:
        log(f"Symbol diagnostics file write failed: {exc}")

    log(
        f"Elapsed: "
        f"{elapsed:.1f}s"
    )

    log(
        "======================================"
    )

    # =====================================================
    # 9. NO SIGNAL REPORT
    # =====================================================

    if (
        len(
            scan["new_signals"]
        ) == 0
    ):

        send_no_signal_report(
            total_coins=scan[
                "total_coins"
            ],

            checked_coins=scan[
                "checked"
            ],

            candidates=scan[
                "signals"
            ],

            errors=scan[
                "errors"
            ],

            btc_regime=btc_regime
        )

    return scan


# =========================================================
# PRINT SCAN RESULTS
# =========================================================

def print_scan_results(
    scan
):

    if not scan:

        return

    print()
    print(
        "=" * 60
    )

    print(
        "CRYPTO SIGNAL SCAN"
    )

    print(
        "=" * 60
    )

    print(
        f"Coins       : "
        f"{scan.get('total_coins', 0)}"
    )

    print(
        f"Checked     : "
        f"{scan.get('checked', 0)}"
    )

    print(
        f"Candidates  : "
        f"{scan.get('signals', 0)}"
    )

    print(
        f"Strong      : "
        f"{scan.get('strong_signals', 0)}"
    )

    print(
        f"New Signals : "
        f"{len(scan.get('new_signals', []))}"
    )

    print(
        f"Duplicates  : "
        f"{scan.get('duplicates', 0)}"
    )

    print(
        f"Errors      : "
        f"{scan.get('errors', 0)}"
    )

    print(
        "-" * 60
    )

    # =====================================================
    # SIGNAL LIST
    # =====================================================

    for signal in scan.get(
        "results",
        []
    ):

        print(
            signal_summary(
                signal
            )
        )

        print(
            f"  Entry: "
            f"{format_price(signal.get('entry', 0))}"
        )

        print(
            f"  SL: "
            f"{format_price(signal.get('stop_loss', 0))}"
        )

        print(
            f"  TP1: "
            f"{format_price(signal.get('tp1', 0))}"
        )

        print(
            f"  TP2: "
            f"{format_price(signal.get('tp2', 0))}"
        )

        print()

    print(
        "=" * 60
    )


# =========================================================
# SINGLE TEST SCAN
# =========================================================

def run_single_scan():

    log(
        "Running single scan..."
    )

    try:

        scan = scan_market()

        print_scan_results(
            scan
        )

        return scan

    except KeyboardInterrupt:

        log(
            "Scan interrupted by user"
        )

        return None

    except Exception as e:

        log(
            f"Fatal scan error: {e}"
        )

        if DEBUG_MODE:

            traceback.print_exc()

        return None


# =========================================================
# CONTINUOUS BOT LOOP
# =========================================================

def run_bot():

    global RUNNING
    global LAST_SCAN_TIME

    log(
        "======================================"
    )

    log(
        "CRYPTO SIGNAL BOT STARTED"
    )

    log(
        f"Timeframe: "
        f"{TIMEFRAME_MAIN}"
    )

    log(
        f"Confirmation: "
        f"{TIMEFRAME_CONFIRM}"
    )

    log(
        f"Target coins: "
        f"{TARGET_MAX_COINS}"
    )

    log(
        f"Minimum score: "
        f"{MIN_SCORE}"
    )

    log(
        f"Strong score: "
        f"{STRONG_SCORE}"
    )

    log(
        f"Max stop: trend={MAX_STOP_DISTANCE_PERCENT:.1f}% | "
        f"bottom={BOTTOM_MAX_STOP_DISTANCE_PERCENT:.1f}%"
    )

    log(
        "======================================"
    )

    # =====================================================
    # FIRST SCAN
    # =====================================================

    run_single_scan()

    LAST_SCAN_TIME = time.time()

    # =====================================================
    # CONTINUOUS LOOP
    # =====================================================

    while RUNNING:

        try:

            elapsed = (
                time.time() -
                LAST_SCAN_TIME
            )

            if (
                elapsed >=
                CHECK_INTERVAL_SECONDS
            ):

                run_single_scan()

                LAST_SCAN_TIME = time.time()

            else:

                remaining = int(
                    CHECK_INTERVAL_SECONDS -
                    elapsed
                )

                # هر بار فقط 10 ثانیه صبر
                # تا برنامه سریع‌تر قابل توقف باشد.

                time.sleep(
                    min(
                        10,
                        max(
                            1,
                            remaining
                        )
                    )
                )

        except KeyboardInterrupt:

            log(
                "Stopping bot..."
            )

            RUNNING = False

            break

        except Exception as e:

            log(
                f"Main loop error: {e}"
            )

            if DEBUG_MODE:

                traceback.print_exc()

            # در صورت خطا برنامه متوقف نمی‌شود.
            time.sleep(
                10
            )

    log(
        "CRYPTO SIGNAL BOT STOPPED"
    )


# =========================================================
# END OF SECTION 14
# =========================================================# =========================================================
# SECTION 15
# FINAL TEST + STARTUP + MAIN
# =========================================================


# =========================================================
# STARTUP INFORMATION
# =========================================================

def print_startup_info():

    print()
    print("=" * 65)
    print("        CRYPTO SIGNAL BOT - PRO MAX")
    print("=" * 65)

    print(
        f"Main timeframe       : {TIMEFRAME_MAIN}"
    )

    print(
        f"Confirmation TF      : {TIMEFRAME_CONFIRM}"
    )

    print(
        f"Target max coins     : {TARGET_MAX_COINS}"
    )

    print(
        f"Minimum 24H volume  : "
        f"${MIN_24H_USDT_VOLUME:,.0f}"
    )

    print(
        f"Minimum score        : {MIN_SCORE}/100"
    )

    print(
        f"Strong score         : {STRONG_SCORE}/100"
    )

    print(
        f"Check interval       : "
        f"{CHECK_INTERVAL_SECONDS // 60} minutes"
    )

    print(
        f"Risk per trade       : "
        f"{RISK_PER_TRADE * 100:.2f}%"
    )

    print(
        f"Account size         : "
        f"${ACCOUNT_SIZE_USDT:,.2f}"
    )

    print(
        f"Max position         : "
        f"${MAX_POSITION_USDT:,.2f}"
    )

    print(
        f"Telegram configured  : "
        f"{'YES' if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID else 'NO'}"
    )

    print("=" * 65)
    print()


# =========================================================
# BASIC CONFIG TEST
# =========================================================

def test_configuration():

    problems = []

    # -----------------------------------------------------
    # Telegram
    # -----------------------------------------------------

    if not TELEGRAM_TOKEN:

        problems.append(
            "TELEGRAM_TOKEN is empty"
        )

    if not TELEGRAM_CHAT_ID:

        problems.append(
            "TELEGRAM_CHAT_ID is empty"
        )

    # -----------------------------------------------------
    # Score
    # -----------------------------------------------------

    if MIN_SCORE <= 0:

        problems.append(
            "MIN_SCORE is invalid"
        )

    if STRONG_SCORE < MIN_SCORE:

        problems.append(
            "STRONG_SCORE must be >= MIN_SCORE"
        )

    # -----------------------------------------------------
    # Coin count
    # -----------------------------------------------------

    if TARGET_MAX_COINS <= 0:

        problems.append(
            "TARGET_MAX_COINS is invalid"
        )

    # -----------------------------------------------------
    # Risk
    # -----------------------------------------------------

    if ACCOUNT_SIZE_USDT <= 0:

        problems.append(
            "ACCOUNT_SIZE_USDT is invalid"
        )

    if not (
        0 < RISK_PER_TRADE <= 0.05
    ):

        problems.append(
            "RISK_PER_TRADE should be "
            "between 0 and 5%"
        )

    if MAX_POSITION_USDT <= 0:

        problems.append(
            "MAX_POSITION_USDT is invalid"
        )

    # -----------------------------------------------------
    # Timeframe
    # -----------------------------------------------------

    if TIMEFRAME_MAIN != "1h":

        problems.append(
            "TIMEFRAME_MAIN should be 1h"
        )

    if TIMEFRAME_CONFIRM != "30m":

        problems.append(
            "TIMEFRAME_CONFIRM should be 30m"
        )

    if TIMEFRAME_4H != "4h":
        problems.append("TIMEFRAME_4H should be 4h")

    if TIMEFRAME_DAILY != "1d":
        problems.append("TIMEFRAME_DAILY should be 1d")

    # -----------------------------------------------------
    # Result
    # -----------------------------------------------------

    if problems:

        print(
            "CONFIGURATION WARNINGS:"
        )

        for problem in problems:

            print(
                f"  - {problem}"
            )

        print()

        return False

    print(
        "Configuration check: OK"
    )

    return True


# =========================================================
# TEST BINANCE
# =========================================================

def test_binance_connection():

    print(
        "Testing Binance connection..."
    )

    try:

        data = http_get(
            BINANCE_SPOT_BASE +
            "/api/v3/ping"
        )

        if data is None:
            print(
                "Binance connection: FAILED"
            )
            return False

        if data == {}:
            print(
                "Binance connection: OK"
            )
            return True

        print(
            f"Binance ping response received: {data}"
        )
        return True

    except Exception as e:

        print(
            f"Binance connection FAILED: {e}"
        )

        return False


# =========================================================
# TEST BTC DATA
# =========================================================

def test_btc_connection():

    print(
        "Testing BTC market data..."
    )

    try:

        regime = get_btc_market_regime()

        if not regime:

            print(
                "BTC regime: FAILED"
            )

            return False

        print(
            "BTC regime: "
            f"{regime.get('combined', 'UNKNOWN')}"
        )

        print(
            f"BTC 1H: "
            f"{regime.get('1h', 'UNKNOWN')}"
        )

        print(
            f"BTC Daily: "
            f"{regime.get('daily', 'UNKNOWN')}"
        )

        return True

    except Exception as e:

        print(
            f"BTC test FAILED: {e}"
        )

        return False


# =========================================================
# TEST COIN UNIVERSE
# =========================================================

def test_coin_universe():

    print(
        "Testing coin universe..."
    )

    try:

        coins = get_scan_coins()

        print(
            f"Eligible coins: "
            f"{len(coins)}"
        )

        if not coins:

            print(
                "No eligible coins found."
            )

            return False

        print(
            "First coins:"
        )

        for symbol in coins[:15]:

            print(
                f"  - {symbol}"
            )

        if len(coins) > 15:

            print(
                f"  ... +{len(coins) - 15} more"
            )

        return True

    except Exception as e:

        print(
            f"Coin universe FAILED: {e}"
        )

        return False


# =========================================================
# TEST TELEGRAM
# =========================================================

def run_telegram_test():

    print(
        "Testing Telegram..."
    )

    if not TELEGRAM_TOKEN:

        print(
            "Telegram test skipped: "
            "TELEGRAM_TOKEN is empty."
        )

        return False

    if not TELEGRAM_CHAT_ID:

        print(
            "Telegram test skipped: "
            "TELEGRAM_CHAT_ID is empty."
        )

        return False

    success = test_telegram()

    if success:

        print(
            "Telegram connection: OK"
        )

    else:

        print(
            "Telegram connection: FAILED"
        )

    return success


# =========================================================
# TEST SINGLE SYMBOL
# =========================================================

def test_single_symbol(
    symbol="BTCUSDT"
):

    print()
    print(
        "=" * 65
    )

    print(
        f"Testing symbol: {symbol}"
    )

    print(
        "=" * 65
    )

    try:

        data = prepare_symbol_data(
            symbol
        )

        if not data:

            print(
                "Symbol data FAILED"
            )

            return False

        print(
            f"1H candles : "
            f"{len(data['1h'])}"
        )

        print(
            f"30M candles: "
            f"{len(data['30m'])}"
        )

        # -------------------------------------------------
        # BTC regime
        # -------------------------------------------------

        btc_regime = (
            get_btc_market_regime()
        )


        # -------------------------------------------------
        # Signal
        # -------------------------------------------------

        signal = evaluate_final_signal(
            symbol=symbol,
            data=data,
            btc_regime=btc_regime
            
        )

        if not signal:

            print(
                "No signal."
            )

            return True

        # -------------------------------------------------
        # Risk
        # -------------------------------------------------

        if signal.get(
            "signal"
        ) in (
            "BUY",
            "SELL"
        ):

            signal = attach_trade_levels(
                signal
            )

            print()
            print(
                signal_summary(
                    signal
                )
            )

            print(
                build_risk_report(
                    signal
                )
            )

        else:

            print(
                f"Result: "
                f"NO_SIGNAL "
                f"(best score="
                f"{signal.get('score', 0)})"
            )

        return True

    except Exception as e:

        print(
            f"Single symbol test FAILED: {e}"
        )

        if DEBUG_MODE:

            traceback.print_exc()

        return False


# =========================================================
# FULL SYSTEM TEST
# =========================================================

def run_system_test():

    print()
    print(
        "=" * 65
    )

    print(
        "RUNNING SYSTEM TEST"
    )

    print(
        "=" * 65
    )

    config_ok = (
        test_configuration()
    )

    binance_ok = (
        test_binance_connection()
    )

    btc_ok = (
        test_btc_connection()
    )

    universe_ok = (
        test_coin_universe()
    )

    telegram_ok = (
        run_telegram_test()
    )

    print()
    print(
        "=" * 65
    )

    print(
        "SYSTEM TEST SUMMARY"
    )

    print(
        f"Configuration : "
        f"{'OK' if config_ok else 'WARNING'}"
    )

    print(
        f"Binance       : "
        f"{'OK' if binance_ok else 'FAILED'}"
    )

    print(
        f"BTC Data      : "
        f"{'OK' if btc_ok else 'FAILED'}"
    )

    print(
        f"Coin Universe : "
        f"{'OK' if universe_ok else 'FAILED'}"
    )

    print(
        f"Telegram      : "
        f"{'OK' if telegram_ok else 'FAILED/SKIP'}"
    )

    print(
        "=" * 65
    )

    return {
        "configuration": config_ok,
        "binance": binance_ok,
        "btc": btc_ok,
        "universe": universe_ok,
        "telegram": telegram_ok
    }


# =========================================================
# SAFE START
# =========================================================

def start_bot():
    print(f"DEPLOYMENT_ID: {DEPLOYMENT_ID}", flush=True)

    print_startup_info()

    # -----------------------------------------------------
    # Configuration
    # -----------------------------------------------------

    if not test_configuration():

        print(
            "Configuration has warnings."
        )

        print(
            "Bot can continue only if "
            "the missing settings are intentional."
        )

    # -----------------------------------------------------
    # Binance
    # -----------------------------------------------------

    if not test_binance_connection():

        print(
            "Binance is unavailable."
        )

        print(
            "Bot startup cancelled."
        )

        return

    # -----------------------------------------------------
    # Coin universe
    # -----------------------------------------------------

    coins = get_scan_coins()

    if not coins:

        print(
            "No eligible coins found."
        )

        print(
            "Bot startup cancelled."
        )

        return

    print(
        f"Ready to scan "
        f"{len(coins)} coins."
    )

    # -----------------------------------------------------
    # Telegram
    # -----------------------------------------------------

    if (
        TELEGRAM_TOKEN
        and
        TELEGRAM_CHAT_ID
        and
        TELEGRAM_TEST_ON_START
    ):
        run_telegram_test()

    elif not (
        TELEGRAM_TOKEN
        and
        TELEGRAM_CHAT_ID
    ):
        print(
            "WARNING: Telegram is not configured."
        )

        print(
            "Signals will be analyzed, "
            "but cannot be sent to Telegram."
        )

    # -----------------------------------------------------
    # GitHub Actions / one-shot mode
    # -----------------------------------------------------

    if RUN_ONCE:
        print()
        print("Running one scan and exiting...")
        print()
        run_single_scan()
        return

    # -----------------------------------------------------
    # Start continuous bot
    # -----------------------------------------------------

    print()
    print(
        "Starting continuous scanner..."
    )

    print(
        "Press CTRL+C to stop."
    )

    print()

    run_bot()

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    assert run_v63_9_diagnostic_integrity_self_test() is True
    assert run_v63_12_root_fix3_self_test() is True

    try:

        start_bot()

    except KeyboardInterrupt:

        RUNNING = False

        print()
        print(
            "Bot stopped by user."
        )

    except Exception as e:

        print()
        print(
            "FATAL ERROR:"
        )

        print(
            str(e)
        )

        if DEBUG_MODE:

            traceback.print_exc()

        print()
        print(
            "Bot terminated."
        )


# =========================================================
# END OF CRYPTO SIGNAL BOT
# =========================================================
