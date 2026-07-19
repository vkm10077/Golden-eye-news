import hashlib
import re
from datetime import datetime, timezone
from functools import lru_cache

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from deep_translator import GoogleTranslator

from news_sources import NEWS_SOURCES

CRITICAL_WORDS = [
    "war",
    "missile",
    "airstrike",
    "attack",
    "explosion",
    "earthquake",
    "tsunami",
    "cyclone",
    "market crash",
    "trading halt",
    "emergency",
    "bank failure",
    "invasion"
]


HIGH_WORDS = [
    "rbi",
    "sebi",
    "federal reserve",
    "fed",
    "interest rate",
    "inflation",
    "sanctions",
    "ceasefire",
    "crude oil",
    "opec",
    "heavy rain",
    "flood",
    "earnings",
    "results",
    "fraud",
    "resignation",
    "acquisition",
    "merger",
    "dividend",
    "bonus"
]


POSITIVE_WORDS = [
    "surge",
    "gain",
    "record high",
    "profit rises",
    "beats estimates",
    "order win",
    "approval",
    "dividend",
    "bonus",
    "buyback",
    "growth",
    "rate cut"
]


NEGATIVE_WORDS = [
    "fall",
    "drop",
    "loss",
    "fraud",
    "resignation",
    "war",
    "attack",
    "sanctions",
    "earthquake",
    "cyclone",
    "flood",
    "default",
    "crash",
    "rate hike"
]


SECTOR_KEYWORDS = {
    "crude oil": [
        "Oil & Gas",
        "Aviation",
        "Paints",
        "Tyres"
    ],
    "gold": [
        "Gold",
        "Jewellery",
        "Metals"
    ],
    "interest rate": [
        "Banks",
        "NBFC",
        "Real Estate",
        "Auto"
    ],
    "rbi": [
        "NIFTY",
        "BANKNIFTY",
        "Banks",
        "NBFC"
    ],
    "sebi": [
        "Capital Market",
        "Broking",
        "NIFTY"
    ],
    "federal reserve": [
        "Global Markets",
        "IT",
        "Metals",
        "USD/INR"
    ],
    "war": [
        "Defence",
        "Crude Oil",
        "Gold",
        "Shipping"
    ],
    "sanctions": [
        "Oil & Gas",
        "Metals",
        "Currency"
    ],
    "cyclone": [
        "Agriculture",
        "Insurance",
        "Logistics"
    ],
    "flood": [
        "Agriculture",
        "Insurance",
        "Logistics"
    ],
    "earnings": [
        "Stock Specific"
    ],
    "results": [
        "Stock Specific"
    ]
}


def clean_text(value):
    soup = BeautifulSoup(
        value or "",
        "html.parser"
    )

    text = soup.get_text(
        " ",
        strip=True
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def get_published_time(entry):
    for field in [
        "published",
        "updated",
        "created"
    ]:
        value = entry.get(field)

        if not value:
            continue

        try:
            parsed_time = date_parser.parse(value)

            if parsed_time.tzinfo is None:
                parsed_time = parsed_time.replace(
                    tzinfo=timezone.utc
                )

            return parsed_time.astimezone(
                timezone.utc
            ).isoformat()

        except Exception:
            continue

    return datetime.now(
        timezone.utc
    ).isoformat()


def get_priority(text):
    text = text.lower()

    for word in CRITICAL_WORDS:
        if word in text:
            return "critical", "high"

    for word in HIGH_WORDS:
        if word in text:
            return "high", "high"

    return "medium", "medium"


def get_sentiment(text):
    text = text.lower()

    positive_score = 0
    negative_score = 0

    for word in POSITIVE_WORDS:
        if word in text:
            positive_score += 1

    for word in NEGATIVE_WORDS:
        if word in text:
            negative_score += 1

    if positive_score > negative_score:
        return "positive"

    if negative_score > positive_score:
        return "negative"

    return "neutral"


def get_affected_sectors(text):
    text = text.lower()
    sectors = []

    for keyword, sector_list in SECTOR_KEYWORDS.items():
        if keyword in text:
            sectors.extend(sector_list)

    unique_sectors = []

    for sector in sectors:
        if sector not in unique_sectors:
            unique_sectors.append(sector)

    if not unique_sectors:
        unique_sectors.append(
            "General Market"
        )

    return unique_sectors[:6]


def create_news_id(title, link):
    value = f"{title}|{link}"

    return hashlib.sha1(
        value.encode(
            "utf-8",
            errors="ignore"
        )
    ).hexdigest()[:16]


def create_summary(title, description):
    description = clean_text(description)

    if not description:
        return title

    if len(description) > 260:
        description = (
            description[:257]
            .rsplit(" ", 1)[0]
            + "..."
        )

    return description


def fetch_source(source):
    feed = feedparser.parse(
        source["url"]
    )

    news_items = []

    # Speed बनाए रखने के लिए प्रत्येक source की latest 12 खबरें
    for entry in feed.entries[:12]:
        original_title = clean_text(
            entry.get("title", "")
        )

        if not original_title:
            continue

        article_link = entry.get(
            "link",
            ""
        )

        rss_description = (
            entry.get("summary", "")
            or entry.get("description", "")
        )

        original_summary = create_summary(
            original_title,
            rss_description
        )

        original_details = fetch_article_details(
            article_link
        )

        if not original_details:
            original_details = original_summary

        # Hindi translation
        hindi_title = translate_to_hindi(
            original_title
        )

        hindi_summary = translate_to_hindi(
            original_summary
        )

        hindi_details = translate_to_hindi(
            original_details
        )

        combined_text = (
            f"{original_title} "
            f"{original_summary} "
            f"{original_details}"
        )

        priority, impact = get_priority(
            combined_text
        )

        news_items.append({
            "id": create_news_id(
                original_title,
                article_link
            ),

            "title": hindi_title,
            "summary": hindi_summary,
            "details": hindi_details,

            "original_title": original_title,

            "category": source["category"],
            "priority": priority,
            "impact": impact,

            "sentiment": get_sentiment(
                combined_text
            ),

            "affected": get_affected_sectors(
                combined_text
            ),

            "source": source["name"],

            "published": get_published_time(
                entry
            ),

            "link": article_link,
            "verified": True
        })

    return news_items
    
def remove_duplicates(news_items):
    unique_news = []
    seen_titles = set()

    for news in news_items:
        title_key = re.sub(
            r"[^a-z0-9]+",
            " ",
            news["title"].lower()
        ).strip()

        title_key = " ".join(
            title_key.split()[:12]
        )

        if title_key in seen_titles:
            continue

        seen_titles.add(title_key)
        unique_news.append(news)

    return unique_news


def sort_news(news_items):
    priority_order = {
        "critical": 3,
        "high": 2,
        "medium": 1,
        "low": 0
    }

    return sorted(
        news_items,
        key=lambda item: (
            priority_order.get(
                item.get("priority", "low"),
                0
            ),
            item.get("published", "")
        ),
        reverse=True
    )


def get_news(category="all", limit=80):
    all_news = []

    for source in NEWS_SOURCES:
        if (
            category != "all"
            and source["category"] != category
        ):
            continue

        try:
            source_news = fetch_source(source)
            all_news.extend(source_news)

        except Exception as error:
            print(
                "NEWS SOURCE ERROR:",
                source["name"],
                error
            )

    all_news = remove_duplicates(
        all_news
    )

    all_news = sort_news(
        all_news
    )

    return all_news[:limit]
