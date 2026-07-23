import hashlib
import html
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


# =========================================================
# SETTINGS
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
    os.environ.get("MAX_ARTICLES_PER_FEED", "35")
)

MAX_PARALLEL_FEEDS = int(
    os.environ.get("MAX_PARALLEL_FEEDS", "6")
)

CACHE_FILE = os.environ.get(
    "NEWS_CACHE_FILE",
    "/tmp/golden_ai_news_cache.json"
)

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13) "
    "AppleWebKit/537.36 "
    "Chrome/125.0 Mobile Safari/537.36"
)


# =========================================================
# MARKET NEWS SEARCH QUERIES
# =========================================================

MARKET_SEARCH_QUERIES = [
    (
        "India stock market RBI inflation interest rates "
        "Sensex Nifty rupee economy"
    ),
    (
        "global stock markets Federal Reserve inflation "
        "interest rates recession economy"
    ),
    (
        "Asian markets China Japan Hong Kong Korea economy "
        "central bank"
    ),
    (
        "crude oil OPEC natural gas commodities market"
    ),
    (
        "gold silver precious metals market dollar yields"
    ),
    (
        "Bitcoin Ethereum crypto market regulation ETF"
    ),
    (
        "geopolitical war sanctions tariffs trade market impact"
    ),
    (
        "major company earnings merger acquisition bankruptcy "
        "stock market"
    ),
]


