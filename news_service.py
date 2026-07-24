import hashlib
import html
import json
import os
import re
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup


# =========================================================
# GOLDEN AI NEWS SETTINGS
# =========================================================

NEWS_UPDATE_INTERVAL = int(
    os.environ.get("NEWS_UPDATE_INTERVAL", "60")
)

NEWS_REQUEST_TIMEOUT = int(
    os.environ.get("NEWS_REQUEST_TIMEOUT", "12")
)

MAX_CACHE_NEWS = int(
    os.environ.get("MAX_CACHE_NEWS", "150")
)

MAX_ARTICLES_PER_FEED = int(
    os.environ.get("MAX_ARTICLES_PER_FEED", "30")
)

MAX_PARALLEL_FEEDS = int(
    os.environ.get("MAX_PARALLEL_FEEDS", "6")
)

MAX_TRANSLATION_WORKERS = int(
    os.environ.get("MAX_TRANSLATION_WORKERS", "4")
)

CACHE_FILE = os.environ.get(
    "NEWS_CACHE_FILE",
    "/tmp/golden_ai_news_cache.json",
)

TRANSLATION_CACHE_FILE = os.environ.get(
    "NEWS_TRANSLATION_CACHE_FILE",
    "/tmp/golden_ai_translation_cache.json",
)

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/125.0 Mobile Safari/537.36"
)

REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "application/rss+xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
    "Cache-Control": "no-cache",
}


# =========================================================
# GLOBAL MARKET NEWS QUERIES
# =========================================================

MARKET_SEARCH_QUERIES = [
    # India
    (
        "India stock market Nifty Sensex Bank Nifty "
        "RBI SEBI rupee inflation GDP economy"
    ),
    (
        "Indian company earnings results order win merger "
        "acquisition IPO dividend buyback stock"
    ),
    (
        "India government policy tax budget import export "
        "industry manufacturing market impact"
    ),

    # USA and global markets
    (
        "global stock market Wall Street Nasdaq Dow Jones "
        "S&P 500 market moving news"
    ),
    (
        "Federal Reserve interest rate inflation CPI jobs data "
        "US economy market impact"
    ),
    (
        "ECB Bank of England Bank of Japan central bank "
        "interest rate market impact"
    ),

    # Asia and Europe
    (
        "China economy PBOC yuan property manufacturing "
        "trade restrictions market"
    ),
    (
        "Japan economy yen Bank of Japan Nikkei market"
    ),
    (
        "Europe economy ECB euro inflation Germany France "
        "stock market"
    ),

    # Commodities and currencies
    (
        "crude oil Brent WTI OPEC oil supply natural gas "
        "market impact"
    ),
    (
        "gold silver copper metals commodity prices "
        "dollar bond yields"
    ),
    (
        "forex dollar index rupee yen yuan euro currency "
        "market movement"
    ),

    # Industry and corporate
    (
        "major company earnings profit warning bankruptcy "
        "merger acquisition market impact"
    ),
    (
        "technology semiconductor AI chip export restriction "
        "stock market impact"
    ),
    (
        "banking financial crisis liquidity default credit "
        "rating market impact"
    ),
    (
        "automobile EV battery lithium supply chain "
        "market impact"
    ),
    (
        "pharma healthcare drug approval trial result "
        "stock market impact"
    ),
    (
        "defence aerospace military contract company "
        "stock market impact"
    ),

    # Geopolitics
    (
        "war missile attack sanctions ceasefire geopolitical "
        "tension market oil gold"
    ),
    (
        "Red Sea shipping disruption Strait of Hormuz "
        "trade route supply chain market"
    ),
    (
        "tariff trade war export ban import restriction "
        "global market impact"
    ),

    # Weather and disasters
    (
        "earthquake flood cyclone drought heatwave wildfire "
        "supply chain commodity market impact"
    ),
    (
        "extreme weather crop production food prices "
        "commodity inflation market"
    ),

    # Crypto
    (
        "Bitcoin Ethereum crypto ETF regulation "
        "digital asset market"
    ),
]


def build_google_news_feed(query):
    encoded_query = urllib.parse.quote_plus(
        f"{query} when:1d"
    )

    return (
        "https://news.google.com/rss/search"
        f"?q={encoded_query}"
        "&hl=en-IN"
        "&gl=IN"
        "&ceid=IN:en"
    )


DEFAULT_RSS_FEEDS = [
    build_google_news_feed(query)
    for query in MARKET_SEARCH_QUERIES
]


def get_configured_feeds():
    """
    Optional Render environment variable:

    NEWS_RSS_FEEDS=url1,url2,url3

    Environment variable नहीं होने पर Golden AI की
    default global market queries इस्तेमाल होंगी।
    """

    configured = os.environ.get(
        "NEWS_RSS_FEEDS",
        "",
    ).strip()

    if not configured:
        return DEFAULT_RSS_FEEDS

    feeds = [
        item.strip()
        for item in configured.split(",")
        if item.strip()
    ]

    return feeds or DEFAULT_RSS_FEEDS


# =========================================================
# GLOBAL CACHE
# =========================================================

_cache_lock = threading.RLock()
_refresh_lock = threading.Lock()
_updater_lock = threading.Lock()
_translation_lock = threading.RLock()

_news_cache = []
_translation_cache = {}

_status = {
    "last_updated": None,
    "last_success": None,
    "last_error": None,
    "updater_running": False,
    "refresh_running": False,
    "last_fetch_count": 0,
    "cached_count": 0,
    "translation_failures": 0,
}

_updater_thread = None
_stop_event = threading.Event()


# =========================================================
# KEYWORDS
# =========================================================

DIRECT_MARKET_KEYWORDS = {
    "stock market",
    "share market",
    "stocks",
    "shares",
    "equities",
    "equity market",
    "nifty",
    "sensex",
    "bank nifty",
    "finnifty",
    "midcap nifty",
    "nifty 50",
    "nifty 500",
    "bse",
    "nse",
    "nasdaq",
    "dow jones",
    "s&p 500",
    "wall street",
    "nikkei",
    "hang seng",
    "ftse",
    "dax",
    "market rally",
    "market crash",
    "market selloff",
    "market falls",
    "market rises",
    "market volatility",
    "bull market",
    "bear market",
    "futures",
    "options",
    "derivatives",
}

