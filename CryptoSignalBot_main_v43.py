# =========================================================
# Crypto Signal Bot - PRO MAX 1H
# Binance Spot Data Only
# Main TF: 1H
# Confirmation TF: 30M
# Higher TF Context: 4H + Daily
# Binance Spot only | No auto-trading
# Version: 2026-10-02 v43 | Independent Trend + Reversal + Breakout + 1H/4H/Daily signals
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
HIGHER_TF_MIN_SCORE = 70
HIGHER_TF_STRONG_SCORE = 80

KLINE_LIMIT_MAIN = 250
KLINE_LIMIT_CONFIRM = 250
KLINE_LIMIT_4H = 250
KLINE_LIMIT_DAILY = 250


# =========================================================
# 3. SIGNAL SCORE
# =========================================================

MIN_SCORE = 66
STRONG_SCORE = 80
BREAKOUT_MIN_SCORE = 66
BREAKOUT_LOOKBACK = 20
BREAKOUT_BUFFER_PERCENT = 0.15
BREAKOUT_MIN_VOLUME_RATIO = 1.10

BOTTOM_MIN_SCORE = 62
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

TARGET_MAX_COINS = 150

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

TP1_RR = 1.35
TP2_RR = 2.10

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

BTC_SYMBOL = "BTCUSDT"

BTC_MAIN_TIMEFRAME = "1h"
BTC_MACRO_TIMEFRAME = "1d"



# =========================================================
# 15. FILES
# =========================================================

STATE_FILE = "signals_state.json"

