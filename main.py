# =========================================================
# Crypto Signal Bot - PRO MAX 1H
# Binance Spot Data Only
# Main TF: 1H
# Confirmation TF: 30M
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

KLINE_LIMIT_MAIN = 250
KLINE_LIMIT_CONFIRM = 250


# =========================================================
# 3. SIGNAL SCORE
# =========================================================

MIN_SCORE = 70
STRONG_SCORE = 82

BOTTOM_MIN_SCORE = 64
BOTTOM_MAX_SIGNALS_PER_RUN = 2
BOTTOM_LOOKBACK = 72
BOTTOM_NEAR_LOW_PERCENT = 4.5
BOTTOM_RSI_MIN = 24
BOTTOM_RSI_MAX = 44
BOTTOM_MAX_DISTANCE_EMA21 = 10.0

# Bottom Hunter v31 quality caps.
# These prevent a setup from reaching a high score mainly from generic
# reversal evidence when RSI/ADX/volume are not supportive.
BOTTOM_ADX_CAP_WEAK = 80
BOTTOM_ADX_CAP_MODERATE = 86
BOTTOM_ADX_CAP_GOOD = 92
BOTTOM_VOLUME_CAP_VERY_WEAK = 80
BOTTOM_VOLUME_CAP_WEAK = 86
BOTTOM_VOLUME_CAP_ACCEPTABLE = 92
BOTTOM_RSI_OUTSIDE_CAP = 78
BOTTOM_NO_RSI_ZONE_CAP = 75


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

TP1_RR = 1.60
TP2_RR = 2.80


# =========================================================
# 10. PRICE DISTANCE FILTER
# =========================================================

# جلوگیری از ورود بعد از یک حرکت بیش از حد کشیده

MAX_DISTANCE_FROM_EMA21 = 4.5