ECONOMY_KEYWORDS = {
    "inflation",
    "interest rate",
    "rate cut",
    "rate hike",
    "monetary policy",
    "central bank",
    "federal reserve",
    "fed",
    "rbi",
    "sebi",
    "ecb",
    "bank of japan",
    "bank of england",
    "gdp",
    "recession",
    "economy",
    "economic growth",
    "jobs report",
    "employment data",
    "unemployment",
    "cpi",
    "ppi",
    "retail sales",
    "manufacturing",
    "factory output",
    "industrial production",
    "pmi",
    "fiscal deficit",
    "budget",
    "tax",
    "stimulus",
    "bond yields",
    "treasury yields",
    "liquidity",
    "credit rating",
    "sovereign rating",
}

POLICY_TRADE_KEYWORDS = {
    "tariff",
    "trade war",
    "export ban",
    "export restriction",
    "import restriction",
    "sanctions",
    "trade sanctions",
    "government policy",
    "regulation",
    "regulatory action",
    "antitrust",
    "custom duty",
    "import duty",
    "export duty",
    "production-linked incentive",
    "pli scheme",
}

CURRENCY_KEYWORDS = {
    "rupee",
    "dollar",
    "yen",
    "yuan",
    "euro",
    "pound",
    "forex",
    "currency",
    "dollar index",
    "currency crisis",
    "devaluation",
}

COMMODITY_KEYWORDS = {
    "crude oil",
    "brent",
    "wti",
    "opec",
    "opec+",
    "natural gas",
    "gold",
    "silver",
    "copper",
    "aluminium",
    "steel",
    "lithium",
    "commodity",
    "commodities",
    "oil prices",
    "metal prices",
    "food prices",
    "crop prices",
}

CRYPTO_KEYWORDS = {
    "bitcoin",
    "ethereum",
    "crypto",
    "cryptocurrency",
    "digital asset",
    "crypto etf",
    "stablecoin",
    "blockchain",
}

GEOPOLITICAL_KEYWORDS = {
    "war",
    "military attack",
    "missile",
    "missile attack",
    "air strike",
    "sanctions",
    "geopolitical",
    "ceasefire",
    "border conflict",
    "shipping disruption",
    "red sea",
    "strait of hormuz",
    "invasion",
    "military conflict",
    "drone attack",
}

COMPANY_KEYWORDS = {
    "earnings",
    "quarterly results",
    "profit",
    "profit rises",
    "profit falls",
    "revenue",
    "sales growth",
    "margin",
    "merger",
    "acquisition",
    "bankruptcy",
    "default",
    "ipo",
    "buyback",
    "dividend",
    "bonus issue",
    "stock split",
    "guidance",
    "profit warning",
    "layoffs",
    "regulatory approval",
    "drug approval",
    "order win",
    "large order",
    "contract win",
    "stake sale",
    "fund raising",
    "rights issue",
    "management change",
    "ceo resigns",
}

INDUSTRY_KEYWORDS = {
    "semiconductor",
    "chip",
    "artificial intelligence",
    "ai investment",
    "technology sector",
    "banking sector",
    "pharma sector",
    "automobile sector",
    "auto sector",
    "defence sector",
    "energy sector",
    "power sector",
    "real estate sector",
    "infrastructure",
    "telecom sector",
    "supply chain",
    "factory shutdown",
    "production halt",
    "plant shutdown",
    "shortage",
}

WEATHER_DISASTER_KEYWORDS = {
    "earthquake",
    "flood",
    "cyclone",
    "hurricane",
    "typhoon",
    "drought",
    "heatwave",
    "wildfire",
    "tsunami",
    "landslide",
    "extreme weather",
    "heavy rain",
    "crop damage",
    "port closure",
    "airport closure",
}

MARKET_CONNECTION_KEYWORDS = {
    "market impact",
    "investors",
    "traders",
    "prices",
    "supply",
    "demand",
    "production",
    "exports",
    "imports",
    "shipping",
    "commodity",
    "inflation",
    "company",
    "sector",
    "economy",
    "business",
    "industry",
    "trade",
    "oil",
    "gas",
    "gold",
    "currency",
    "stock",
    "shares",
}

EXCLUDED_KEYWORDS = {
    "movie review",
    "film review",
    "actor",
    "actress",
    "celebrity",
    "box office",
    "cricket match",
    "football match",
    "tennis match",
    "sports score",
    "fashion",
    "recipe",
    "relationship advice",
    "horoscope",
    "astrology",
    "wedding photos",
    "viral video",
    "reality show",
    "web series",
    "music album",
}


POSITIVE_TERMS = {
    "beats estimates",
    "profit rises",
    "profit jumps",
    "record profit",
    "revenue growth",
    "strong earnings",
    "order win",
    "wins contract",
    "large contract",
    "approval received",
    "rate cut",
    "stimulus",
    "tax cut",
    "buyback",
    "dividend",
    "bonus issue",
    "merger approved",
    "acquisition approved",
    "debt reduction",
    "rating upgrade",
    "exports rise",
    "sales rise",
    "production rises",
    "ceasefire",
    "supply restored",
    "rally",
    "surge",
    "gain",
    "growth",
}

NEGATIVE_TERMS = {
    "misses estimates",
    "profit falls",
    "profit drops",
    "loss widens",
    "weak earnings",
    "profit warning",
    "bankruptcy",
    "default",
    "fraud",
    "investigation",
    "fine imposed",
    "rate hike",
    "tariff",
    "export ban",
    "sanctions",
    "war",
    "missile attack",
    "air strike",
    "factory shutdown",
    "production halt",
    "supply disruption",
    "recession",
    "layoffs",
    "rating downgrade",
    "crash",
    "selloff",
    "slump",
    "decline",
    "falls",
    "drops",
}


# =========================================================
# TEXT HELPERS
# =========================================================

def utc_now():
    return datetime.now(timezone.utc)


def utc_now_iso():
    return utc_now().isoformat()


