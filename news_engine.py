import hashlib
import html
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup

from news_sources import NEWS_SOURCES


# =========================================================
# SETTINGS
# =========================================================

REQUEST_TIMEOUT = 12
MAX_WORKERS = 6
MAX_ITEMS_PER_SOURCE = 12
DEFAULT_NEWS_LIMIT = 80

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13) "
    "AppleWebKit/537.36 "
    "Chrome/125.0 Mobile Safari/537.36 "
    "GoldenAI/2.0"
)


# =========================================================
# MARKET FILTER KEYWORDS
# =========================================================

DIRECT_MARKET_WORDS = {
    "stock market",
    "share market",
    "nifty",
    "sensex",
    "bank nifty",
    "nse",
    "bse",
    "nasdaq",
    "dow jones",
    "s&p 500",
    "wall street",
    "nikkei",
    "hang seng",
    "ftse",
    "equity market",
    "market rally",
    "market crash",
    "market selloff",
    "शेयर बाजार",
    "निफ्टी",
    "सेंसेक्स",
    "बैंक निफ्टी",
    "तेजी",
    "गिरावट",
}

ECONOMIC_WORDS = {
    "rbi",
    "sebi",
    "federal reserve",
    "fed",
    "ecb",
    "central bank",
    "interest rate",
    "rate hike",
    "rate cut",
    "monetary policy",
    "inflation",
    "cpi",
    "ppi",
    "gdp",
    "recession",
    "unemployment",
    "jobs report",
    "bond yields",
    "treasury yields",
    "liquidity",
    "budget",
    "tax",
    "fiscal deficit",
    "ब्याज दर",
    "मौद्रिक नीति",
    "महंगाई",
    "बजट",
    "अर्थव्यवस्था",
}

COMPANY_WORDS = {
    "earnings",
    "quarterly results",
    "profit",
    "revenue",
    "guidance",
    "merger",
    "acquisition",
    "bankruptcy",
    "default",
    "ipo",
    "dividend",
    "buyback",
    "bonus issue",
    "stock split",
    "order win",
    "contract win",
    "regulatory approval",
    "stake sale",
    "fundraising",
    "layoffs",
    "profit warning",
    "कंपनी नतीजे",
    "मुनाफा",
    "डिविडेंड",
    "बोनस",
    "बायबैक",
    "अधिग्रहण",
    "विलय",
    "बड़ा ऑर्डर",
}

COMMODITY_WORDS = {
    "crude oil",
    "brent",
    "wti",
    "opec",
    "natural gas",
    "gold",
    "silver",
    "copper",
    "steel",
    "aluminium",
    "lithium",
    "commodity",
    "oil prices",
    "कच्चा तेल",
    "सोना",
    "चांदी",
    "प्राकृतिक गैस",
}

CURRENCY_WORDS = {
    "rupee",
    "dollar",
    "dollar index",
    "yen",
    "yuan",
    "euro",
    "pound",
    "currency",
    "forex",
    "रुपया",
    "डॉलर",
    "मुद्रा",
}

GEOPOLITICAL_WORDS = {
    "war",
    "missile",
    "missile attack",
    "air strike",
    "military attack",
    "sanctions",
    "ceasefire",
    "geopolitical",
    "border conflict",
    "red sea",
    "strait of hormuz",
    "shipping disruption",
    "trade war",
    "tariff",
    "export ban",
    "युद्ध",
    "मिसाइल",
    "हमला",
    "एयर स्ट्राइक",
    "प्रतिबंध",
    "युद्धविराम",
    "सीमा तनाव",
}

WEATHER_DISASTER_WORDS = {
    "earthquake",
    "tsunami",
    "cyclone",
    "hurricane",
    "flood",
    "drought",
    "heatwave",
    "wildfire",
    "landslide",
    "heavy rain",
    "crop damage",
    "port closure",
    "factory shutdown",
    "भूकंप",
    "सुनामी",
    "चक्रवात",
    "बाढ़",
    "सूखा",
    "भारी बारिश",
    "हीटवेव",
    "भूस्खलन",
}