def build_google_news_feed(query):
    encoded_query = urllib.parse.quote_plus(
        query + " when:1d"
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
    Optional environment variable:

    NEWS_RSS_FEEDS=url1,url2,url3

    अगर environment variable मौजूद नहीं है तो default
    Google News market queries उपयोग होंगी।
    """

    configured = os.environ.get(
        "NEWS_RSS_FEEDS",
        ""
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
# GLOBAL CACHE AND STATUS
# =========================================================

_cache_lock = threading.RLock()
_refresh_lock = threading.Lock()
_updater_lock = threading.Lock()

_news_cache = []

_status = {
    "last_updated": None,
    "last_success": None,
    "last_error": None,
    "updater_running": False,
    "refresh_running": False,
    "last_fetch_count": 0,
    "cached_count": 0,
}

_updater_thread = None
_stop_event = threading.Event()


# =========================================================
# MARKET KEYWORDS
# =========================================================

STRONG_MARKET_KEYWORDS = {
    "stock market",
    "stocks",
    "shares",
    "nifty",
    "sensex",
    "bank nifty",
    "dow jones",
    "nasdaq",
    "s&p 500",
    "nikkei",
    "hang seng",
    "ftse",
    "dax",
    "market rally",
    "market crash",
    "market falls",
    "market rises",
    "bull market",
    "bear market",
    "equity market",
    "wall street",
    "dalal street",
}

ECONOMY_KEYWORDS = {
    "inflation",
    "interest rate",
    "rate cut",
    "rate hike",
    "central bank",
    "federal reserve",
    "fed",
    "rbi",
    "ecb",
    "bank of japan",
    "bank of england",
    "gdp",
    "recession",
    "economy",
    "economic growth",
    "jobs report",
    "unemployment",
    "cpi",
    "ppi",
    "retail sales",
    "manufacturing",
    "pmi",
    "fiscal deficit",
    "budget",
    "tax",
    "tariff",
    "trade war",
    "stimulus",
    "bond yields",
    "treasury yields",
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
}

COMMODITY_KEYWORDS = {
    "crude oil",
    "brent",
    "wti",
    "opec",
    "natural gas",
    "gold",
    "silver",
    "copper",
    "commodity",
    "commodities",
    "oil prices",
    "metal prices",
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
    "sanctions",
    "geopolitical",
    "ceasefire",
    "border conflict",
    "trade sanctions",
    "shipping disruption",
    "red sea",
    "strait of hormuz",
}

COMPANY_KEYWORDS = {
    "earnings",
    "quarterly results",
    "profit",
    "revenue",
    "merger",
    "acquisition",
    "bankruptcy",
    "default",
    "ipo",
    "buyback",
    "dividend",
    "guidance",
    "layoffs",
    "regulatory approval",
}

EXCLUDED_KEYWORDS = {
    "movie",
    "film",
    "actor",
    "actress",
    "celebrity",
    "cricket",
    "football",
    "tennis",
    "sports",
    "fashion",
    "recipe",
    "relationship",
    "horoscope",
    "astrology",
    "wedding",
    "viral video",
}


# =========================================================
# TEXT HELPERS
# =========================================================

def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


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

    return text[:limit].rsplit(" ", 1)[0] + "..."


def split_sentences(value):
    text = clean_html(value)

    if not text:
        return []

    parts = re.split(
        r"(?<=[.!?।])\s+",
        text,
    )

    return [
        item.strip()
        for item in parts
        if len(item.strip()) >= 20
    ]


def make_article_id(title, url, published_at):
    raw_value = (
        f"{normalize_title(title)}|"
        f"{url.strip()}|"
        f"{published_at.strip()}"
    )

    return hashlib.sha256(
        raw_value.encode("utf-8", errors="ignore")
    ).hexdigest()[:24]


# =========================================================
# DATE HELPERS
# =========================================================

def parse_date(value):
    if not value:
        return datetime.now(timezone.utc)

    raw_value = str(value).strip()

    try:
        parsed = parsedate_to_datetime(raw_value)

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(timezone.utc)

    except Exception:
        pass

    iso_value = raw_value.replace(
        "Z",
        "+00:00"
    )

    try:
        parsed = datetime.fromisoformat(iso_value)

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(timezone.utc)

    except Exception:
        return datetime.now(timezone.utc)


def date_to_iso(value):
    return parse_date(value).isoformat()


def article_timestamp(article):
    published_at = article.get(
        "published_at",
        ""
    )

    return parse_date(
        published_at
    ).timestamp()


# =========================================================
# XML HELPERS
# =========================================================

def local_tag(element):
    return element.tag.split("}")[-1].lower()


def find_child_text(element, possible_names):
    names = {
        item.lower()
        for item in possible_names
    }

    for child in list(element):
        if local_tag(child) in names:
            if child.text:
                return child.text.strip()

    return ""


def find_link(element):
    for child in list(element):
        if local_tag(child) != "link":
            continue

        href = child.attrib.get("href")

        if href:
            return href.strip()

        if child.text:
            return child.text.strip()

    return ""


def find_source(element):
    for child in list(element):
        if local_tag(child) != "source":
            continue

        if child.text:
            return clean_html(child.text)

        title = child.attrib.get("title")

        if title:
            return clean_html(title)

    return ""


# =========================================================
# MARKET FILTERING
# =========================================================

def keyword_matches(text, keywords):
    lowered = text.lower()

    return [
        keyword
        for keyword in keywords
        if keyword in lowered
    ]


def calculate_relevance_score(title, description):
    combined = (
        f"{title} {description}"
    ).lower()

    if keyword_matches(
        combined,
        EXCLUDED_KEYWORDS
    ):
        return -10

    score = 0

    strong_matches = keyword_matches(
        combined,
        STRONG_MARKET_KEYWORDS
    )

    economy_matches = keyword_matches(
        combined,
        ECONOMY_KEYWORDS
    )

    currency_matches = keyword_matches(
        combined,
        CURRENCY_KEYWORDS
    )

    commodity_matches = keyword_matches(
        combined,
        COMMODITY_KEYWORDS
    )

    crypto_matches = keyword_matches(
        combined,
        CRYPTO_KEYWORDS
    )

    geopolitical_matches = keyword_matches(
        combined,
        GEOPOLITICAL_KEYWORDS
    )

    company_matches = keyword_matches(
        combined,
        COMPANY_KEYWORDS
    )

    score += len(strong_matches) * 4
    score += len(economy_matches) * 3
    score += len(currency_matches) * 3
    score += len(commodity_matches) * 3
    score += len(crypto_matches) * 3
    score += len(geopolitical_matches) * 2
    score += len(company_matches) * 2

    title_lower = title.lower()

    if keyword_matches(
        title_lower,
        STRONG_MARKET_KEYWORDS
    ):
        score += 5

    if keyword_matches(
        title_lower,
        ECONOMY_KEYWORDS
    ):
        score += 4

    if keyword_matches(
        title_lower,
        COMMODITY_KEYWORDS
    ):
        score += 4

    if keyword_matches(
        title_lower,
        CRYPTO_KEYWORDS
    ):
        score += 4

    return score


def is_market_relevant(title, description):
    return calculate_relevance_score(
        title,
        description
    ) >= 3


# =========================================================
# CATEGORY, COUNTRY AND IMPACT
# =========================================================

def detect_category(text):
    lowered = text.lower()

    if keyword_matches(
        lowered,
        CRYPTO_KEYWORDS
    ):
        return "Crypto"

    if any(
        keyword in lowered
        for keyword in [
            "gold",
            "silver",
            "precious metal",
        ]
    ):
        return "Gold & Silver"

    if any(
        keyword in lowered
        for keyword in [
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
        CURRENCY_KEYWORDS
    ):
        return "Currency"

    if keyword_matches(
        lowered,
        ECONOMY_KEYWORDS
    ):
        return "Economy"

    if keyword_matches(
        lowered,
        GEOPOLITICAL_KEYWORDS
    ):
        return "Geopolitics"

    if keyword_matches(
        lowered,
        COMPANY_KEYWORDS
    ):
        return "Corporate"

    return "Stock Market"


def detect_country(text):
    lowered = text.lower()

    country_rules = [
        (
            "India",
            [
                "india",
                "indian",
                "rbi",
                "nifty",
                "sensex",
                "rupee",
                "sebi",
                "mumbai",
                "new delhi",
            ],
        ),
        (
            "USA",
            [
                "united states",
                "u.s.",
                " us ",
                "federal reserve",
                "wall street",
                "nasdaq",
                "dow jones",
                "s&p 500",
                "washington",
            ],
        ),
        (
            "China",
            [
                "china",
                "chinese",
                "beijing",
                "shanghai",
                "yuan",
                "people's bank of china",
            ],
        ),
        (
            "Japan",
            [
                "japan",
                "japanese",
                "tokyo",
                "nikkei",
                "bank of japan",
                "yen",
            ],
        ),
        (
            "Europe",
            [
                "europe",
                "european union",
                "eurozone",
                "ecb",
                "germany",
                "france",
                "italy",
                "euro",
            ],
        ),
        (
            "United Kingdom",
            [
                "united kingdom",
                "britain",
                "british",
                "bank of england",
                "london",
                "ftse",
                "pound",
            ],
        ),
        (
            "Middle East",
            [
                "middle east",
                "iran",
                "israel",
                "saudi arabia",
                "uae",
                "qatar",
                "red sea",
                "strait of hormuz",
            ],
        ),
        (
            "Russia",
            [
                "russia",
                "russian",
                "moscow",
            ],
        ),
        (
            "South Korea",
            [
                "south korea",
                "korean",
                "seoul",
                "kospi",
            ],
        ),
        (
            "Hong Kong",
            [
                "hong kong",
                "hang seng",
            ],
        ),
    ]

    padded_text = f" {lowered} "

    for country, keywords in country_rules:
        if any(
            keyword in padded_text
            for keyword in keywords
        ):
            return country

    return "Global"


def detect_impact(title, description):
    combined = (
        f"{title} {description}"
    ).lower()

    score = calculate_relevance_score(
        title,
        description
    )

    high_impact_terms = [
        "emergency rate cut",
        "unexpected rate hike",
        "unexpected rate cut",
        "market crash",
        "trading halt",
        "bankruptcy",
        "sovereign default",
        "war begins",
        "military attack",
        "missile attack",
        "major sanctions",
        "oil supply disruption",
        "recession confirmed",
        "financial crisis",
        "currency crisis",
        "record inflation",
        "central bank decision",
        "federal reserve decision",
        "rbi policy",
    ]

    if any(
        term in combined
        for term in high_impact_terms
    ):
        return "High"

    if score >= 13:
        return "High"

    if score >= 6:
        return "Medium"

    return "Low"


# =========================================================
# IMPORTANT POINTS AND HINDI DETAILS
# =========================================================

def build_important_points(
    title,
    description,
    category,
    country,
    impact,
):
    points = []

    description_sentences = split_sentences(
        description
    )

    for sentence in description_sentences:
        clean_sentence = truncate_text(
            sentence,
            240
        )

        if (
            clean_sentence
            and clean_sentence not in points
        ):
            points.append(clean_sentence)

        if len(points) >= 3:
            break

    if not points:
        points.append(
            truncate_text(
                title,
                240
            )
        )

    points.append(
        f"Region: {country} | "
        f"Category: {category}"
    )

    points.append(
        f"Potential market impact: {impact}"
    )

    return points[:5]


def build_market_effect_hi(
    category,
    country,
    impact,
    text,
):
    lowered = text.lower()

    effect_parts = []

    if category == "Crypto":
        effect_parts.append(
            "इस खबर से Bitcoin, Ethereum और "
            "दूसरी crypto assets में volatility बढ़ सकती है।"
        )

    elif category == "Gold & Silver":
        effect_parts.append(
            "इसका असर gold, silver, dollar और "
            "bond yields से जुड़े trades पर पड़ सकता है।"
        )

    elif category == "Energy":
        effect_parts.append(
            "Crude oil और energy prices में बदलाव से "
            "inflation, currency और oil-dependent कंपनियों "
            "पर प्रभाव पड़ सकता है।"
        )

    elif category == "Currency":
        effect_parts.append(
            "Currency movement का असर import-export, "
            "IT, banking और commodity prices पर पड़ सकता है।"
        )

    elif category == "Economy":
        effect_parts.append(
            "Economic data और interest-rate expectations "
            "से equity, bond और currency markets प्रभावित "
            "हो सकते हैं।"
        )

    elif category == "Geopolitics":
        effect_parts.append(
            "Geopolitical uncertainty से risk sentiment, "
            "crude oil, gold और global equity markets में "
            "तेज उतार-चढ़ाव आ सकता है।"
        )

    elif category == "Corporate":
        effect_parts.append(
            "इस corporate development का असर संबंधित "
            "company, sector और peer stocks पर पड़ सकता है।"
        )

    else:
        effect_parts.append(
            "यह खबर equity market sentiment और संबंधित "
            "sector के stocks को प्रभावित कर सकती है।"
        )

    if country != "India":
        effect_parts.append(
            "Global market reaction के माध्यम से इसका असर "
            "भारतीय बाजार के opening trend, FII flows, "
            "rupee और sectoral movement पर भी पड़ सकता है।"
        )

    if any(
        keyword in lowered
        for keyword in [
            "rate hike",
            "higher interest rate",
            "hawkish",
        ]
    ):
        effect_parts.append(
            "ब्याज दर बढ़ने की आशंका growth stocks और "
            "rate-sensitive sectors पर दबाव बना सकती है।"
        )

    if any(
        keyword in lowered
        for keyword in [
            "rate cut",
            "lower interest rate",
            "dovish",
        ]
    ):
        effect_parts.append(
            "ब्याज दर घटने की उम्मीद liquidity और "
            "risk assets के लिए सकारात्मक हो सकती है।"
        )

    if impact == "High":
        effect_parts.append(
            "इसे High Impact update माना गया है, इसलिए "
            "trade लेने से पहले price confirmation और "
            "risk management जरूरी है।"
        )

    elif impact == "Medium":
        effect_parts.append(
            "इसे Medium Impact update माना गया है। "
            "Market reaction की पुष्टि price और volume "
            "से करनी चाहिए।"
        )

    return " ".join(effect_parts)


def build_detail_hi(
    title,
    description,
    country,
    category,
    impact,
    source,
    market_effect_hi,
):
    cleaned_description = truncate_text(
        description,
        1400
    )

    detail_parts = [
        f"यह खबर {country} से संबंधित है।",
        f"यह {category} category की खबर है।",
        f"इसका संभावित market impact {impact} है।",
        f"खबर की headline है: {title}।",
    ]

    if cleaned_description:
        detail_parts.append(
            "खबर में उपलब्ध जानकारी के अनुसार: "
            f"{cleaned_description}"
        )

    if market_effect_hi:
        detail_parts.append(
            "बाजार पर संभावित असर: "
            f"{market_effect_hi}"
        )

    if source:
        detail_parts.append(
            f"इस खबर का source {source} है।"
        )

    return " ".join(detail_parts)


def build_audio_text_hi(article):
    important_points = article.get(
        "important_points",
        []
    )

    spoken_points = []

    for index, point in enumerate(
        important_points[:3],
        start=1,
    ):
        spoken_points.append(
            f"मुख्य बिंदु {index}: {point}।"
        )

    parts = [
        (
            f"यह खबर {article.get('country', 'Global')} "
            "से संबंधित है।"
        ),
        (
            f"श्रेणी {article.get('category', 'Market')}।"
        ),
        (
            f"मार्केट प्रभाव "
            f"{article.get('impact', 'Medium')}।"
        ),
        (
            f"हेडलाइन: "
            f"{article.get('headline', '')}।"
        ),
    ]

    parts.extend(spoken_points)

    detail_hi = article.get(
        "detail_hi",
        ""
    )

    if detail_hi:
        parts.append(
            f"विस्तृत जानकारी: {detail_hi}"
        )

    market_effect = article.get(
        "market_effect_hi",
        ""
    )

    if market_effect:
        parts.append(
            f"बाजार पर संभावित असर: {market_effect}"
        )

    return " ".join(
        item
        for item in parts
        if item
    )


# =========================================================
# RSS FETCHING
# =========================================================

def fetch_url(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/rss+xml,"
                "application/xml,"
                "text/xml,"
                "*/*"
            ),
            "Accept-Language": "en-IN,en;q=0.9",
            "Cache-Control": "no-cache",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=NEWS_REQUEST_TIMEOUT,
    ) as response:
        return response.read()


def parse_feed(feed_url):
    raw_xml = fetch_url(feed_url)

    root = ET.fromstring(raw_xml)

    feed_articles = []

    for element in root.iter():
        element_name = local_tag(element)

        if element_name not in {
            "item",
            "entry",
        }:
            continue

        title = clean_html(
            find_child_text(
                element,
                ["title"],
            )
        )

        if not title:
            continue

        description = clean_html(
            find_child_text(
                element,
                [
                    "description",
                    "summary",
                    "content",
                    "encoded",
                ],
            )
        )

        url = find_link(element)

        published_raw = find_child_text(
            element,
            [
                "pubdate",
                "published",
                "updated",
                "date",
            ],
        )

        source = find_source(element)

        if not source:
            source = clean_html(
                find_child_text(
                    element,
                    ["author", "creator"],
                )
            )

        if not source:
            source = "News Source"

        if not is_market_relevant(
            title,
            description,
        ):
            continue

        combined_text = (
            f"{title} {description}"
        )

        category = detect_category(
            combined_text
        )

        country = detect_country(
            combined_text
        )

        impact = detect_impact(
            title,
            description,
        )

        published_at = date_to_iso(
            published_raw
        )

        market_effect_hi = (
            build_market_effect_hi(
                category=category,
                country=country,
                impact=impact,
                text=combined_text,
            )
        )

        important_points = (
            build_important_points(
                title=title,
                description=description,
                category=category,
                country=country,
                impact=impact,
            )
        )

        detail_hi = build_detail_hi(
            title=title,
            description=description,
            country=country,
            category=category,
            impact=impact,
            source=source,
            market_effect_hi=market_effect_hi,
        )

        article = {
            "headline": title,
            "title": title,
            "country": country,
            "region": country,
            "category": category,
            "impact": impact,
            "important_points": important_points,
            "summary_hi": truncate_text(
                description or title,
                650
            ),
            "detail_hi": detail_hi,
            "market_effect_hi": market_effect_hi,
            "source": source,
            "url": url,
            "published_at": published_at,
            "fetched_at": utc_now_iso(),
        }

        article["id"] = make_article_id(
            title=title,
            url=url,
            published_at=published_at,
        )

        article["audio_text_hi"] = (
            build_audio_text_hi(article)
        )

        feed_articles.append(article)

        if (
            len(feed_articles)
            >= MAX_ARTICLES_PER_FEED
        ):
            break

    return feed_articles


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
        article_id = article.get("id", "")
        normalized_title = normalize_title(
            article.get("headline", "")
        )

        if not normalized_title:
            continue

        title_words = normalized_title.split()

        title_signature = " ".join(
            title_words[:14]
        )

        if article_id and article_id in seen_ids:
            continue

        if (
            title_signature
            and title_signature in seen_titles
        ):
            continue

        if article_id:
            seen_ids.add(article_id)

        if title_signature:
            seen_titles.add(title_signature)

        unique_articles.append(article)

        if (
            len(unique_articles)
            >= MAX_CACHE_NEWS
        ):
            break

    return unique_articles


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
            []
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

            _status["cached_count"] = len(
                _news_cache
            )

            _status["last_updated"] = (
                payload.get("saved_at")
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
# PUBLIC CACHE FUNCTIONS
# =========================================================

def get_cached_news(limit=None):
    with _cache_lock:
        articles = list(_news_cache)

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

    except (TypeError, ValueError):
        safe_limit = MAX_CACHE_NEWS

    return articles[:safe_limit]


def get_news_status():
    with _cache_lock:
        return dict(_status)


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
        _status["refresh_running"] = True
        _status["last_error"] = None

    try:
        feeds = get_configured_feeds()

        all_articles = []
        feed_errors = []

        worker_count = min(
            MAX_PARALLEL_FEEDS,
            max(1, len(feeds)),
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
                            f"{feed_url[:70]} | "
                            f"{type(error).__name__}: "
                            f"{error}"
                        )
                    )

        merged_articles = (
            merge_with_existing_cache(
                all_articles
            )
        )

        current_time = utc_now_iso()

        with _cache_lock:
            _news_cache = merged_articles

            _status["last_updated"] = (
                current_time
            )

            _status["last_success"] = (
                current_time
            )

            _status["last_fetch_count"] = (
                len(all_articles)
            )

            _status["cached_count"] = len(
                _news_cache
            )

            if feed_errors:
                _status["last_error"] = (
                    f"{len(feed_errors)} feeds failed; "
                    "other feeds updated successfully."
                )
            else:
                _status["last_error"] = None

        save_cache_to_disk(
            merged_articles
        )

        print(
            "NEWS REFRESH SUCCESS | "
            f"Fetched: {len(all_articles)} | "
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
            _status["last_error"] = (
                error_message
            )

        print(
            "NEWS REFRESH FAILED | "
            f"{error_message}",
            flush=True,
        )

        return False

    finally:
        with _cache_lock:
            _status["refresh_running"] = False

        _refresh_lock.release()


def refresh_news_now(
    run_in_background=True,
):
    """
    run_in_background=True:
    API तुरंत response देगी और fetching thread में चलेगी।

    run_in_background=False:
    Current thread में refresh पूरा होगा।
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
# BACKGROUND UPDATER
# =========================================================

def updater_loop():
    with _cache_lock:
        _status["updater_running"] = True

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
            _status["updater_running"] = False


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
# INITIAL CACHE LOAD
# =========================================================

load_cache_from_disk()
