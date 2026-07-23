import html
import re
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import feedparser
import requests


# =========================================================
# GOLDEN AI INTELLIGENCE NEWS CONFIGURATION
# =========================================================

UPDATE_INTERVAL_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 12
MAX_NEWS_PER_SOURCE = 15
MAX_TOTAL_NEWS = 150

NEWS_CACHE = []
NEWS_LAST_UPDATED = None
NEWS_LAST_ERROR = None

NEWS_LOCK = threading.Lock()
UPDATER_LOCK = threading.Lock()

UPDATER_STARTED = False


# =========================================================
# NEWS SOURCES
# =========================================================

def google_news_rss(search_query, language="en-IN", country="IN"):
    """
    Google News RSS search URL बनाता है।
    """
    encoded_query = quote_plus(search_query)

    return (
        f"https://news.google.com/rss/search"
        f"?q={encoded_query}"
        f"&hl={language}"
        f"&gl={country}"
        f"&ceid={country}:en"
    )


NEWS_SOURCES = [
    {
        "name": "Global Markets",
        "category": "Market",
        "url": google_news_rss(
            "stock market OR global markets OR Wall Street"
        )
    },
    {
        "name": "Indian Markets",
        "category": "Indian Market",
        "url": google_news_rss(
            "Nifty OR Sensex OR Indian stock market"
        )
    },
    {
        "name": "Companies",
        "category": "Corporate",
        "url": google_news_rss(
            "Indian companies earnings results acquisition merger"
        )
    },
    {
        "name": "Economy",
        "category": "Economy",
        "url": google_news_rss(
            "India economy RBI inflation GDP interest rates"
        )
    },
    {
        "name": "Geopolitics",
        "category": "Geopolitics",
        "url": google_news_rss(
            "geopolitical conflict sanctions global tensions"
        )
    },
    {
        "name": "Military",
        "category": "Military",
        "url": google_news_rss(
            "military conflict defence missile war"
        )
    },
    {
        "name": "Weather",
        "category": "Weather",
        "url": google_news_rss(
            "India weather IMD cyclone heavy rain heatwave"
        )
    },
    {
        "name": "Natural Disasters",
        "category": "Disaster",
        "url": google_news_rss(
            "earthquake flood cyclone tsunami landslide"
        )
    },
    {
        "name": "Commodities",
        "category": "Commodity",
        "url": google_news_rss(
            "gold crude oil silver commodity prices"
        )
    },
    {
        "name": "Cryptocurrency",
        "category": "Crypto",
        "url": google_news_rss(
            "Bitcoin cryptocurrency crypto market regulation"
        )
    },
    {
        "name": "Technology",
        "category": "Technology",
        "url": google_news_rss(
            "artificial intelligence technology semiconductor"
        )
    },
    {
        "name": "BBC World",
        "category": "World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml"
    },
    {
        "name": "BBC Business",
        "category": "Business",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml"
    }
]


# =========================================================
# TEXT CLEANING
# =========================================================