MARKET_CONNECTION_WORDS = {
    "market",
    "stock",
    "shares",
    "investor",
    "economy",
    "inflation",
    "supply",
    "production",
    "company",
    "sector",
    "commodity",
    "oil",
    "gold",
    "currency",
    "trade",
    "export",
    "import",
    "shipping",
    "supply chain",
    "crop",
    "prices",
    "बाजार",
    "शेयर",
    "अर्थव्यवस्था",
    "महंगाई",
    "आपूर्ति",
    "उत्पादन",
    "कंपनी",
    "सेक्टर",
    "कीमत",
}

EXCLUDED_WORDS = {
    "movie review",
    "film review",
    "actor",
    "actress",
    "celebrity",
    "box office",
    "cricket match",
    "football match",
    "sports score",
    "fashion",
    "recipe",
    "horoscope",
    "astrology",
    "wedding",
    "viral video",
    "web series",
    "फिल्म",
    "अभिनेता",
    "अभिनेत्री",
    "क्रिकेट मैच",
    "राशिफल",
}


# =========================================================
# IMPORTANCE AND SENTIMENT
# =========================================================

CRITICAL_WORDS = {
    "emergency rate cut",
    "unexpected rate hike",
    "unexpected rate cut",
    "market crash",
    "trading halt",
    "bankruptcy",
    "sovereign default",
    "financial crisis",
    "currency crisis",
    "missile attack",
    "military attack",
    "major sanctions",
    "oil supply disruption",
    "strait of hormuz closed",
    "war begins",
    "आपातकाल",
    "बाजार में भारी गिरावट",
    "मिसाइल हमला",
    "सैन्य हमला",
    "वित्तीय संकट",
}

HIGH_WORDS = {
    "rbi policy",
    "fed decision",
    "federal reserve decision",
    "central bank decision",
    "interest rate decision",
    "inflation data",
    "jobs report",
    "quarterly results",
    "profit warning",
    "merger",
    "acquisition",
    "tariff",
    "export ban",
    "sanctions",
    "earthquake",
    "cyclone",
    "flood",
    "crude oil",
    "opec",
    "ब्याज दर",
    "मौद्रिक नीति",
    "महंगाई",
    "कंपनी नतीजे",
    "अधिग्रहण",
    "प्रतिबंध",
    "भूकंप",
    "चक्रवात",
}

POSITIVE_WORDS = {
    "beats estimates",
    "profit rises",
    "profit jumps",
    "record profit",
    "revenue growth",
    "strong earnings",
    "order win",
    "wins contract",
    "approval received",
    "rate cut",
    "stimulus",
    "tax cut",
    "buyback",
    "dividend",
    "bonus issue",
    "rating upgrade",
    "exports rise",
    "sales rise",
    "ceasefire",
    "rally",
    "surge",
    "gain",
    "growth",
    "मुनाफा बढ़ा",
    "रिकॉर्ड मुनाफा",
    "बड़ा ऑर्डर",
    "मंजूरी",
    "तेजी",
    "बढ़त",
    "वृद्धि",
    "डिविडेंड",
    "बोनस",
    "बायबैक",
}

NEGATIVE_WORDS = {
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
    "rate hike",
    "tariff",
    "export ban",
    "sanctions",
    "war",
    "missile attack",
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
    "गिरावट",
    "नुकसान",
    "घाटा",
    "धोखाधड़ी",
    "युद्ध",
    "हमला",
    "प्रतिबंध",
    "संकट",
}


# =========================================================
# TEXT HELPERS
# =========================================================