def clean_html(value):
    if not value:
        return ""

    text = html.unescape(str(value))

    text = re.sub(
        r"<script.*?>.*?</script>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    text = re.sub(
        r"<style.*?>.*?</style>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def normalize_title(value):
    text = clean_html(value).lower()

    text = re.sub(
        r"[^a-z0-9\u0900-\u097f]+",
        " ",
        text,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def truncate_text(value, limit=1800):
    text = clean_html(value)

    if len(text) <= limit:
        return text

    shortened = text[:limit]

    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0]

    return shortened.strip() + "..."


def split_sentences(value):
    text = clean_html(value)

    if not text:
        return []

    parts = re.split(
        r"(?<=[.!?।])\s+",
        text,
    )

    return [
        part.strip()
        for part in parts
        if len(part.strip()) >= 20
    ]


def remove_source_from_google_title(title):
    """
    Google News title अक्सर:
    Headline - Source Name

    इस function से अंतिम source suffix हटाने का प्रयास होता है।
    """

    cleaned = clean_html(title)

    parts = re.split(
        r"\s+-\s+",
        cleaned,
    )

    if len(parts) >= 2:
        possible_source = parts[-1].strip()

        if 2 <= len(possible_source.split()) <= 8:
            return " - ".join(parts[:-1]).strip()

    return cleaned


def make_article_id(title, url, published_at):
    raw_value = (
        f"{normalize_title(title)}|"
        f"{str(url).strip()}|"
        f"{str(published_at).strip()}"
    )

    return hashlib.sha256(
        raw_value.encode(
            "utf-8",
            errors="ignore",
        )
    ).hexdigest()[:24]


def contains_devanagari(text):
    return bool(
        re.search(
            r"[\u0900-\u097f]",
            str(text or ""),
        )
    )


def is_mostly_hindi(text):
    value = str(text or "")

    if not value:
        return False

    devanagari_count = len(
        re.findall(
            r"[\u0900-\u097f]",
            value,
        )
    )

    alphabet_count = len(
        re.findall(
            r"[A-Za-z\u0900-\u097f]",
            value,
        )
    )

    if alphabet_count == 0:
        return False

    return (
        devanagari_count / alphabet_count
    ) >= 0.35


# =========================================================
# DATE HELPERS
# =========================================================

def parse_date(value):
    if not value:
        return utc_now()

    raw_value = str(value).strip()

    try:
        parsed = parsedate_to_datetime(
            raw_value
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )

    except Exception:
        pass

    try:
        iso_value = raw_value.replace(
            "Z",
            "+00:00",
        )

        parsed = datetime.fromisoformat(
            iso_value
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )

    except Exception:
        return utc_now()


def date_to_iso(value):
    return parse_date(value).isoformat()


def article_timestamp(article):
    return parse_date(
        article.get(
            "published_at",
            "",
        )
    ).timestamp()


def is_recent_breaking_news(published_at):
    published_time = parse_date(
        published_at
    )

    age = utc_now() - published_time

    return age <= timedelta(
        hours=2
    )


# =========================================================
# KEYWORD AND RELEVANCE HELPERS
# =========================================================

def keyword_matches(text, keywords):
    lowered = str(text or "").lower()

    return [
        keyword
        for keyword in keywords
        if keyword in lowered
    ]


def calculate_relevance_score(title, description):
    title_lower = str(title or "").lower()
    combined = (
        f"{title or ''} {description or ''}"
    ).lower()

    excluded_matches = keyword_matches(
        combined,
        EXCLUDED_KEYWORDS,
    )

    if excluded_matches:
        return -20

    score = 0

    direct_matches = keyword_matches(
        combined,
        DIRECT_MARKET_KEYWORDS,
    )

    economy_matches = keyword_matches(
        combined,
        ECONOMY_KEYWORDS,
    )

    policy_matches = keyword_matches(
        combined,
        POLICY_TRADE_KEYWORDS,
    )

    currency_matches = keyword_matches(
        combined,
        CURRENCY_KEYWORDS,
    )

    commodity_matches = keyword_matches(
        combined,
        COMMODITY_KEYWORDS,
    )

    crypto_matches = keyword_matches(
        combined,
        CRYPTO_KEYWORDS,
    )

    geopolitical_matches = keyword_matches(
        combined,
        GEOPOLITICAL_KEYWORDS,
    )

    company_matches = keyword_matches(
        combined,
        COMPANY_KEYWORDS,
    )

    industry_matches = keyword_matches(
        combined,
        INDUSTRY_KEYWORDS,
    )

    disaster_matches = keyword_matches(
        combined,
        WEATHER_DISASTER_KEYWORDS,
    )

    connection_matches = keyword_matches(
        combined,
        MARKET_CONNECTION_KEYWORDS,
    )

    score += len(direct_matches) * 5
    score += len(economy_matches) * 4
    score += len(policy_matches) * 4
    score += len(currency_matches) * 4
    score += len(commodity_matches) * 4
    score += len(crypto_matches) * 3
    score += len(company_matches) * 4
    score += len(industry_matches) * 3
    score += len(geopolitical_matches) * 3

    # प्राकृतिक आपदा तभी market news मानी जाएगी जब
    # उसके साथ supply, commodity, company या economy connection हो।
    if disaster_matches and connection_matches:
        score += (
            len(disaster_matches) * 3
            + len(connection_matches) * 2
        )

    if keyword_matches(
        title_lower,
        DIRECT_MARKET_KEYWORDS,
    ):
        score += 7

    if keyword_matches(
        title_lower,
        ECONOMY_KEYWORDS,
    ):
        score += 5

    if keyword_matches(
        title_lower,
        COMPANY_KEYWORDS,
    ):
        score += 5

    if keyword_matches(
        title_lower,
        COMMODITY_KEYWORDS,
    ):
        score += 5

    if (
        keyword_matches(
            title_lower,
            GEOPOLITICAL_KEYWORDS,
        )
        and connection_matches
    ):
        score += 5

    return score


def is_market_relevant(title, description):
    return calculate_relevance_score(
        title,
        description,
    ) >= 5


# =========================================================
# CATEGORY, REGION, IMPORTANCE AND EFFECT
# =========================================================

def detect_category(text):
    lowered = str(text or "").lower()

    if keyword_matches(
        lowered,
        CRYPTO_KEYWORDS,
    ):
        return "Crypto"

    if any(
        term in lowered
        for term in [
            "gold",
            "silver",
            "precious metal",
        ]
    ):
        return "Gold & Silver"

    if any(
        term in lowered
        for term in [
            "crude oil",
            "brent",
            "wti",
            "opec",
            "natural gas",
        ]
    ):
        return "Energy"

    if keyword_matches(
        lowered,
        CURRENCY_KEYWORDS,
    ):
        return "Currency"

    if keyword_matches(
        lowered,
        GEOPOLITICAL_KEYWORDS,
    ):
        return "Geopolitics"

    if keyword_matches(
        lowered,
        WEATHER_DISASTER_KEYWORDS,
    ):
        return "Weather & Disaster"

    if keyword_matches(
        lowered,
        COMPANY_KEYWORDS,
    ):
        return "Corporate"

    if keyword_matches(
        lowered,
        INDUSTRY_KEYWORDS,
    ):
        return "Industry"

    if keyword_matches(
        lowered,
        ECONOMY_KEYWORDS,
    ):
        return "Economy"

    return "Stock Market"


def detect_country(text):
    lowered = f" {str(text or '').lower()} "

    country_rules = [
        (
            "India",
            [
                " india ",
                " indian ",
                " rbi ",
                " sebi ",
                " nifty ",
                " sensex ",
                " bank nifty ",
                " rupee ",
                " mumbai ",
                " new delhi ",
            ],
        ),
        (
            "USA",
            [
                " united states ",
                " u.s. ",
                " federal reserve ",
                " wall street ",
                " nasdaq ",
                " dow jones ",
                " s&p 500 ",
                " washington ",
            ],
        ),
        (
            "China",
            [
                " china ",
                " chinese ",
                " beijing ",
                " shanghai ",
                " yuan ",
                " pboc ",
            ],
        ),
        (
            "Japan",
            [
                " japan ",
                " japanese ",
                " tokyo ",
                " nikkei ",
                " bank of japan ",
                " yen ",
            ],
        ),
        (
            "Europe",
            [
                " europe ",
                " european union ",
                " eurozone ",
                " ecb ",
                " germany ",
                " france ",
                " italy ",
                " euro ",
            ],
        ),
        (
            "United Kingdom",
            [
                " united kingdom ",
                " britain ",
                " british ",
                " bank of england ",
                " london ",
                " ftse ",
                " pound ",
            ],
        ),
        (
            "Middle East",
            [
                " middle east ",
                " iran ",
                " israel ",
                " saudi arabia ",
                " uae ",
                " qatar ",
                " red sea ",
                " strait of hormuz ",
            ],
        ),
        (
            "Russia",
            [
                " russia ",
                " russian ",
                " moscow ",
            ],
        ),
        (
            "South Korea",
            [
                " south korea ",
                " korean ",
                " seoul ",
                " kospi ",
            ],
        ),
        (
            "Hong Kong",
            [
                " hong kong ",
                " hang seng ",
            ],
        ),
    ]

    for country, keywords in country_rules:
        if any(
            keyword in lowered
            for keyword in keywords
        ):
            return country

    return "Global"


def detect_importance(title, description):
    combined = (
        f"{title or ''} {description or ''}"
    ).lower()

    score = calculate_relevance_score(
        title,
        description,
    )

    high_impact_terms = {
        "emergency rate cut",
        "unexpected rate hike",
        "unexpected rate cut",
        "market crash",
        "trading halt",
        "bankruptcy",
        "sovereign default",
        "military attack",
        "missile attack",
        "major sanctions",
        "oil supply disruption",
        "financial crisis",
        "currency crisis",
        "central bank decision",
        "federal reserve decision",
        "rbi policy",
        "war begins",
        "strait of hormuz closed",
        "red sea shipping disruption",
    }

    if keyword_matches(
        combined,
        high_impact_terms,
    ):
        return "High"

    if score >= 18:
        return "High"

    if score >= 9:
        return "Medium"

    return "Low"


def detect_market_direction(title, description):
    combined = (
        f"{title or ''} {description or ''}"
    ).lower()

    positive_score = len(
        keyword_matches(
            combined,
            POSITIVE_TERMS,
        )
    )

    negative_score = len(
        keyword_matches(
            combined,
            NEGATIVE_TERMS,
        )
    )

    if positive_score > negative_score:
        return "Positive"

    if negative_score > positive_score:
        return "Negative"

    return "Neutral"


def build_market_reason(
    category,
    country,
    direction,
    importance,
    text,
):
    lowered = str(text or "").lower()

    if category == "Corporate":
        reason = (
            "इस खबर से संबंधित कंपनी, उसके sector और "
            "peer stocks में movement आ सकता है।"
        )

    elif category == "Economy":
        reason = (
            "यह खबर interest-rate expectations, liquidity, "
            "bond yields और equity sentiment को प्रभावित कर सकती है।"
        )

    elif category == "Energy":
        reason = (
            "Crude oil या energy prices में बदलाव से inflation, "
            "rupee और oil-dependent कंपनियों पर असर पड़ सकता है।"
        )

    elif category == "Gold & Silver":
        reason = (
            "इसका असर gold, silver, dollar और bond yields "
            "से जुड़े trades पर पड़ सकता है।"
        )

    elif category == "Currency":
        reason = (
            "Currency movement से import-export, IT, banking "
            "और commodity-related stocks प्रभावित हो सकते हैं।"
        )

    elif category == "Geopolitics":
        reason = (
            "Geopolitical tension से global risk sentiment, "
            "crude oil, gold और equity markets में volatility बढ़ सकती है।"
        )

    elif category == "Weather & Disaster":
        reason = (
            "इस घटना से production, transport, crops या supply chain "
            "प्रभावित होने पर commodity और संबंधित stocks में movement आ सकता है।"
        )

    elif category == "Crypto":
        reason = (
            "इस खबर से Bitcoin, Ethereum और crypto-related "
            "assets में volatility बढ़ सकती है।"
        )

    elif category == "Industry":
        reason = (
            "इस development से संबंधित industry, supply chain "
            "और sector companies पर असर पड़ सकता है।"
        )

    else:
        reason = (
            "यह खबर equity market sentiment और संबंधित "
            "sector के stocks को प्रभावित कर सकती है।"
        )

    extra_parts = []

    if country != "India":
        extra_parts.append(
            "Global reaction के जरिए इसका असर भारतीय बाजार, "
            "FII flow और rupee पर भी दिख सकता है।"
        )

    if any(
        term in lowered
        for term in [
            "rate hike",
            "higher interest rate",
            "hawkish",
        ]
    ):
        extra_parts.append(
            "ब्याज दर बढ़ने का संकेत growth और rate-sensitive "
            "stocks पर दबाव बना सकता है।"
        )

    if any(
        term in lowered
        for term in [
            "rate cut",
            "lower interest rate",
            "dovish",
        ]
    ):
        extra_parts.append(
            "Rate cut की उम्मीद liquidity और risk assets "
            "के लिए positive हो सकती है।"
        )

    if importance == "High":
        extra_parts.append(
            "यह high-impact update है, इसलिए market reaction तेज हो सकता है।"
        )

    result = " ".join(
        [reason] + extra_parts
    )

    return truncate_text(
        result,
        520,
    )


# =========================================================
# TRANSLATION
# =========================================================

def translation_cache_key(text):
    return hashlib.sha256(
        str(text or "").encode(
            "utf-8",
            errors="ignore",
        )
    ).hexdigest()


def load_translation_cache():
    global _translation_cache

    try:
        if not os.path.exists(
            TRANSLATION_CACHE_FILE
        ):
            return

        with open(
            TRANSLATION_CACHE_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            payload = json.load(file)

        if isinstance(payload, dict):
            with _translation_lock:
                _translation_cache = payload

    except Exception as error:
        print(
            "TRANSLATION CACHE LOAD ERROR | "
            f"{type(error).__name__}: {error}",
            flush=True,
        )


def save_translation_cache():
    try:
        with _translation_lock:
            payload = dict(
                list(
                    _translation_cache.items()
                )[-1500:]
            )

        directory = os.path.dirname(
            TRANSLATION_CACHE_FILE
        )

        if directory:
            os.makedirs(
                directory,
                exist_ok=True,
            )

        temporary_file = (
            TRANSLATION_CACHE_FILE + ".tmp"
        )

        with open(
            temporary_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                payload,
                file,
                ensure_ascii=False,
            )

        os.replace(
            temporary_file,
            TRANSLATION_CACHE_FILE,
        )

    except Exception as error:
        print(
            "TRANSLATION CACHE SAVE ERROR | "
            f"{type(error).__name__}: {error}",
            flush=True,
        )


def translate_text_to_hindi(text):
    """
    English news को सामान्य Hindi news-channel style में बदलने का प्रयास।

    Translation service fail होने पर application crash नहीं होगा।
    """

    cleaned_text = truncate_text(
        text,
        3200,
    )

    if not cleaned_text:
        return ""

    if is_mostly_hindi(
        cleaned_text
    ):
        return cleaned_text

    cache_key = translation_cache_key(
        cleaned_text
    )

    with _translation_lock:
        cached_value = _translation_cache.get(
            cache_key
        )

    if cached_value:
        return cached_value

    try:
        response = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={
                "client": "gtx",
                "sl": "auto",
                "tl": "hi",
                "dt": "t",
                "q": cleaned_text,
            },
            headers=REQUEST_HEADERS,
            timeout=NEWS_REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        payload = response.json()

        translated_parts = []

        if (
            isinstance(payload, list)
            and payload
            and isinstance(payload[0], list)
        ):
            for item in payload[0]:
                if (
                    isinstance(item, list)
                    and item
                    and item[0]
                ):
                    translated_parts.append(
                        str(item[0])
                    )

        translated_text = clean_html(
            "".join(translated_parts)
        )

        if not translated_text:
            raise ValueError(
                "Empty Hindi translation"
            )

        translated_text = improve_reporter_hindi(
            translated_text
        )

        with _translation_lock:
            _translation_cache[
                cache_key
            ] = translated_text

        return translated_text

    except Exception as error:
        with _cache_lock:
            _status[
                "translation_failures"
            ] = (
                _status.get(
                    "translation_failures",
                    0,
                )
                + 1
            )

        print(
            "TRANSLATION WARNING | "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        return cleaned_text


def improve_reporter_hindi(text):
    """
    बहुत कठिन या robotic wording को थोड़ा सामान्य बनाता है।
    Common market words को news-channel style में रहने देता है।
    """

    result = clean_html(text)

    replacements = {
        "संयुक्त राज्य अमेरिका": "अमेरिका",
        "संघीय रिजर्व": "फेडरल रिजर्व",
        "भारतीय रिजर्व बैंक": "RBI",
        "भारतीय प्रतिभूति और विनिमय बोर्ड": "SEBI",
        "शेयरों": "शेयरों",
        "स्टॉक मार्केट": "शेयर बाजार",
        "कच्चे तेल": "क्रूड ऑयल",
        "सकल घरेलू उत्पाद": "GDP",
        "आरंभिक सार्वजनिक पेशकश": "IPO",
        "अधिग्रहण और विलय": "merger और acquisition",
        "कृत्रिम बुद्धिमत्ता": "AI",
        "बिटकॉइन": "Bitcoin",
        "एथेरियम": "Ethereum",
    }

    for old_value, new_value in replacements.items():
        result = result.replace(
            old_value,
            new_value,
        )

    result = re.sub(
        r"\s+",
        " ",
        result,
    ).strip()

    return result


# =========================================================
# ARTICLE BODY EXTRACTION
# =========================================================

def resolve_google_news_url(url):
    """
    Google News RSS link से final publisher URL प्राप्त करने का प्रयास।
    Fail होने पर original URL लौटता है।
    """

    if not url:
        return ""

    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=NEWS_REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        final_url = response.url

        return final_url or url

    except Exception:
        return url


def extract_full_article_text(url):
    """
    Publisher page से readable article paragraphs निकालने का प्रयास।
    Paywall या blocked site होने पर empty string मिलेगा।
    """

    if not url:
        return ""

    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=NEWS_REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type",
            "",
        ).lower()

        if "html" not in content_type:
            return ""

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        for tag in soup(
            [
                "script",
                "style",
                "nav",
                "header",
                "footer",
                "aside",
                "form",
                "button",
            ]
        ):
            tag.decompose()

        candidate_selectors = [
            "article p",
            "[itemprop='articleBody'] p",
            ".article-body p",
            ".story-body p",
            ".story-content p",
            ".entry-content p",
            ".post-content p",
            ".content-body p",
            "main p",
        ]

        paragraphs = []

        for selector in candidate_selectors:
            selected = soup.select(
                selector
            )

            current_paragraphs = []

            for paragraph in selected:
                text = clean_html(
                    paragraph.get_text(
                        " ",
                        strip=True,
                    )
                )

                if (
                    len(text) >= 60
                    and "cookie" not in text.lower()
                    and "subscribe" not in text.lower()
                ):
                    current_paragraphs.append(
                        text
                    )

            if len(
                " ".join(current_paragraphs)
            ) >= 350:
                paragraphs = current_paragraphs
                break

        if not paragraphs:
            for paragraph in soup.find_all(
                "p"
            ):
                text = clean_html(
                    paragraph.get_text(
                        " ",
                        strip=True,
                    )
                )

                if (
                    70 <= len(text) <= 1200
                    and "cookie" not in text.lower()
                    and "subscribe" not in text.lower()
                    and "sign up" not in text.lower()
                ):
                    paragraphs.append(
                        text
                    )

                if len(
                    " ".join(paragraphs)
                ) >= 4000:
                    break

        full_text = " ".join(
            paragraphs
        )

        return truncate_text(
            full_text,
            4500,
        )

    except Exception:
        return ""


# =========================================================
# HINDI NEWS AND AUDIO TEXT
# =========================================================

def build_hindi_news_text(
    headline,
    description,
    full_text,
):
    body_source = (
        full_text
        or description
        or headline
    )

    hindi_headline = translate_text_to_hindi(
        headline
    )

    hindi_body = translate_text_to_hindi(
        body_source
    )

    if normalize_title(
        hindi_headline
    ) == normalize_title(
        hindi_body
    ):
        return truncate_text(
            hindi_body,
            3400,
        )

    if hindi_body:
        return truncate_text(
            f"{hindi_headline}। {hindi_body}",
            3400,
        )

    return truncate_text(
        hindi_headline,
        3400,
    )


def build_audio_text_hi(
    headline_hi,
    full_news_hi,
    market_reason_hi,
):
    """
    Audio में कोई label नहीं जोड़ा जाएगा।

    Dashboard JavaScript नई खबर होने पर:
    'ब्रेकिंग न्यूज़' और खबरों के बीच
    'अगली खबर' जोड़ेगा।
    """

    parts = []

    cleaned_headline = clean_html(
        headline_hi
    )

    cleaned_news = clean_html(
        full_news_hi
    )

    cleaned_reason = clean_html(
        market_reason_hi
    )

    if cleaned_headline:
        parts.append(
            cleaned_headline
        )

    if (
        cleaned_news
        and normalize_title(
            cleaned_news
        ) != normalize_title(
            cleaned_headline
        )
    ):
        parts.append(
            cleaned_news
        )

    if cleaned_reason:
        parts.append(
            cleaned_reason
        )

    audio_text = "। ".join(
        part.rstrip(
            ".। "
        )
        for part in parts
        if part
    )

    return truncate_text(
        audio_text + "।",
        3600,
    )


# =========================================================
# FEED PARSING
# =========================================================

def get_feed_entry_source(entry):
    source = ""

    entry_source = entry.get(
        "source"
    )

    if isinstance(
        entry_source,
        dict,
    ):
        source = clean_html(
            entry_source.get(
                "title",
                "",
            )
        )

    if not source:
        source = clean_html(
            entry.get(
                "author",
                "",
            )
        )

    return source or "News Source"


def get_feed_entry_description(entry):
    candidates = [
        entry.get(
            "summary",
            "",
        ),
        entry.get(
            "description",
            "",
        ),
    ]

    content = entry.get(
        "content",
        [],
    )

    if isinstance(
        content,
        list,
    ):
        for item in content:
            if isinstance(
                item,
                dict,
            ):
                candidates.append(
                    item.get(
                        "value",
                        "",
                    )
                )

    for candidate in candidates:
        cleaned = clean_html(
            candidate
        )

        if cleaned:
            return cleaned

    return ""


def parse_single_entry(entry):
    raw_title = clean_html(
        entry.get(
            "title",
            "",
        )
    )

    headline = remove_source_from_google_title(
        raw_title
    )

    if not headline:
        return None

    description = get_feed_entry_description(
        entry
    )

    if not is_market_relevant(
        headline,
        description,
    ):
        return None

    original_url = clean_html(
        entry.get(
            "link",
            "",
        )
    )

    source = get_feed_entry_source(
        entry
    )

    published_raw = (
        entry.get(
            "published",
            ""
        )
        or entry.get(
            "updated",
            ""
        )
    )

    published_at = date_to_iso(
        published_raw
    )

    combined_text = (
        f"{headline} {description}"
    )

    category = detect_category(
        combined_text
    )

    country = detect_country(
        combined_text
    )

    importance = detect_importance(
        headline,
        description,
    )

    direction = detect_market_direction(
        headline,
        description,
    )

    market_reason_hi = build_market_reason(
        category=category,
        country=country,
        direction=direction,
        importance=importance,
        text=combined_text,
    )

    article_id = make_article_id(
        title=headline,
        url=original_url,
        published_at=published_at,
    )

    article = {
        "id": article_id,

        # Main dashboard fields
        "headline": headline,
        "title": headline,
        "market_impact": direction,
        "impact": direction,
        "importance": importance,
        "market_reason_hi": market_reason_hi,
        "market_effect_hi": market_reason_hi,

        # News details
        "summary": truncate_text(
            description or headline,
            900,
        ),
        "full_news": truncate_text(
            description or headline,
            2200,
        ),
        "full_news_hi": "",
        "detail_hi": "",

        # Hindi audio fields
        "headline_hi": "",
        "audio_text_hi": "",

        # Metadata
        "country": country,
        "region": country,
        "category": category,
        "source": source,
        "url": original_url,
        "original_url": original_url,
        "published_at": published_at,
        "fetched_at": utc_now_iso(),
        "is_breaking": (
            importance == "High"
            and is_recent_breaking_news(
                published_at
            )
        ),

        # Compatibility with older dashboard
        "important_points": [],
        "summary_hi": "",
    }

    return article


def enrich_article(article):
    """
    Full article और Hindi audio तैयार करता है।
    किसी एक article की failure से बाकी refresh नहीं रुकेगा।
    """

    try:
        original_url = article.get(
            "url",
            "",
        )

        resolved_url = resolve_google_news_url(
            original_url
        )

        full_text = extract_full_article_text(
            resolved_url
        )

        description = article.get(
            "summary",
            "",
        )

        if not full_text:
            full_text = (
                description
                or article.get(
                    "headline",
                    "",
                )
            )

        full_text = truncate_text(
            full_text,
            4500,
        )

        headline_hi = translate_text_to_hindi(
            article.get(
                "headline",
                "",
            )
        )

        full_news_hi = build_hindi_news_text(
            headline=article.get(
                "headline",
                "",
            ),
            description=description,
            full_text=full_text,
        )

        article[
            "url"
        ] = resolved_url or original_url

        article[
            "full_news"
        ] = full_text

        article[
            "headline_hi"
        ] = headline_hi

        article[
            "full_news_hi"
        ] = full_news_hi

        article[
            "summary_hi"
        ] = truncate_text(
            full_news_hi,
            800,
        )

        article[
            "detail_hi"
        ] = full_news_hi

        article[
            "audio_text_hi"
        ] = build_audio_text_hi(
            headline_hi=headline_hi,
            full_news_hi=full_news_hi,
            market_reason_hi=article.get(
                "market_reason_hi",
                "",
            ),
        )

        # पुरानी compatibility field को खाली नहीं छोड़ा गया।
        article[
            "important_points"
        ] = [
            article.get(
                "market_reason_hi",
                "",
            )
        ]

        return article

    except Exception as error:
        print(
            "ARTICLE ENRICH WARNING | "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        fallback_headline = article.get(
            "headline",
            "",
        )

        fallback_news = article.get(
            "summary",
            "",
        )

        article[
            "headline_hi"
        ] = translate_text_to_hindi(
            fallback_headline
        )

        article[
            "full_news_hi"
        ] = translate_text_to_hindi(
            fallback_news
            or fallback_headline
        )

        article[
            "summary_hi"
        ] = truncate_text(
            article.get(
                "full_news_hi",
                "",
            ),
            800,
        )

        article[
            "detail_hi"
        ] = article.get(
            "full_news_hi",
            "",
        )

        article[
            "audio_text_hi"
        ] = build_audio_text_hi(
            headline_hi=article.get(
                "headline_hi",
                "",
            ),
            full_news_hi=article.get(
                "full_news_hi",
                "",
            ),
            market_reason_hi=article.get(
                "market_reason_hi",
                "",
            ),
        )

        return article


def parse_feed(feed_url):
    response = requests.get(
        feed_url,
        headers=REQUEST_HEADERS,
        timeout=NEWS_REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    parsed_feed = feedparser.parse(
        response.content
    )

    articles = []

    for entry in parsed_feed.entries:
        try:
            article = parse_single_entry(
                entry
            )

            if article:
                articles.append(
                    article
                )

        except Exception as error:
            print(
                "ENTRY PARSE WARNING | "
                f"{type(error).__name__}: {error}",
                flush=True,
            )

        if len(
            articles
        ) >= MAX_ARTICLES_PER_FEED:
            break

    return articles


# =========================================================
# DEDUPLICATION AND SORTING
# =========================================================

def deduplicate_articles(articles):
    unique_articles = []
    seen_ids = set()
    seen_titles = set()

    sorted_articles = sorted(
        articles,
        key=article_timestamp,
        reverse=True,
    )

    for article in sorted_articles:
        article_id = str(
            article.get(
                "id",
                "",
            )
        )

        normalized_title = normalize_title(
            article.get(
                "headline",
                "",
            )
        )

        if not normalized_title:
            continue

        title_words = normalized_title.split()

        title_signature = " ".join(
            title_words[:15]
        )

        if (
            article_id
            and article_id in seen_ids
        ):
            continue

        if (
            title_signature
            and title_signature in seen_titles
        ):
            continue

        if article_id:
            seen_ids.add(
                article_id
            )

        if title_signature:
            seen_titles.add(
                title_signature
            )

        unique_articles.append(
            article
        )

        if len(
            unique_articles
        ) >= MAX_CACHE_NEWS:
            break

    return unique_articles


def should_enrich_article(article, existing_ids):
    article_id = article.get(
        "id",
        "",
    )

    if article_id in existing_ids:
        return False

    importance = article.get(
        "importance",
        "Low",
    )

    return importance in {
        "High",
        "Medium",
    }


# =========================================================
# CACHE STORAGE
# =========================================================

def save_cache_to_disk(articles):
    try:
        directory = os.path.dirname(
            CACHE_FILE
        )

        if directory:
            os.makedirs(
                directory,
                exist_ok=True,
            )

        temporary_file = (
            CACHE_FILE + ".tmp"
        )

        payload = {
            "saved_at": utc_now_iso(),
            "news": articles,
        }

        with open(
            temporary_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                payload,
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temporary_file,
            CACHE_FILE,
        )

    except Exception as error:
        print(
            "CACHE SAVE ERROR | "
            f"{type(error).__name__}: {error}",
            flush=True,
        )


def load_cache_from_disk():
    global _news_cache

    try:
        if not os.path.exists(
            CACHE_FILE
        ):
            return

        with open(
            CACHE_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            payload = json.load(file)

        articles = payload.get(
            "news",
            [],
        )

        if not isinstance(
            articles,
            list,
        ):
            return

        articles = deduplicate_articles(
            articles
        )

        with _cache_lock:
            _news_cache = articles

            _status[
                "cached_count"
            ] = len(
                _news_cache
            )

            _status[
                "last_updated"
            ] = (
                payload.get(
                    "saved_at"
                )
                or utc_now_iso()
            )

        print(
            "NEWS CACHE LOADED | "
            f"{len(articles)} articles",
            flush=True,
        )

    except Exception as error:
        print(
            "CACHE LOAD ERROR | "
            f"{type(error).__name__}: {error}",
            flush=True,
        )


def merge_with_existing_cache(
    fetched_articles,
):
    with _cache_lock:
        combined = (
            list(fetched_articles)
            + list(_news_cache)
        )

    return deduplicate_articles(
        combined
    )


# =========================================================
# PUBLIC FUNCTIONS USED BY APP.PY
# =========================================================

def get_cached_news(limit=None):
    with _cache_lock:
        articles = list(
            _news_cache
        )

    articles.sort(
        key=article_timestamp,
        reverse=True,
    )

    if limit is None:
        return articles

    try:
        safe_limit = max(
            1,
            min(
                int(limit),
                MAX_CACHE_NEWS,
            ),
        )

    except (
        TypeError,
        ValueError,
    ):
        safe_limit = MAX_CACHE_NEWS

    return articles[
        :safe_limit
    ]


def get_news_status():
    with _cache_lock:
        return dict(
            _status
        )


def get_news_by_id(article_id):
    if not article_id:
        return None

    with _cache_lock:
        for article in _news_cache:
            if str(
                article.get(
                    "id",
                    "",
                )
            ) == str(
                article_id
            ):
                return dict(
                    article
                )

    return None


# =========================================================
# NEWS REFRESH
# =========================================================

def perform_news_refresh():
    global _news_cache

    if not _refresh_lock.acquire(
        blocking=False
    ):
        return False

    with _cache_lock:
        _status[
            "refresh_running"
        ] = True

        _status[
            "last_error"
        ] = None

        existing_ids = {
            article.get(
                "id",
                "",
            )
            for article in _news_cache
        }

    try:
        feeds = get_configured_feeds()

        all_articles = []
        feed_errors = []

        worker_count = min(
            MAX_PARALLEL_FEEDS,
            max(
                1,
                len(feeds),
            ),
        )

        with ThreadPoolExecutor(
            max_workers=worker_count
        ) as executor:

            future_map = {
                executor.submit(
                    parse_feed,
                    feed_url,
                ): feed_url
                for feed_url in feeds
            }

            for future in as_completed(
                future_map
            ):
                feed_url = future_map[
                    future
                ]

                try:
                    articles = future.result()

                    all_articles.extend(
                        articles
                    )

                except Exception as error:
                    feed_errors.append(
                        (
                            f"{feed_url[:80]} | "
                            f"{type(error).__name__}: "
                            f"{error}"
                        )
                    )

        all_articles = deduplicate_articles(
            all_articles
        )

        new_articles = [
            article
            for article in all_articles
            if article.get(
                "id",
                "",
            ) not in existing_ids
        ]

        # Server load नियंत्रित रखने के लिए एक refresh में
        # केवल सबसे जरूरी नई खबरें enrich होंगी।
        articles_to_enrich = [
            article
            for article in new_articles
            if should_enrich_article(
                article,
                existing_ids,
            )
        ][:20]

        if articles_to_enrich:
            translation_workers = min(
                MAX_TRANSLATION_WORKERS,
                len(
                    articles_to_enrich
                ),
            )

            with ThreadPoolExecutor(
                max_workers=max(
                    1,
                    translation_workers,
                )
            ) as executor:

                enrichment_map = {
                    executor.submit(
                        enrich_article,
                        article,
                    ): article.get(
                        "id",
                        "",
                    )
                    for article in articles_to_enrich
                }

                enriched_by_id = {}

                for future in as_completed(
                    enrichment_map
                ):
                    article_id = enrichment_map[
                        future
                    ]

                    try:
                        enriched_by_id[
                            article_id
                        ] = future.result()

                    except Exception as error:
                        print(
                            "ENRICHMENT WARNING | "
                            f"{type(error).__name__}: {error}",
                            flush=True,
                        )

                all_articles = [
                    enriched_by_id.get(
                        article.get(
                            "id",
                            "",
                        ),
                        article,
                    )
                    for article in all_articles
                ]

        # Low-impact articles और enrichment fail होने पर भी
        # basic Hindi audio fields जरूर बनेंगे।
        prepared_articles = []

        for article in all_articles:
            if not article.get(
                "headline_hi"
            ):
                article[
                    "headline_hi"
                ] = translate_text_to_hindi(
                    article.get(
                        "headline",
                        "",
                    )
                )

            if not article.get(
                "full_news_hi"
            ):
                article[
                    "full_news_hi"
                ] = translate_text_to_hindi(
                    article.get(
                        "full_news",
                        ""
                    )
                    or article.get(
                        "summary",
                        ""
                    )
                    or article.get(
                        "headline",
                        "",
                    )
                )

            if not article.get(
                "audio_text_hi"
            ):
                article[
                    "audio_text_hi"
                ] = build_audio_text_hi(
                    headline_hi=article.get(
                        "headline_hi",
                        "",
                    ),
                    full_news_hi=article.get(
                        "full_news_hi",
                        "",
                    ),
                    market_reason_hi=article.get(
                        "market_reason_hi",
                        "",
                    ),
                )

            article[
                "summary_hi"
            ] = truncate_text(
                article.get(
                    "full_news_hi",
                    "",
                ),
                800,
            )

            article[
                "detail_hi"
            ] = article.get(
                "full_news_hi",
                "",
            )

            prepared_articles.append(
                article
            )

        merged_articles = merge_with_existing_cache(
            prepared_articles
        )

        current_time = utc_now_iso()

        with _cache_lock:
            _news_cache = merged_articles

            _status[
                "last_updated"
            ] = current_time

            _status[
                "last_success"
            ] = current_time

            _status[
                "last_fetch_count"
            ] = len(
                all_articles
            )

            _status[
                "cached_count"
            ] = len(
                _news_cache
            )

            if feed_errors:
                _status[
                    "last_error"
                ] = (
                    f"{len(feed_errors)} feeds failed; "
                    "other feeds updated successfully."
                )
            else:
                _status[
                    "last_error"
                ] = None

        save_cache_to_disk(
            merged_articles
        )

        save_translation_cache()

        print(
            "NEWS REFRESH SUCCESS | "
            f"Fetched: {len(all_articles)} | "
            f"New: {len(new_articles)} | "
            f"Cached: {len(merged_articles)} | "
            f"Feed errors: {len(feed_errors)}",
            flush=True,
        )

        return True

    except Exception as error:
        error_message = (
            f"{type(error).__name__}: {error}"
        )

        with _cache_lock:
            _status[
                "last_error"
            ] = error_message

        print(
            "NEWS REFRESH FAILED | "
            f"{error_message}",
            flush=True,
        )

        return False

    finally:
        with _cache_lock:
            _status[
                "refresh_running"
            ] = False

        _refresh_lock.release()


def refresh_news_now(
    run_in_background=True,
):
    """
    True:
    API तुरंत response देगी और refresh background में चलेगा।

    False:
    Refresh current request/thread में पूरा होगा।
    """

    with _cache_lock:
        refresh_running = _status.get(
            "refresh_running",
            False,
        )

    if refresh_running:
        return False

    if run_in_background:
        thread = threading.Thread(
            target=perform_news_refresh,
            name="manual-news-refresh",
            daemon=True,
        )

        thread.start()

        return True

    return perform_news_refresh()


# =========================================================
# BACKGROUND AUTO-UPDATER
# =========================================================

def updater_loop():
    with _cache_lock:
        _status[
            "updater_running"
        ] = True

    try:
        perform_news_refresh()

        while not _stop_event.wait(
            max(
                30,
                NEWS_UPDATE_INTERVAL,
            )
        ):
            perform_news_refresh()

    finally:
        with _cache_lock:
            _status[
                "updater_running"
            ] = False


def start_news_updater():
    global _updater_thread

    with _updater_lock:
        if (
            _updater_thread is not None
            and _updater_thread.is_alive()
        ):
            return False

        _stop_event.clear()

        _updater_thread = threading.Thread(
            target=updater_loop,
            name="golden-ai-news-updater",
            daemon=True,
        )

        _updater_thread.start()

        return True


def stop_news_updater():
    _stop_event.set()


# =========================================================
# INITIAL LOAD
# =========================================================

load_translation_cache()
load_cache_from_disk()