# ورود بسیار دیرهنگام: اگر هم RSI بالا باشد و هم قیمت از EMA21 دور شده باشد،
# سیگنال صادر نمی‌شود تا احتمال خرید در سقف حرکت کمتر شود.
MAX_LATE_ENTRY_EMA21_DISTANCE = 5.5
MAX_LATE_ENTRY_RSI_BUY = 67.0
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
BINANCE_VOLUME_CACHE_TTL = 60


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
        and (current_time - BINANCE_VOLUME_CACHE_TIME) < BINANCE_VOLUME_CACHE_TTL
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

        return {
            "1h": main_df,
            "30m": confirm_df
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
# APPLY INDICATORS TO BOTH TIMEFRAMES
# =========================================================

def prepare_symbol_data(symbol):

    try:

        # -------------------------------------------------
        # Get raw market data
        # -------------------------------------------------

        data = get_symbol_market_data(
            symbol
        )

        if not data:
            return None

        # -------------------------------------------------
        # Extract 1H / 30M
        # -------------------------------------------------

        main_df = data.get("1h")
        confirm_df = data.get("30m")

        # -------------------------------------------------
        # Validate raw data
        # -------------------------------------------------

        if not validate_market_dataframe(
            main_df
        ):
            log(
                f"⚠️ Invalid 1H data: {symbol}"
            )
            return None

        if not validate_market_dataframe(
            confirm_df
        ):
            log(
                f"⚠️ Invalid 30M data: {symbol}"
            )
            return None

        # -------------------------------------------------
        # Add indicators to 1H
        # -------------------------------------------------

        main_df = add_indicators(
            main_df
        )

        if main_df is None:
            log(
                f"⚠️ Failed indicators 1H: "
                f"{symbol}"
            )
            return None

        if main_df.empty:
            return None

        # -------------------------------------------------
        # Add indicators to 30M
        # -------------------------------------------------

        confirm_df = add_indicators(
            confirm_df
        )

        if confirm_df is None:
            log(
                f"⚠️ Failed indicators 30M: "
                f"{symbol}"
            )
            return None

        if confirm_df.empty:
            return None

        # -------------------------------------------------
        # Final validation
        # -------------------------------------------------

        if not validate_market_dataframe(
            main_df
        ):
            return None

        if not validate_market_dataframe(
            confirm_df
        ):
            return None

        # -------------------------------------------------
        # Return dictionary
        # IMPORTANT:
        # Do NOT return tuple
        # -------------------------------------------------

        return {
            "1h": main_df,
            "30m": confirm_df
        }

    except Exception as e:

        log(
            f"⚠️ prepare_symbol_data "
            f"error {symbol}: {e}"
        )

        if DEBUG_MODE:
            traceback.print_exc()

        return None


# =========================================================
# TEST SINGLE SYMBOL
# =========================================================

def test_symbol_data(symbol="BTC"):

    try:

        log(
            f"Testing market data: {symbol}"
        )

        data = prepare_symbol_data(
            symbol
        )

        if not data:

            log(
                f"❌ Test failed: {symbol}"
            )

            return False

        main_df = data.get("1h")
        confirm_df = data.get("30m")

        if main_df is None:
            return False

        if confirm_df is None:
            return False

        log(
            f"✅ {symbol} 1H rows: "
            f"{len(main_df)}"
        )

        log(
            f"✅ {symbol} 30M rows: "
            f"{len(confirm_df)}"
        )

        return True

    except Exception as e:

        log(
            f"❌ test_symbol_data error: "
            f"{e}"
        )

        return False


# =========================================================
# END OF SECTION 4
# =========================================================# =========================================================
# SECTION 5
# TECHNICAL INDICATORS
# EMA / RSI / MACD / ATR / ADX / VOLUME
# =========================================================


# =========================================================
# ADD INDICATORS
# =========================================================

def add_indicators(df):

    if df is None or len(df) < 50:
        return None

    df = df.copy()

    df["ema9"] = df["close"].ewm(
        span=EMA_FAST,
        adjust=False,
        min_periods=9
    ).mean()

    df["ema21"] = df["close"].ewm(
        span=EMA_MID,
        adjust=False,
        min_periods=21
    ).mean()

    df["ema50"] = df["close"].ewm(
        span=EMA_TREND,
        adjust=False,
        min_periods=50
    ).mean()

    df["ema200"] = df["close"].ewm(
        span=EMA_MAJOR,
        adjust=False,
        min_periods=50
    ).mean()

# ==========================================================
    # RSI - Wilder
    # =====================================================

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = (
        gain
        .ewm(
            alpha=1 / RSI_PERIOD,
            adjust=False,
            min_periods=RSI_PERIOD
        )
        .mean()
    )

    avg_loss = (
        loss
        .ewm(
            alpha=1 / RSI_PERIOD,
            adjust=False,
            min_periods=RSI_PERIOD
        )
        .mean()
    )

    rs = pd.Series(
        np.nan,
        index=df.index,
        dtype=float
    )

    normal_loss = avg_loss > 0

    rs.loc[normal_loss] = (
        avg_gain.loc[normal_loss] /
        avg_loss.loc[normal_loss]
    )

    # اگر loss صفر باشد:
    # RSI باید نزدیک 100 باشد، نه 50
    no_loss = (
        (avg_loss <= 0) &
        (avg_gain > 0)
    )

    rs.loc[no_loss] = np.inf

    neutral = (
        (avg_gain <= 0) &
        (avg_loss <= 0)
    )

    rs.loc[neutral] = 1.0

    df["rsi"] = (
        100 -
        (
            100 /
            (1 + rs)
        )
    )

    df["rsi"] = df["rsi"].clip(
        lower=0,
        upper=100
    )

    # =====================================================
    # MACD
    # =====================================================

    ema_fast = (
        df["close"]
        .ewm(
            span=MACD_FAST,
            adjust=False
        )
        .mean()
    )

    ema_slow = (
        df["close"]
        .ewm(
            span=MACD_SLOW,
            adjust=False
        )
        .mean()
    )

    df["macd"] = (
        ema_fast -
        ema_slow
    )

    df["macd_signal"] = (
        df["macd"]
        .ewm(
            span=MACD_SIGNAL,
            adjust=False
        )
        .mean()
    )

    df["macd_hist"] = (
        df["macd"] -
        df["macd_signal"]
    )

    # =====================================================
    # TRUE RANGE
    # =====================================================

    previous_close = df["close"].shift(1)

    tr1 = (
        df["high"] -
        df["low"]
    )

    tr2 = (
        df["high"] -
        previous_close
    ).abs()

    tr3 = (
        df["low"] -
        previous_close
    ).abs()

    df["tr"] = pd.concat(
        [
            tr1,
            tr2,
            tr3
        ],
        axis=1
    ).max(axis=1)

    # =====================================================
    # ATR
    # =====================================================

    df["atr"] = (
        df["tr"]
        .ewm(
            alpha=1 / ATR_PERIOD,
            adjust=False,
            min_periods=ATR_PERIOD
        )
        .mean()
    )

    df["atr_percent"] = (
        df["atr"] /
        df["close"].replace(0, np.nan) *
        100
    )

    # =====================================================
    # VOLUME
    # =====================================================

    # میانگین 20 کندل قبلی
    # کندل فعلی وارد baseline نمی‌شود
    df["volume_ma20"] = (
        df["volume"]
        .shift(1)
        .rolling(
            window=20,
            min_periods=10
        )
        .mean()
    )

    df["volume_ratio"] = (
        df["volume"] /
        df["volume_ma20"].replace(
            0,
            np.nan
        )
    )

    df["volume_ratio"] = (
        df["volume_ratio"]
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
        .clip(
            lower=0,
            upper=20
        )
    )

    # =====================================================
    # CANDLE STRUCTURE
    # =====================================================

    df["candle_range"] = (
        df["high"] -
        df["low"]
    )

    df["candle_body"] = (
        df["close"] -
        df["open"]
    ).abs()

    df["body_ratio"] = np.where(
        df["candle_range"] > 0,
        df["candle_body"] /
        df["candle_range"],
        0
    )

    df["body_ratio"] = (
        pd.Series(
            df["body_ratio"],
            index=df.index
        )
        .clip(
            lower=0,
            upper=1
        )
    )

    df["bullish_candle"] = (
        df["close"] >
        df["open"]
    )

    df["bearish_candle"] = (
        df["close"] <
        df["open"]
    )

    # =====================================================
    # DISTANCE FROM EMA
    # =====================================================

    df["distance_ema21"] = (
        (
            df["close"] -
            df["ema21"]
        )
        /
        df["ema21"].replace(
            0,
            np.nan
        )
        * 100
    )

    df["distance_ema200"] = (
        (
            df["close"] -
            df["ema200"]
        )
        /
        df["ema200"].replace(
            0,
            np.nan
        )
        * 100
    )

    # =====================================================
    # EMA SLOPE
    # =====================================================

    df["ema9_slope"] = (
        df["ema9"] -
        df["ema9"].shift(3)
    )

    df["ema21_slope"] = (
        df["ema21"] -
        df["ema21"].shift(3)
    )

    df["ema50_slope"] = (
        df["ema50"] -
        df["ema50"].shift(3)
    )

    df["ema200_slope"] = (
        df["ema200"] -
        df["ema200"].shift(5)
    )

    # =====================================================
    # ADX / DI
    # =====================================================

    up_move = (
        df["high"] -
        df["high"].shift(1)
    )

    down_move = (
        df["low"].shift(1) -
        df["low"]
    )

    plus_dm = pd.Series(
        np.where(
            (
                (up_move > down_move) &
                (up_move > 0)
            ),
            up_move,
            0.0
        ),
        index=df.index
    )

    minus_dm = pd.Series(
        np.where(
            (
                (down_move > up_move) &
                (down_move > 0)
            ),
            down_move,
            0.0
        ),
        index=df.index
    )

    atr_for_adx = (
        df["tr"]
        .ewm(
            alpha=1 / ADX_PERIOD,
            adjust=False,
            min_periods=ADX_PERIOD
        )
        .mean()
    )

    plus_dm_smoothed = (
        plus_dm
        .ewm(
            alpha=1 / ADX_PERIOD,
            adjust=False,
            min_periods=ADX_PERIOD
        )
        .mean()
    )

    minus_dm_smoothed = (
        minus_dm
        .ewm(
            alpha=1 / ADX_PERIOD,
            adjust=False,
            min_periods=ADX_PERIOD
        )
        .mean()
    )

    df["plus_di"] = (
        100 *
        plus_dm_smoothed /
        atr_for_adx.replace(
            0,
            np.nan
        )
    )

    df["minus_di"] = (
        100 *
        minus_dm_smoothed /
        atr_for_adx.replace(
            0,
            np.nan
        )
    )

    di_sum = (
        df["plus_di"] +
        df["minus_di"]
    )

    di_diff = (
        df["plus_di"] -
        df["minus_di"]
    ).abs()

    dx = (
        di_diff /
        di_sum.replace(
            0,
            np.nan
        ) *
        100
    )

    df["adx"] = (
        dx
        .ewm(
            alpha=1 / ADX_PERIOD,
            adjust=False,
            min_periods=ADX_PERIOD
        )
        .mean()
    )

    # =====================================================
    # MACD HISTOGRAM SLOPE
    # =====================================================

    df["macd_hist_prev"] = (
        df["macd_hist"].shift(1)
    )

    df["macd_hist_rising"] = (
        df["macd_hist"] >
        df["macd_hist_prev"]
    )

    df["macd_hist_falling"] = (
        df["macd_hist"] <
        df["macd_hist_prev"]
    )

    # =====================================================
    # RSI MOMENTUM
    # =====================================================

    df["rsi_prev"] = (
        df["rsi"].shift(1)
    )

    df["rsi_rising"] = (
        df["rsi"] >
        df["rsi_prev"]
    )

    df["rsi_falling"] = (
        df["rsi"] <
        df["rsi_prev"]
    )

    # =====================================================
    # HIGH / LOW STRUCTURE
    # =====================================================

    df["higher_high"] = (
        df["high"] >
        df["high"].shift(1)
    )

    df["higher_low"] = (
        df["low"] >
        df["low"].shift(1)
    )

    df["lower_high"] = (
        df["high"] <
        df["high"].shift(1)
    )

    df["lower_low"] = (
        df["low"] <
        df["low"].shift(1)
    )

    # =====================================================
    # CLEANUP
    # =====================================================

    df = df.replace(
        [np.inf, -np.inf],
        np.nan
    )

    return df

def indicators_ready(row):
    required = [
        "close",
        "ema9",
        "ema21",
        "ema50",
        "ema200",
        "rsi",
        "macd",
        "macd_signal",
        "macd_hist",
        "atr",
        "atr_percent",
        "volume_ratio",
        "body_ratio",
        "adx",
        "plus_di",
        "minus_di"
    ]

    missing = []

    for column in required:
        value = row.get(column, np.nan)

        if pd.isna(value):
            missing.append(f"{column}=NaN")
            continue

        try:
            if not np.isfinite(float(value)):
                missing.append(f"{column}=invalid")
        except Exception:
            missing.append(f"{column}=error")

    if missing:
        if DEBUG_MODE:
            log(
                f"⚠️ indicators_ready FAILED | "
                f"missing: {', '.join(missing)}"
            )
        return False

    return True


# =========================================================
# APPLY INDICATORS TO BOTH TIMEFRAMES
# =========================================================


    


# =========================================================
# END OF SECTION 5
# =========================================================# =========================================================
# SECTION 6
# BTC MARKET REGIME
# 1H + DAILY
# =========================================================


# =========================================================
# GET BTC TIMEFRAME DATA
# =========================================================

def get_btc_dataframe(
    timeframe,
    limit=250
):

    df = get_klines(
        symbol=BTC_SYMBOL,
        interval=timeframe,
        limit=limit
    )

    if df is None:
        return None

    df = add_indicators(df)

    if df is None:
        return None

    if len(df) < 5:
        return None

    return df


# =========================================================
# BTC 1H REGIME
# =========================================================

def get_btc_1h_regime():

    df = get_btc_dataframe(
        BTC_MAIN_TIMEFRAME,
        KLINE_LIMIT_MAIN
    )

    if df is None:

        log(
            "⚠️ BTC 1H data unavailable"
        )

        return {
            "regime": "UNKNOWN",
            "score": 0,
            "bullish": False,
            "bearish": False
        }

    row = df.iloc[-1]

    if not indicators_ready(row):

        return {
            "regime": "UNKNOWN",
            "score": 0,
            "bullish": False,
            "bearish": False
        }

    score = 0

    # -----------------------------------------------------
    # PRICE vs EMA200
    # -----------------------------------------------------

    if row["close"] > row["ema200"]:
        score += 2

    elif row["close"] < row["ema200"]:
        score -= 2


    # -----------------------------------------------------
    # EMA9 / EMA21
    # -----------------------------------------------------

    if row["ema9"] > row["ema21"]:
        score += 2

    elif row["ema9"] < row["ema21"]:
        score -= 2


    # -----------------------------------------------------
    # EMA21 / EMA50
    # -----------------------------------------------------

    if row["ema21"] > row["ema50"]:
        score += 1

    elif row["ema21"] < row["ema50"]:
        score -= 1


    # -----------------------------------------------------
    # MACD
    # -----------------------------------------------------

    if (
        row["macd"] >
        row["macd_signal"]
    ):
        score += 1

    elif (
        row["macd"] <
        row["macd_signal"]
    ):
        score -= 1


    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    if row["rsi"] >= 52:
        score += 1

    elif row["rsi"] <= 48:
        score -= 1


    # -----------------------------------------------------
    # ADX + DI
    # -----------------------------------------------------

    if (
        row["adx"] >= MIN_ADX
        and
        row["plus_di"] >
        row["minus_di"]
    ):
        score += 1

    elif (
        row["adx"] >= MIN_ADX
        and
        row["minus_di"] >
        row["plus_di"]
    ):
        score -= 1


    # -----------------------------------------------------
    # REGIME
    # -----------------------------------------------------

    if score >= 5:

        regime = "BULLISH"

    elif score <= -5:

        regime = "BEARISH"

    else:

        regime = "NEUTRAL"


    return {
        "regime": regime,
        "score": score,
        "bullish": regime == "BULLISH",
        "bearish": regime == "BEARISH"
    }


# =========================================================
# BTC DAILY MACRO REGIME
# =========================================================

def get_btc_daily_regime():

    df = get_btc_dataframe(
        BTC_MACRO_TIMEFRAME,
        250
    )

    if df is None:

        log(
            "⚠️ BTC Daily data unavailable"
        )

        return {
            "regime": "UNKNOWN",
            "score": 0,
            "bullish": False,
            "bearish": False
        }

    row = df.iloc[-1]

    if not indicators_ready(row):

        return {
            "regime": "UNKNOWN",
            "score": 0,
            "bullish": False,
            "bearish": False
        }

    score = 0

    # -----------------------------------------------------
    # PRICE / EMA200
    # -----------------------------------------------------

    if row["close"] > row["ema200"]:
        score += 3

    elif row["close"] < row["ema200"]:
        score -= 3


    # -----------------------------------------------------
    # EMA50 / EMA200
    # -----------------------------------------------------

    if row["ema50"] > row["ema200"]:
        score += 2

    elif row["ema50"] < row["ema200"]:
        score -= 2


    # -----------------------------------------------------
    # EMA21 / EMA50
    # -----------------------------------------------------

    if row["ema21"] > row["ema50"]:
        score += 1

    elif row["ema21"] < row["ema50"]:
        score -= 1


    # -----------------------------------------------------
    # MACD
    # -----------------------------------------------------

    if row["macd"] > row["macd_signal"]:
        score += 1

    elif row["macd"] < row["macd_signal"]:
        score -= 1


    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    if row["rsi"] >= 52:
        score += 1

    elif row["rsi"] <= 48:
        score -= 1


    # -----------------------------------------------------
    # REGIME
    # -----------------------------------------------------

    if score >= 5:

        regime = "BULLISH"

    elif score <= -5:

        regime = "BEARISH"

    else:

        regime = "NEUTRAL"


    return {
        "regime": regime,
        "score": score,
        "bullish": regime == "BULLISH",
        "bearish": regime == "BEARISH"
    }


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


def score_main_1h(df, side):
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

        if distance_ema21 > MAX_LATE_ENTRY_EMA21_DISTANCE:

            score -= 8

            reasons.append(
                f"BUY overextended from EMA21 -8 ({distance_ema21:.2f}%)"
            )

        elif distance_ema21 > MAX_DISTANCE_FROM_EMA21 * 0.75:

            score -= 3

            reasons.append(
                f"BUY somewhat extended from EMA21 -3 ({distance_ema21:.2f}%)"
            )

        if distance_ema200 > MAX_DISTANCE_FROM_EMA200:

            score -= 7

            reasons.append(
                f"BUY far from EMA200 -7 ({distance_ema200:.2f}%)"
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
    # TREND QUALITY CONTROL (v32)
    # =====================================================
    # ADX measures trend strength. A weak ADX must not be allowed to
    # produce a STRONG trend signal just because EMA/MACD/RSI agree.
    # Volume is used as a second quality check. These are score caps,
    # not hard rejections, so useful signals are not broadly suppressed.
    if adx < 15:
        if volume_ratio < TREND_WEAK_VOLUME_THRESHOLD:
            score = min(score, TREND_ADX_CAP_VERY_WEAK)
            reasons.append(
                f"Trend quality cap: very weak ADX + low volume -> max {TREND_ADX_CAP_VERY_WEAK}"
            )
        else:
            score = min(score, TREND_ADX_CAP_WEAK)
            reasons.append(
                f"Trend quality cap: weak ADX ({adx:.1f}) -> max {TREND_ADX_CAP_WEAK}"
            )
    elif adx < MIN_ADX:
        score = min(score, TREND_ADX_CAP_MODERATE)
        reasons.append(
            f"Trend quality cap: ADX below {MIN_ADX:.0f} ({adx:.1f}) -> max {TREND_ADX_CAP_MODERATE}"
        )

    if volume_ratio < TREND_WEAK_VOLUME_THRESHOLD:
        score = min(score, TREND_ADX_CAP_VERY_WEAK)
        reasons.append(
            f"Trend quality cap: low volume ({volume_ratio:.2f}x) -> max {TREND_ADX_CAP_VERY_WEAK}"
        )

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
    # FINAL TREND QUALITY CONTROL (v32)
    # =====================================================
    # Apply the quality cap to the complete 1H Trend score, including
    # 30M/BTC/structure bonuses. This prevents those bonuses from
    # rebuilding an inflated score after the main-score cap.
    def apply_trend_quality_cap(total_score, main_result):
        adx_value = safe_float(main_result.get("adx"))
        volume_value = safe_float(main_result.get("volume_ratio"))

        capped = int(total_score)

        if adx_value < 15:
            if volume_value < TREND_WEAK_VOLUME_THRESHOLD:
                capped = min(capped, TREND_ADX_CAP_VERY_WEAK)
            else:
                capped = min(capped, TREND_ADX_CAP_WEAK)
        elif adx_value < MIN_ADX:
            capped = min(capped, TREND_ADX_CAP_MODERATE)

        if volume_value < TREND_WEAK_VOLUME_THRESHOLD:
            capped = min(capped, TREND_ADX_CAP_VERY_WEAK)

        return max(0, min(100, capped))

    buy_score = apply_trend_quality_cap(buy_score, buy_main)
    sell_score = apply_trend_quality_cap(sell_score, sell_main)

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
    # STRENGTH
    # =====================================================

    selected_main = (
        buy_main if selected_side == "BUY" else sell_main
    )

    selected_adx = safe_float(selected_main.get("adx"))
    selected_volume = safe_float(selected_main.get("volume_ratio"))

    # STRONG is reserved for a score that is also backed by a minimum
    # trend strength and acceptable 1H volume.
    strong_quality_ok = (
        selected_adx >= TREND_STRONG_MIN_ADX
        and
        selected_volume >= TREND_STRONG_MIN_VOLUME
    )

    if (
        selected_score >= STRONG_SCORE
        and strong_quality_ok
    ):
        strength = "STRONG"

    elif selected_score >= MIN_SCORE:
        strength = "NORMAL"

    else:
        strength = "NONE"

    if selected_score >= STRONG_SCORE and not strong_quality_ok:
        # Keep the signal, but downgrade its label rather than rejecting it.
        # This preserves useful signals while avoiding misleading STRONG labels.
        if selected_adx < TREND_STRONG_MIN_ADX:
            reasons_note = (
                f"Strong blocked: ADX {selected_adx:.1f} < {TREND_STRONG_MIN_ADX:.0f}"
            )
        else:
            reasons_note = (
                f"Strong blocked: volume {selected_volume:.2f}x < {TREND_STRONG_MIN_VOLUME:.2f}x"
            )
    else:
        reasons_note = None

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

    if reasons_note:
        reasons.append(reasons_note)

    # =====================================================
    # CURRENT MARKET VALUES
    # =====================================================

    row = df_1h.iloc[-1]

    result.update({

        "signal": selected_side,

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

    if score < MIN_SCORE:

        return False

    price = safe_float(
        signal.get(
            "price",
            0
        )
    )

    if price <= 0:

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
MAX_STOP_DISTANCE_PERCENT = 12.0


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

    stop_distance = (
        atr *
        SL_ATR_MULTIPLIER
    )

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

    # جلوگیری از Stop غیرعادی بزرگ
    if (
        stop_percent >
        MAX_STOP_DISTANCE_PERCENT
    ):

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

    levels = calculate_trade_levels(
        signal
    )

    if not levels:

        signal["risk_valid"] = False

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

    if not signal.get(
        "risk_valid",
        False
    ):

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

        return False

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

            return False

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

            return False

    else:

        return False

    # =====================================================
    # RR VALIDATION
    # =====================================================

    if safe_float(
        signal.get(
            "rr_tp1",
            0
        )
    ) < TP1_RR:

        return False

    if safe_float(
        signal.get(
            "rr_tp2",
            0
        )
    ) < TP2_RR:

        return False

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

        f"📊 <b>1H ANALYSIS</b>\n"
        f"RSI: "
        f"{rsi:.1f}\n"

        f"ADX: "
        f"{adx:.1f}\n"

        f"Volume: "
        f"{volume_ratio:.2f}x\n"

        f"ATR: "
        f"{atr_percent:.2f}%\n\n"

        f"⏱ <b>MARKET CONFIRMATION</b>\n"
        f"BTC: "
        f"{btc_regime}\n"


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

        log(
            f"Telegram signal sent: "
            f"{signal.get('symbol')} "
            f"{signal.get('signal')} "
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
        f"<b>{telegram_escape(TIMEFRAME_CONFIRM)}</b>\n\n"

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
        "new_signals": []
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

def score_bottom_hunter(df_1h, df_30m, btc_regime=None, diagnostic=None, symbol=None):
    """Score a 1H early-reversal setup with conservative quality controls (v31)."""
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
    if low_n <= 0 or high_n <= 0 or high_n <= low_n:
        dmark("invalid_range")
        return None

    dist_low = (close / low_n - 1) * 100
    drawdown = (close / high_n - 1) * 100
    ema_dist = abs(close / ema21 - 1) * 100 if ema21 > 0 else 999
    rng = high_n - low_n
    fib618 = high_n - rng * .618
    fib786 = high_n - rng * .786
    fib_dist = min(
        abs(close / fib618 - 1) * 100 if fib618 > 0 else 999,
        abs(close / fib786 - 1) * 100 if fib786 > 0 else 999,
    )

    near_low = dist_low <= 7
    dmark("near_low" if near_low else "not_near_low")

    div = analyze_divergence(df_1h)
    bullish_rsi_div = bool(div.get("bullish_rsi", False))
    bullish_macd_div = bool(div.get("bullish_macd", False))

    score = 0
    reasons = []
    reversal = False

    # Location matters, but being near a low alone must not create a huge score.
    if dist_low <= BOTTOM_NEAR_LOW_PERCENT:
        score += 16
        reasons.append(f"Near {BOTTOM_LOOKBACK}H low ({dist_low:.2f}% above)")
    elif dist_low <= 7:
        score += 9
        reasons.append(f"Close to recent low ({dist_low:.2f}% above)")

    # RSI is the primary Bottom Hunter quality filter.
    rsi_in_zone = BOTTOM_RSI_MIN <= rsi <= BOTTOM_RSI_MAX
    if BOTTOM_RSI_MIN <= rsi <= 34:
        score += 18
        reasons.append(f"RSI oversold/recovery zone ({rsi:.1f})")
    elif 34 < rsi <= BOTTOM_RSI_MAX:
        score += 10
        reasons.append(f"RSI low recovery zone ({rsi:.1f})")
    dmark("rsi_zone" if rsi_in_zone else "rsi_outside")

    if rsi > prev_rsi and rsi >= 28:
        score += 7
        reversal = True
        reasons.append(f"RSI recovering ({prev_rsi:.1f} -> {rsi:.1f})")
    if rsi > 30 and prev_rsi <= 30:
        score += 4
        reversal = True
        reasons.append("RSI reclaimed 30")

    if bullish_rsi_div:
        score += 12
        reversal = True
        reasons.append("RSI bullish divergence")
    if bullish_macd_div:
        score += 6
        reversal = True
        reasons.append("MACD bullish divergence")

    if hist > prev_hist:
        score += 5
        reversal = True
        reasons.append("MACD histogram improving")
    if macd > macd_signal:
        score += 3
        reversal = True
        reasons.append("MACD above signal")

    if fib_dist <= 1.2:
        score += 5
        reasons.append("Price near Fibonacci 0.618/0.786 zone")
    elif fib_dist <= 2.5:
        score += 3
        reasons.append("Price near Fibonacci retracement zone")

    if vol >= 1.10:
        score += 7
        reversal = True
        reasons.append(f"Volume expansion ({vol:.2f}x)")
    elif vol >= .80:
        score += 3
        reasons.append(f"Volume acceptable ({vol:.2f}x)")
    elif vol >= .60:
        score -= 3
        reasons.append(f"Weak volume -3 ({vol:.2f}x)")
    else:
        score -= 6
        reasons.append(f"Very weak volume -6 ({vol:.2f}x)")

    if close > safe_float(row.get("open")):
        score += 4
        reversal = True
        reasons.append("Bullish 1H candle")
    if close > safe_float(prev.get("close")):
        score += 3
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
        score += min(confirm, 8)
        reversal = True
        reasons.append("30M reversal confirmation")
        dmark("confirm_30m")
    else:
        dmark("no_confirm_30m")

    if ema21 > 0 and ema_dist <= BOTTOM_MAX_DISTANCE_EMA21:
        score += 3
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
    if "BEARISH" in btc and ("STRONG" in btc or "SEVERE" in btc):
        dmark("btc_blocked")
        return None
    dmark("btc_allowed")
    if btc and "BEARISH" not in btc:
        score += 2
        reasons.append("BTC regime not strongly bearish")

    if vol < 0.60:
        dmark("volume_rejected")
        return None
    dmark("volume_valid")

    # Quality caps: Bottom Hunter should not score like a confirmed trend setup.
    if not rsi_in_zone:
        score = min(score, BOTTOM_RSI_OUTSIDE_CAP)
        reasons.append("RSI outside Bottom Hunter zone - score capped")
    if not bullish_rsi_div and not bullish_macd_div and not (rsi > prev_rsi and rsi >= 28):
        score = min(score, BOTTOM_NO_RSI_ZONE_CAP)
        reasons.append("Limited RSI reversal evidence - score capped")

    if adx < 20:
        score = min(score, BOTTOM_ADX_CAP_WEAK)
        reasons.append(f"Weak ADX ({adx:.1f}) - score capped")
    elif adx < 25:
        score = min(score, BOTTOM_ADX_CAP_MODERATE)
        reasons.append(f"Moderate ADX ({adx:.1f}) - score capped")
    else:
        score = min(score, BOTTOM_ADX_CAP_GOOD)

    if vol < 0.80:
        score = min(score, BOTTOM_VOLUME_CAP_VERY_WEAK)
        reasons.append(f"Very weak volume ({vol:.2f}x) - score capped")
    elif vol < 1.10:
        score = min(score, BOTTOM_VOLUME_CAP_WEAK)
        reasons.append(f"Weak volume ({vol:.2f}x) - score capped")
    else:
        score = min(score, BOTTOM_VOLUME_CAP_ACCEPTABLE)

    score = max(0, min(100, int(round(score))))
    if near_low:
        dmark("passed_near_low")
    else:
        dmark("failed_near_low")
    if reversal:
        dmark("reversal_evidence")
    else:
        dmark("no_reversal_evidence")

    if not (near_low and reversal and score >= BOTTOM_MIN_SCORE):
        dmark("score_pass" if score >= BOTTOM_MIN_SCORE else "score_fail")
        dmark("final_rejected")
        return None
    dmark("score_pass")
    dmark("final_passed")

    return {
        "symbol": symbol or "UNKNOWN",
        "score": score,
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
        "reasons": reasons,
        "candle_time": str(row.get("open_time")),
        "bottom_warning": "Early reversal setup; exact bottom is not confirmed.",
    }


def analyze_one_symbol(
    symbol,
    btc_regime,
    bottom_diagnostic=None
):

    try:

        # -------------------------------------------------
        # Get 1H + 30M
        # -------------------------------------------------

        data = prepare_symbol_data(
            symbol
        )

        if not data:

            return {
                "ok": False,
                "symbol": symbol,
                "signal": None,
                "error": "No market data"
            }

        # -------------------------------------------------
        # First technical screening
        # -------------------------------------------------

        df_1h = data.get(
            "1h"
        )

        if df_1h is None:

            return {
                "ok": False,
                "symbol": symbol,
                "signal": None,
                "error": "1H data unavailable"
            }

        df_30m = data.get("30m")
        bottom_signal = score_bottom_hunter(df_1h, df_30m, btc_regime, bottom_diagnostic, symbol=symbol)

        buy_main = score_main_1h(
            df_1h,
            "BUY"
        )

        sell_main = score_main_1h(
            df_1h,
            "SELL"
        )

        possible_buy = (
            buy_main.get(
                "hard_pass",
                False
            )
        )

        possible_sell = (
            sell_main.get(
                "hard_pass",
                False
            )
        )

        # -------------------------------------------------
        # DEBUG: show why both sides failed
        # -------------------------------------------------

        if not (
            possible_buy
            or
            possible_sell
        ):

            if DEBUG_MODE:

                buy_reason = buy_main.get(
                    "reasons",
                    []
                )

                sell_reason = sell_main.get(
                    "reasons",
                    []
                )

                log(
                    f"🔎 {symbol} | "
                    f"BUY: {buy_reason} | "
                    f"SELL: {sell_reason}"
                )

            if bottom_signal:
                bottom_signal = attach_trade_levels(bottom_signal)
                if validate_risk_levels(bottom_signal):
                    if isinstance(bottom_diagnostic, dict): bottom_diagnostic["risk_valid"] = safe_int(bottom_diagnostic.get("risk_valid", 0)) + 1
                    return {"ok": True, "symbol": symbol, "signal": bottom_signal}
                if isinstance(bottom_diagnostic, dict): bottom_diagnostic["risk_rejected"] = safe_int(bottom_diagnostic.get("risk_rejected", 0)) + 1

            return {
                "ok": True,
                "symbol": symbol,
                "signal": None,
                "reason": "No 1H setup",
                "buy_reasons": buy_main.get(
                    "reasons",
                    []
                ),
                "sell_reasons": sell_main.get(
                    "reasons",
                    []
                )
            }


        # -------------------------------------------------
        # Final evaluation
        # -------------------------------------------------

        signal = evaluate_final_signal(
            symbol=symbol,
            data=data,
            btc_regime=btc_regime
           
        )

        # -------------------------------------------------
        # No signal
        # -------------------------------------------------

        if not signal:

            return {
                "ok": True,
                "symbol": symbol,
                "signal": None
            }

        if signal.get(
            "signal"
        ) not in (
            "BUY",
            "SELL"
        ):

            return {
                "ok": True,
                "symbol": symbol,
                "signal": None,
                "score": signal.get(
                    "score",
                    0
                )
            }

        # -------------------------------------------------
        # Risk levels
        # -------------------------------------------------

        signal = attach_trade_levels(
            signal
        )

        # -------------------------------------------------
        # Final risk validation
        # -------------------------------------------------

        if not validate_risk_levels(signal):
            if bottom_signal:
                bottom_signal = attach_trade_levels(bottom_signal)
                if validate_risk_levels(bottom_signal):
                    if isinstance(bottom_diagnostic, dict): bottom_diagnostic["risk_valid"] = safe_int(bottom_diagnostic.get("risk_valid", 0)) + 1
                    return {"ok": True, "symbol": symbol, "signal": bottom_signal}
                if isinstance(bottom_diagnostic, dict): bottom_diagnostic["risk_rejected"] = safe_int(bottom_diagnostic.get("risk_rejected", 0)) + 1
            return {
                "ok": True, "symbol": symbol, "signal": None,
                "score": signal.get("score", 0),
                "reason": "Risk validation failed"
            }

        signal["signal_mode"] = "TREND"
        return {"ok": True, "symbol": symbol, "signal": signal}

    except Exception as e:

        log(
            f"Symbol error "
            f"{symbol}: {e}"
        )

        if DEBUG_MODE:

            traceback.print_exc()

        return {
            "ok": False,
            "symbol": symbol,
            "signal": None,
            "error": str(e)
        }

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
    bottom_diagnostic = {}

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
            btc_regime,
            bottom_diagnostic
        )

        if not result.get(
            "ok",
            False
        ):

            scan["errors"] += 1

            continue

        scan["checked"] += 1

        signal = result.get(
            "signal"
        )

        if not signal:

            continue

        candidates.append(
            signal
        )

        # -------------------------------------------------
        # Strong signal count
        # -------------------------------------------------

        if signal.get(
            "strength"
        ) == "STRONG":

            scan["strong_signals"] += 1

    # Final diagnostic counts for Bottom Hunter candidates.
    bottom_diagnostic["final_passed"] = len([x for x in candidates if str(x.get("signal_mode", "TREND")).upper() == "BOTTOM_HUNTER"])
    bottom_diagnostic["final_rejected"] = max(0, bottom_diagnostic.get("score_pass", 0) - bottom_diagnostic["final_passed"])
    scan["bottom_diagnostic"] = bottom_diagnostic

    # =====================================================
    # 5. SORT / SEPARATE BOTTOM HUNTER
    # =====================================================
    bottom_candidates=[x for x in candidates if str(x.get("signal_mode","TREND")).upper()=="BOTTOM_HUNTER"]
    trend_candidates=[x for x in candidates if str(x.get("signal_mode","TREND")).upper()!="BOTTOM_HUNTER"]
    bottom_candidates=sort_signals(bottom_candidates)[:BOTTOM_MAX_SIGNALS_PER_RUN]
    candidates=sort_signals(trend_candidates)+bottom_candidates

    scan["results"] = candidates

    scan["signals"] = len(
        candidates
    )

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

    print("BOTTOM HUNTER DIAGNOSTIC")
    print(f"Data ready        : {scan.get('bottom_diagnostic', {}).get('data_ready', 0)}")
    print(f"Near recent low   : {scan.get('bottom_diagnostic', {}).get('near_low', 0)}")
    print(f"RSI zone          : {scan.get('bottom_diagnostic', {}).get('rsi_zone', 0)}")
    print(f"Reversal evidence : {scan.get('bottom_diagnostic', {}).get('reversal_evidence', 0)}")
    print(f"30M confirmation  : {scan.get('bottom_diagnostic', {}).get('confirm_30m', 0)}")
    print(f"BTC allowed       : {scan.get('bottom_diagnostic', {}).get('btc_allowed', 0)}")
    print(f"Score pass        : {scan.get('bottom_diagnostic', {}).get('score_pass', 0)}")
    print(f"Final rejected    : {scan.get('bottom_diagnostic', {}).get('final_rejected', 0)}")
    print(f"Final passed      : {scan.get('bottom_diagnostic', {}).get('final_passed', 0)}")
    print(f"Risk valid        : {scan.get('bottom_diagnostic', {}).get('risk_valid', 0)}")
    print(f"Risk rejected     : {scan.get('bottom_diagnostic', {}).get('risk_rejected', 0)}")

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

        if data == {}:

            print(
                "Binance connection: OK"
            )

            return True

        print(
            "Binance ping response received"
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