HISTORY_FILE = "signals_history.json"


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
    print("🚀 BUILDING FINAL 1H SCAN UNIVERSE")
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
    # 3. تقاطع لیست ثابت و Binance
    # -----------------------------------------------------

    common_coins = curated & binance_coins

    print(
        f"🔗 Curated ∩ Binance: "
        f"{len(common_coins)} coins"
    )

    if not common_coins:

        print(
            "❌ No common coins found."
        )

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
        "volume_ratio", "body_ratio", "adx", "plus_di", "minus_di"
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
    # Confirmation threshold
    # -----------------------------------------------------

    confirmed = score >= 2

    return {
        "score": (
            SCORE_CONFIRM_30M
            if confirmed
            else 0
        ),
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
        or df_4h is None
        or df_daily is None
        or len(df_1h) < 50
        or len(df_30m) < 30
        or len(df_4h) < 50
        or len(df_daily) < 50
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
        and sell_score >= MIN_SCORE
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
            "strength": "NONE"
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
            TP1_RR
        )

        tp2 = (
            entry +
            risk_per_unit *
            TP2_RR
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
            TP1_RR
        )

        tp2 = (
            entry -
            risk_per_unit *
            TP2_RR
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

    if safe_float(
        signal.get(
            "rr_tp1",
            0
        )
    ) < TP1_RR:
        return reject("TP1_RR_TOO_LOW")

    if safe_float(
        signal.get(
            "rr_tp2",
            0
        )
    ) < TP2_RR:
        return reject("TP2_RR_TOO_LOW")

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

def get_empty_state():
    return {
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

    return key in last_signals


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
            "duplicate": False
        }

    if signal.get(
        "signal"
    ) not in (
        "BUY",
        "SELL"
    ):

        return {
            "sent": False,
            "duplicate": False
        }

    # -----------------------------------------------------
    # Duplicate Check
    # -----------------------------------------------------

    if is_duplicate_signal(
        signal,
        state
    ):

        log(
            f"Duplicate skipped: "
            f"{signal.get('symbol')} "
            f"{signal.get('signal')} "
            f"{signal.get('candle_time')}"
        )

        return {
            "sent": False,
            "duplicate": True
        }

    # -----------------------------------------------------
    # Telegram
    # -----------------------------------------------------

    sent = send_signal_to_telegram(
        signal
    )

    if not sent:

        log(
            f"Telegram failed: "
            f"{signal.get('symbol')}"
        )

        return {
            "sent": False,
            "duplicate": False
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
        "higher_daily_accepted": 0
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
        trend_signal = evaluate_final_signal(symbol=symbol, data=data, btc_regime=btc_regime)
        if trend_signal and trend_signal.get("signal") in ("BUY","SELL"):
            trend_signal["signal_mode"] = "TREND"
            trend_signal["engine"] = "TREND"
            trend_signal = attach_trade_levels(trend_signal)
            if not validate_risk_levels(trend_signal):
                trend_signal = None

        bottom_signal = score_bottom_hunter(df_1h, df_30m, btc_regime, diagnostic=bottom_diagnostic, mtf_context=mtf_context)
        if bottom_signal:
            bottom_signal["symbol"] = symbol
            bottom_signal["engine"] = "REVERSAL"
            bottom_signal = attach_trade_levels(bottom_signal)
            if not validate_risk_levels(bottom_signal):
                bottom_signal = None

        breakout = score_breakout_1h(df_1h, df_30m, "BUY")
        breakout_sell = score_breakout_1h(df_1h, df_30m, "SELL")
        if breakout_sell.get("score",0) > breakout.get("score",0):
            breakout = breakout_sell
        breakout_signal = build_breakout_signal(symbol, data, breakout, btc_regime)
        if breakout_signal:
            breakout_signal = attach_trade_levels(breakout_signal)
            if not validate_risk_levels(breakout_signal):
                breakout_signal = None

        engines = [x for x in (trend_signal, bottom_signal, breakout_signal) if x]
        selected = max(engines, key=lambda x: (safe_int(x.get("score",0)), 1 if x.get("strength")=="STRONG" else 0)) if engines else None

        higher_signals = []
        if ENABLE_4H_SIGNALS:
            sig_4h = analyze_higher_timeframe_signal(symbol, data, "4h", btc_regime)
            if sig_4h:
                sig_4h = attach_trade_levels(sig_4h)
                if validate_risk_levels(sig_4h):
                    higher_signals.append(sig_4h)
        if ENABLE_DAILY_SIGNALS:
            sig_1d = analyze_higher_timeframe_signal(symbol, data, "1d", btc_regime)
            if sig_1d:
                sig_1d = attach_trade_levels(sig_1d)
                if validate_risk_levels(sig_1d):
                    higher_signals.append(sig_1d)

        if selected:
            selected.setdefault("signal_timeframe", TIMEFRAME_MAIN)
            return {"ok": True, "symbol": symbol, "signal": selected, "higher_signals": higher_signals, "bottom_diagnostic": bottom_diagnostic}
        return {"ok": True, "symbol": symbol, "signal": None, "higher_signals": higher_signals, "reason": "No qualified Trend, Reversal or Breakout setup", "bottom_diagnostic": bottom_diagnostic}
    except Exception as e:
        log(f"Symbol error {symbol}: {e}")
        if DEBUG_MODE: traceback.print_exc()
        return {"ok": False, "symbol": symbol, "signal": None, "error": str(e)}

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
    # 4. SCAN COINS
    # =====================================================

    candidates = []

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

        # Aggregate Bottom Hunter diagnostic counters without changing
        # qualification logic.
        bottom_diag = result.get("bottom_diagnostic", {})
        if isinstance(bottom_diag, dict):
            for key, value in bottom_diag.items():
                scan["bottom_diagnostic"][key] = (
                    safe_int(scan["bottom_diagnostic"].get(key, 0)) + safe_int(value)
                )

        signal = result.get(
            "signal"
        )

        if signal:
            candidates.append(signal)

        # Independent 4H / Daily signals
        for higher_signal in result.get("higher_signals", []):
            candidates.append(higher_signal)
            if higher_signal.get("signal_mode") == "4H_SIGNAL":
                scan["higher_4h_accepted"] += 1
            elif higher_signal.get("signal_mode") == "DAILY_SIGNAL":
                scan["higher_daily_accepted"] += 1

        if not signal and not result.get("higher_signals"):
            continue

        # -------------------------------------------------
        # Strong signal count
        # -------------------------------------------------

        if signal and signal.get(
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

        if result.get(
            "sent",
            False
        ):

            scan["new_signals"].append(
                signal
            )

        elif result.get(
            "duplicate",
            False
        ):

            scan["duplicates"] += 1

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
    log(f"Accepted 4H signals : {scan.get('higher_4h_accepted', 0)}")
    log(f"Accepted Daily signals: {scan.get('higher_daily_accepted', 0)}")

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
    risk_reason_keys = sorted(
        key for key in bd.keys()
        if str(key).startswith("risk_reject_")
    )
    for key in risk_reason_keys:
        log(f"  {str(key)[13:]} : {safe_int(bd.get(key))}")

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