def clean_text(value):
    if not value:
        return ""

    decoded = html.unescape(
        str(value)
    )

    soup = BeautifulSoup(
        decoded,
        "html.parser",
    )

    text = soup.get_text(
        " ",
        strip=True,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def truncate_text(value, limit=900):
    text = clean_text(value)

    if len(text) <= limit:
        return text

    shortened = text[:limit]

    if " " in shortened:
        shortened = shortened.rsplit(
            " ",
            1,
        )[0]

    return shortened.strip() + "..."


def normalize_title(value):
    text = clean_text(
        value
    ).lower()

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


def remove_google_source_suffix(title):
    cleaned = clean_text(
        title
    )

    parts = re.split(
        r"\s+-\s+",
        cleaned,
    )

    if len(parts) < 2:
        return cleaned

    possible_source = parts[-1].strip()

    if 1 <= len(
        possible_source.split()
    ) <= 8:
        return " - ".join(
            parts[:-1]
        ).strip()

    return cleaned


def contains_any(text, keywords):
    lowered = str(
        text or ""
    ).lower()

    return any(
        keyword in lowered
        for keyword in keywords
    )


def count_matches(text, keywords):
    lowered = str(
        text or ""
    ).lower()

    return sum(
        1
        for keyword in keywords
        if keyword in lowered
    )


# =========================================================
# DATE HELPERS
# =========================================================

def get_published_time(entry):
    possible_fields = [
        "published",
        "updated",
        "created",
    ]

    for field in possible_fields:
        value = entry.get(
            field
        )

        if not value:
            continue

        try:
            parsed = parsedate_to_datetime(
                str(value)
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed.astimezone(
                timezone.utc
            ).isoformat()

        except Exception:
            pass

        try:
            iso_value = str(
                value
            ).replace(
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
            ).isoformat()

        except Exception:
            continue

    return datetime.now(
        timezone.utc
    ).isoformat()


def news_timestamp(item):
    published_value = (
        item.get("published")
        or item.get("published_at")
        or ""
    )

    try:
        parsed = datetime.fromisoformat(
            str(published_value).replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.timestamp()

    except Exception:
        return 0


# =========================================================
# MARKET RELEVANCE FILTER
# =========================================================

def relevance_score(title, description):
    title_lower = str(
        title or ""
    ).lower()

    combined = (
        f"{title or ''} {description or ''}"
    ).lower()

    if contains_any(
        combined,
        EXCLUDED_WORDS,
    ):
        return -20

    score = 0

    score += count_matches(
        combined,
        DIRECT_MARKET_WORDS,
    ) * 5

    score += count_matches(
        combined,
        ECONOMIC_WORDS,
    ) * 4

    score += count_matches(
        combined,
        COMPANY_WORDS,
    ) * 4

    score += count_matches(
        combined,
        COMMODITY_WORDS,
    ) * 4

    score += count_matches(
        combined,
        CURRENCY_WORDS,
    ) * 4

    score += count_matches(
        combined,
        GEOPOLITICAL_WORDS,
    ) * 3

    disaster_count = count_matches(
        combined,
        WEATHER_DISASTER_WORDS,
    )

    connection_count = count_matches(
        combined,
        MARKET_CONNECTION_WORDS,
    )

    if (
        disaster_count > 0
        and connection_count > 0
    ):
        score += (
            disaster_count * 3
            + connection_count * 2
        )

    if contains_any(
        title_lower,
        DIRECT_MARKET_WORDS,
    ):
        score += 7

    if contains_any(
        title_lower,
        ECONOMIC_WORDS,
    ):
        score += 5

    if contains_any(
        title_lower,
        COMPANY_WORDS,
    ):
        score += 5

    if contains_any(
        title_lower,
        COMMODITY_WORDS,
    ):
        score += 5

    return score


def is_market_relevant(title, description):
    return relevance_score(
        title,
        description,
    ) >= 5


# =========================================================
# NEWS ANALYSIS
# =========================================================

def get_priority(text):
    lowered = str(
        text or ""
    ).lower()

    if contains_any(
        lowered,
        CRITICAL_WORDS,
    ):
        return "critical", "High"

    score = relevance_score(
        text,
        "",
    )

    if (
        contains_any(
            lowered,
            HIGH_WORDS,
        )
        or score >= 18
    ):
        return "high", "High"

    if score >= 9:
        return "medium", "Medium"

    return "low", "Low"


def get_sentiment(text):
    positive = count_matches(
        text,
        POSITIVE_WORDS,
    )

    negative = count_matches(
        text,
        NEGATIVE_WORDS,
    )

    if positive > negative:
        return "positive"

    if negative > positive:
        return "negative"

    return "neutral"


def sentiment_label(sentiment):
    mapping = {
        "positive": "Positive",
        "negative": "Negative",
        "neutral": "Neutral",
    }

    return mapping.get(
        sentiment,
        "Neutral",
    )


def get_affected(text):
    lowered = str(
        text or ""
    ).lower()

    affected = []

    mapping = {
        "rbi": [
            "NIFTY",
            "BANKNIFTY",
            "Banks",
            "NBFC",
        ],
        "sebi": [
            "Broking",
            "Capital Market",
        ],
        "interest rate": [
            "Banks",
            "NBFC",
            "Real Estate",
            "Auto",
        ],
        "ब्याज दर": [
            "Banks",
            "NBFC",
            "Real Estate",
            "Auto",
        ],
        "crude oil": [
            "Oil & Gas",
            "Aviation",
            "Paints",
            "Tyres",
        ],
        "कच्चा तेल": [
            "Oil & Gas",
            "Aviation",
            "Paints",
            "Tyres",
        ],
        "gold": [
            "Gold",
            "Jewellery",
            "Currency",
        ],
        "सोना": [
            "Gold",
            "Jewellery",
            "Currency",
        ],
        "rupee": [
            "IT",
            "Pharma",
            "Importers",
            "Exporters",
        ],
        "रुपया": [
            "IT",
            "Pharma",
            "Importers",
            "Exporters",
        ],
        "war": [
            "Defence",
            "Crude Oil",
            "Gold",
            "Global Markets",
        ],
        "युद्ध": [
            "Defence",
            "Crude Oil",
            "Gold",
            "Global Markets",
        ],
        "semiconductor": [
            "Technology",
            "Electronics",
            "Auto",
        ],
        "chip": [
            "Technology",
            "Electronics",
            "Auto",
        ],
        "flood": [
            "Agriculture",
            "Insurance",
            "Logistics",
        ],
        "बाढ़": [
            "Agriculture",
            "Insurance",
            "Logistics",
        ],
        "cyclone": [
            "Agriculture",
            "Insurance",
            "Logistics",
            "Ports",
        ],
        "चक्रवात": [
            "Agriculture",
            "Insurance",
            "Logistics",
            "Ports",
        ],
        "earnings": [
            "Stock Specific",
            "Sector Peers",
        ],
        "quarterly results": [
            "Stock Specific",
            "Sector Peers",
        ],
        "कंपनी नतीजे": [
            "Stock Specific",
            "Sector Peers",
        ],
    }

    for keyword, sectors in mapping.items():
        if keyword in lowered:
            affected.extend(
                sectors
            )

    unique = []

    for item in affected:
        if item not in unique:
            unique.append(
                item
            )

    return unique[:6] or [
        "General Market"
    ]


def get_market_reason(
    category,
    sentiment,
    affected,
):
    affected_text = ", ".join(
        affected[:4]
    )

    category_name = str(
        category or ""
    ).lower()

    if category_name in {
        "economy",
        "policy",
        "regulation",
        "bonds",
    }:
        reason = (
            "इस खबर से interest rates, liquidity, currency "
            "और equity market sentiment प्रभावित हो सकता है।"
        )

    elif category_name in {
        "energy",
        "commodities",
        "precious_metals",
    }:
        reason = (
            "Commodity prices में बदलाव से inflation, currency "
            "और संबंधित कंपनियों के margins पर असर पड़ सकता है।"
        )

    elif category_name in {
        "corporate",
        "banking",
        "technology",
        "pharma",
        "automobile",
        "defence",
        "infrastructure",
    }:
        reason = (
            "इस development से संबंधित company, उसके sector "
            "और peer stocks में movement आ सकता है।"
        )

    elif category_name in {
        "geopolitics",
        "trade",
        "supply_chain",
    }:
        reason = (
            "इस खबर से global risk sentiment, crude oil, gold "
            "और equity markets में volatility बढ़ सकती है।"
        )

    elif category_name in {
        "weather",
        "disaster",
    }:
        reason = (
            "Production, transport, crops या supply chain प्रभावित "
            "होने पर commodity और sector stocks में movement आ सकता है।"
        )

    elif category_name == "crypto":
        reason = (
            "इस खबर से Bitcoin, Ethereum और crypto market "
            "में तेज volatility आ सकती है।"
        )

    else:
        reason = (
            "यह खबर market sentiment और संबंधित sectors "
            "को प्रभावित कर सकती है।"
        )

    if sentiment == "positive":
        direction_text = (
            "शुरुआती असर सकारात्मक रह सकता है।"
        )

    elif sentiment == "negative":
        direction_text = (
            "शुरुआती असर नकारात्मक रह सकता है।"
        )

    else:
        direction_text = (
            "साफ direction के लिए price और volume reaction देखना जरूरी है।"
        )

    return (
        f"{reason} {direction_text} "
        f"प्रभावित क्षेत्र: {affected_text}।"
    )


# =========================================================
# NEWS ITEM CREATION
# =========================================================

def create_news_id(title, link):
    raw_value = (
        f"{normalize_title(title)}|"
        f"{str(link or '').strip()}"
    )

    return hashlib.sha256(
        raw_value.encode(
            "utf-8",
            errors="ignore",
        )
    ).hexdigest()[:24]


def get_entry_description(entry):
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
        cleaned = clean_text(
            candidate
        )

        if cleaned:
            return cleaned

    return ""


def create_summary(title, description):
    cleaned_description = clean_text(
        description
    )

    cleaned_description = re.sub(
        r"\s+View Full Coverage.*$",
        "",
        cleaned_description,
        flags=re.IGNORECASE,
    )

    if not cleaned_description:
        return truncate_text(
            title,
            500,
        )

    return truncate_text(
        cleaned_description,
        700,
    )


def create_audio_text(
    title,
    summary,
    market_reason,
):
    parts = []

    if title:
        parts.append(
            clean_text(title)
        )

    if (
        summary
        and normalize_title(
            summary
        ) != normalize_title(
            title
        )
    ):
        parts.append(
            clean_text(summary)
        )

    if market_reason:
        parts.append(
            clean_text(market_reason)
        )

    return "। ".join(
        part.rstrip(
            ".। "
        )
        for part in parts
        if part
    ) + "।"


# =========================================================
# RSS FETCHING
# =========================================================

def fetch_source(source):
    source_name = source.get(
        "name",
        "News Source",
    )

    source_url = source.get(
        "url",
        "",
    )

    if not source_url:
        return []

    try:
        response = requests.get(
            source_url,
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": (
                    "application/rss+xml,"
                    "application/xml,"
                    "text/xml,*/*"
                ),
                "Accept-Language": (
                    "en-IN,en;q=0.9,hi;q=0.8"
                ),
            },
        )

        response.raise_for_status()

        feed = feedparser.parse(
            response.content
        )

    except Exception as error:
        print(
            "RSS FETCH ERROR | "
            f"{source_name} | "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        return []

    news_items = []

    for entry in feed.entries[
        :MAX_ITEMS_PER_SOURCE
    ]:
        try:
            raw_title = clean_text(
                entry.get(
                    "title",
                    "",
                )
            )

            title = remove_google_source_suffix(
                raw_title
            )

            if not title:
                continue

            description = get_entry_description(
                entry
            )

            if not is_market_relevant(
                title,
                description,
            ):
                continue

            summary = create_summary(
                title,
                description,
            )

            combined_text = (
                f"{title} {summary}"
            )

            priority, importance = get_priority(
                combined_text
            )

            sentiment = get_sentiment(
                combined_text
            )

            affected = get_affected(
                combined_text
            )

            market_reason = get_market_reason(
                category=source.get(
                    "category",
                    "market",
                ),
                sentiment=sentiment,
                affected=affected,
            )

            link = str(
                entry.get(
                    "link",
                    "",
                )
            ).strip()

            published_at = get_published_time(
                entry
            )

            impact_label = sentiment_label(
                sentiment
            )

            audio_text = create_audio_text(
                title=title,
                summary=summary,
                market_reason=market_reason,
            )

            news_items.append({
                "id": create_news_id(
                    title,
                    link,
                ),

                # Current news_engine compatibility
                "title": title,
                "summary": summary,
                "details": summary,
                "category": source.get(
                    "category",
                    "market",
                ),
                "priority": priority,
                "impact": impact_label,
                "sentiment": sentiment,
                "affected": affected,
                "source": source_name,
                "published": published_at,
                "link": link,
                "verified": True,

                # New dashboard compatibility
                "headline": title,
                "market_impact": impact_label,
                "importance": importance,
                "market_reason_hi": market_reason,
                "market_effect_hi": market_reason,
                "full_news": summary,
                "full_news_hi": summary,
                "detail_hi": summary,
                "summary_hi": summary,
                "headline_hi": title,
                "audio_text_hi": audio_text,
                "published_at": published_at,
                "url": link,
                "region": source.get(
                    "region",
                    "Global",
                ),
                "country": source.get(
                    "region",
                    "Global",
                ),
                "is_breaking": (
                    priority == "critical"
                ),
            })

        except Exception as error:
            print(
                "RSS ENTRY ERROR | "
                f"{source_name} | "
                f"{type(error).__name__}: {error}",
                flush=True,
            )

    return news_items


# =========================================================
# DEDUPLICATION AND SORTING
# =========================================================

def remove_duplicates(news_items):
    unique_news = []
    seen_ids = set()
    seen_titles = set()

    sorted_items = sort_news(
        news_items
    )

    for item in sorted_items:
        article_id = str(
            item.get(
                "id",
                "",
            )
        )

        normalized = normalize_title(
            item.get(
                "title",
                "",
            )
        )

        if not normalized:
            continue

        title_signature = " ".join(
            normalized.split()[:15]
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

        unique_news.append(
            item
        )

    return unique_news


def sort_news(news_items):
    return sorted(
        news_items,
        key=news_timestamp,
        reverse=True,
    )


# =========================================================
# PUBLIC FUNCTION
# =========================================================

def get_news(
    category="all",
    limit=DEFAULT_NEWS_LIMIT,
):
    required_category = str(
        category or "all"
    ).strip().lower()

    selected_sources = [
        source
        for source in NEWS_SOURCES
        if (
            required_category == "all"
            or str(
                source.get(
                    "category",
                    "",
                )
            ).strip().lower()
            == required_category
        )
    ]

    if not selected_sources:
        selected_sources = list(
            NEWS_SOURCES
        )

    all_news = []

    worker_count = min(
        MAX_WORKERS,
        max(
            1,
            len(selected_sources),
        ),
    )

    with ThreadPoolExecutor(
        max_workers=worker_count
    ) as executor:

        futures = [
            executor.submit(
                fetch_source,
                source,
            )
            for source in selected_sources
        ]

        for future in as_completed(
            futures
        ):
            try:
                all_news.extend(
                    future.result()
                )

            except Exception as error:
                print(
                    "SOURCE THREAD ERROR | "
                    f"{type(error).__name__}: {error}",
                    flush=True,
                )

    all_news = remove_duplicates(
        all_news
    )

    all_news = sort_news(
        all_news
    )

    try:
        safe_limit = max(
            1,
            min(
                int(limit),
                200,
            ),
        )

    except (
        TypeError,
        ValueError,
    ):
        safe_limit = DEFAULT_NEWS_LIMIT

    if all_news:
        return all_news[
            :safe_limit
        ]

    current_time = datetime.now(
        timezone.utc
    ).isoformat()

    return [{
        "id": "golden-ai-feed-temporary-error",
        "title": "अभी live market news उपलब्ध नहीं हो पाई",
        "headline": "अभी live market news उपलब्ध नहीं हो पाई",
        "summary": (
            "कुछ news sources ने समय पर response नहीं दिया। "
            "थोड़ी देर बाद system अपने आप दोबारा कोशिश करेगा।"
        ),
        "details": (
            "Golden AI server चल रहा है, लेकिन RSS feeds से "
            "फिलहाल नई खबर प्राप्त नहीं हुई।"
        ),
        "full_news": (
            "Golden AI server चल रहा है, लेकिन RSS feeds से "
            "फिलहाल नई खबर प्राप्त नहीं हुई।"
        ),
        "full_news_hi": (
            "Golden AI server चल रहा है, लेकिन RSS feeds से "
            "फिलहाल नई खबर प्राप्त नहीं हुई।"
        ),
        "detail_hi": (
            "कुछ news sources ने समय पर response नहीं दिया।"
        ),
        "summary_hi": (
            "कुछ news sources ने समय पर response नहीं दिया।"
        ),
        "headline_hi": (
            "अभी live market news उपलब्ध नहीं हो पाई"
        ),
        "audio_text_hi": (
            "अभी live market news उपलब्ध नहीं हो पाई। "
            "System थोड़ी देर बाद अपने आप दोबारा कोशिश करेगा।"
        ),
        "category": "market",
        "priority": "medium",
        "importance": "Medium",
        "impact": "Neutral",
        "market_impact": "Neutral",
        "sentiment": "neutral",
        "affected": [
            "Golden AI"
        ],
        "market_reason_hi": (
            "यह केवल temporary feed status है, market news नहीं।"
        ),
        "market_effect_hi": (
            "यह केवल temporary feed status है, market news नहीं।"
        ),
        "source": "Golden AI",
        "published": current_time,
        "published_at": current_time,
        "link": "",
        "url": "",
        "region": "Global",
        "country": "Global",
        "is_breaking": False,
        "verified": False,
    }]