def clean_html_text(value):
    """
    RSS description से HTML tags और extra spaces हटाता है।
    """
    if not value:
        return ""

    text = html.unescape(str(value))

    text = re.sub(
        r"<script.*?>.*?</script>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    text = re.sub(
        r"<style.*?>.*?</style>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    text = re.sub(r"<[^>]+>", " ", text)

    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > 700:
        text = text[:700].rsplit(" ", 1)[0] + "..."

    return text


def clean_title(value):
    if not value:
        return "Untitled News"

    title = clean_html_text(value)

    if len(title) > 220:
        title = title[:220].rsplit(" ", 1)[0] + "..."

    return title


# =========================================================
# DATE PROCESSING
# =========================================================

def parse_published_date(entry):
    """
    RSS published date को ISO format और timestamp में बदलता है।
    """
    date_value = (
        entry.get("published")
        or entry.get("updated")
        or entry.get("created")
        or ""
    )

    parsed_datetime = None

    if date_value:
        try:
            parsed_datetime = parsedate_to_datetime(date_value)

            if parsed_datetime.tzinfo is None:
                parsed_datetime = parsed_datetime.replace(
                    tzinfo=timezone.utc
                )

            parsed_datetime = parsed_datetime.astimezone(timezone.utc)

        except Exception:
            parsed_datetime = None

    if parsed_datetime is None:
        parsed_struct = (
            entry.get("published_parsed")
            or entry.get("updated_parsed")
        )

        if parsed_struct:
            try:
                parsed_datetime = datetime(
                    year=parsed_struct.tm_year,
                    month=parsed_struct.tm_mon,
                    day=parsed_struct.tm_mday,
                    hour=parsed_struct.tm_hour,
                    minute=parsed_struct.tm_min,
                    second=parsed_struct.tm_sec,
                    tzinfo=timezone.utc
                )
            except Exception:
                parsed_datetime = None

    if parsed_datetime is None:
        parsed_datetime = datetime.now(timezone.utc)

    return {
        "display": parsed_datetime.strftime(
            "%d %b %Y, %I:%M %p UTC"
        ),
        "iso": parsed_datetime.isoformat(),
        "timestamp": parsed_datetime.timestamp()
    }


# =========================================================
# NEWS FETCHING
# =========================================================

def fetch_single_source(source):
    """
    एक RSS source से news fetch करता है।
    Source fail होने पर empty list return करता है।
    """
    articles = []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13) "
            "AppleWebKit/537.36 "
            "Chrome/124.0 Mobile Safari/537.36"
        ),
        "Accept": (
            "application/rss+xml, application/xml, "
            "text/xml, */*"
        ),
        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        "Connection": "close"
    }

    try:
        response = requests.get(
            source["url"],
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS
        )

        response.raise_for_status()

        parsed_feed = feedparser.parse(response.content)

        if parsed_feed.bozo and not parsed_feed.entries:
            raise ValueError(
                f"Invalid RSS response: {parsed_feed.bozo_exception}"
            )

        for entry in parsed_feed.entries[:MAX_NEWS_PER_SOURCE]:
            title = clean_title(entry.get("title"))

            link = entry.get("link", "").strip()

            summary = clean_html_text(
                entry.get("summary")
                or entry.get("description")
                or entry.get("content", [{}])[0].get("value", "")
            )

            published_data = parse_published_date(entry)

            if not link:
                continue

            articles.append({
                "title": title,
                "summary": summary,
                "link": link,
                "published": published_data["display"],
                "published_iso": published_data["iso"],
                "timestamp": published_data["timestamp"],
                "source": source["name"],
                "category": source["category"]
            })

        print(
            f"NEWS SOURCE SUCCESS | "
            f"{source['name']} | "
            f"{len(articles)} articles"
        )

    except requests.exceptions.Timeout:
        print(
            f"NEWS SOURCE TIMEOUT | "
            f"{source['name']}"
        )

    except requests.exceptions.RequestException as error:
        print(
            f"NEWS SOURCE REQUEST ERROR | "
            f"{source['name']} | "
            f"{type(error).__name__}: {error}"
        )

    except Exception as error:
        print(
            f"NEWS SOURCE ERROR | "
            f"{source['name']} | "
            f"{type(error).__name__}: {error}"
        )

    return articles


# =========================================================
# DUPLICATE REMOVAL
# =========================================================

def normalize_title_for_duplicate_check(title):
    normalized = str(title).lower()

    normalized = re.sub(r"[^a-z0-9\u0900-\u097f ]", " ", normalized)

    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized


def remove_duplicate_news(articles):
    """
    Same headline वाली duplicate news हटाता है।
    """
    unique_articles = []
    seen_titles = set()
    seen_links = set()

    for article in articles:
        title_key = normalize_title_for_duplicate_check(
            article.get("title", "")
        )

        link_key = article.get("link", "").strip().lower()

        if not title_key:
            continue

        if title_key in seen_titles:
            continue

        if link_key and link_key in seen_links:
            continue

        seen_titles.add(title_key)

        if link_key:
            seen_links.add(link_key)

        unique_articles.append(article)

    return unique_articles


# =========================================================
# MARKET IMPACT SCORE
# =========================================================

HIGH_IMPACT_KEYWORDS = [
    "war",
    "attack",
    "missile",
    "sanction",
    "emergency",
    "earthquake",
    "cyclone",
    "rate hike",
    "rate cut",
    "rbi",
    "federal reserve",
    "inflation",
    "gdp",
    "crash",
    "surge",
    "plunge",
    "acquisition",
    "merger",
    "results",
    "profit",
    "loss",
    "default",
    "bankruptcy",
    "crude oil",
    "gold",
    "nifty",
    "sensex"
]


def calculate_impact_score(article):
    """
    Headline और summary के आधार पर approximate market-impact score।
    """
    combined_text = (
        f"{article.get('title', '')} "
        f"{article.get('summary', '')}"
    ).lower()

    score = 20

    for keyword in HIGH_IMPACT_KEYWORDS:
        if keyword in combined_text:
            score += 7

    category = article.get("category", "")

    if category in {
        "Market",
        "Indian Market",
        "Economy",
        "Geopolitics",
        "Military",
        "Commodity",
        "Disaster"
    }:
        score += 15

    return min(score, 100)


def add_news_intelligence_fields(articles):
    processed_articles = []

    for article in articles:
        impact_score = calculate_impact_score(article)

        if impact_score >= 75:
            impact_level = "HIGH"
        elif impact_score >= 45:
            impact_level = "MEDIUM"
        else:
            impact_level = "LOW"

        article["impact_score"] = impact_score
        article["impact_level"] = impact_level

        processed_articles.append(article)

    return processed_articles


# =========================================================
# CACHE UPDATE
# =========================================================

def fetch_all_news():
    """
    सभी sources की news fetch, clean, sort और deduplicate करता है।
    """
    all_articles = []

    for source in NEWS_SOURCES:
        source_articles = fetch_single_source(source)
        all_articles.extend(source_articles)

    all_articles = remove_duplicate_news(all_articles)

    all_articles = add_news_intelligence_fields(all_articles)

    all_articles.sort(
        key=lambda article: article.get("timestamp", 0),
        reverse=True
    )

    return all_articles[:MAX_TOTAL_NEWS]


def update_news_cache_once():
    """
    Cache को एक बार update करता है।
    नई news न मिले तो पुरानी cache delete नहीं करता।
    """
    global NEWS_CACHE
    global NEWS_LAST_UPDATED
    global NEWS_LAST_ERROR

    try:
        fresh_news = fetch_all_news()

        if fresh_news:
            with NEWS_LOCK:
                NEWS_CACHE = fresh_news
                NEWS_LAST_UPDATED = datetime.now(
                    timezone.utc
                ).isoformat()
                NEWS_LAST_ERROR = None

            print(
                f"GOLDEN AI CACHE UPDATED | "
                f"{len(fresh_news)} articles | "
                f"{NEWS_LAST_UPDATED}"
            )

        else:
            with NEWS_LOCK:
                NEWS_LAST_ERROR = (
                    "No fresh articles received. "
                    "Previous cache retained."
                )

            print(
                "GOLDEN AI CACHE WARNING | "
                "No fresh articles received"
            )

    except Exception as error:
        with NEWS_LOCK:
            NEWS_LAST_ERROR = (
                f"{type(error).__name__}: {error}"
            )

        print(
            f"GOLDEN AI CACHE ERROR | "
            f"{type(error).__name__}: {error}"
        )


def news_update_loop():
    """
    Background में हर 60 सेकंड cache update करता है।
    """
    while True:
        cycle_start_time = time.time()

        update_news_cache_once()

        cycle_duration = time.time() - cycle_start_time

        sleep_duration = max(
            5,
            UPDATE_INTERVAL_SECONDS - cycle_duration
        )

        time.sleep(sleep_duration)


# =========================================================
# PUBLIC FUNCTIONS USED BY APP.PY
# =========================================================

def get_cached_news():
    with NEWS_LOCK:
        return [dict(article) for article in NEWS_CACHE]


def get_news_status():
    with NEWS_LOCK:
        return {
            "count": len(NEWS_CACHE),
            "last_updated": NEWS_LAST_UPDATED,
            "last_error": NEWS_LAST_ERROR,
            "update_interval_seconds": UPDATE_INTERVAL_SECONDS
        }


def start_news_updater():
    """
    Background updater को process में केवल एक बार start करता है।
    """
    global UPDATER_STARTED

    with UPDATER_LOCK:
        if UPDATER_STARTED:
            print("NEWS UPDATER ALREADY RUNNING")
            return

        updater_thread = threading.Thread(
            target=news_update_loop,
            daemon=True,
            name="golden-ai-news-updater"
        )

        updater_thread.start()

        UPDATER_STARTED = True

        print("NEWS UPDATER THREAD CREATED")
