import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from news_sources import NEWS_SOURCES


CRITICAL_WORDS = [
    "युद्ध",
    "मिसाइल",
    "हमला",
    "एयर स्ट्राइक",
    "विस्फोट",
    "भूकंप",
    "सुनामी",
    "चक्रवात",
    "बाजार में भारी गिरावट",
    "आपातकाल",
    "war",
    "missile",
    "attack",
    "earthquake",
    "tsunami",
    "cyclone"
]


HIGH_WORDS = [
    "rbi",
    "sebi",
    "ब्याज दर",
    "मौद्रिक नीति",
    "महंगाई",
    "प्रतिबंध",
    "युद्धविराम",
    "कच्चा तेल",
    "भारी बारिश",
    "बाढ़",
    "कंपनी नतीजे",
    "डिविडेंड",
    "बोनस",
    "अधिग्रहण",
    "इस्तीफा",
    "fraud",
    "results",
    "dividend"
]


POSITIVE_WORDS = [
    "तेजी",
    "बढ़त",
    "रिकॉर्ड ऊंचाई",
    "मुनाफा बढ़ा",
    "डिविडेंड",
    "बोनस",
    "बायबैक",
    "वृद्धि",
    "मंजूरी",
    "gain",
    "growth",
    "surge"
]


NEGATIVE_WORDS = [
    "गिरावट",
    "नुकसान",
    "घाटा",
    "धोखाधड़ी",
    "इस्तीफा",
    "युद्ध",
    "हमला",
    "प्रतिबंध",
    "भूकंप",
    "चक्रवात",
    "बाढ़",
    "संकट",
    "fall",
    "loss",
    "crash"
]


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
    for field in ["published", "updated", "created"]:
        value = entry.get(field)

        if not value:
            continue

        try:
            parsed = date_parser.parse(value)

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


def get_priority(text):
    lowered = text.lower()

    if any(word.lower() in lowered for word in CRITICAL_WORDS):
        return "critical", "high"

    if any(word.lower() in lowered for word in HIGH_WORDS):
        return "high", "high"

    return "medium", "medium"


def get_sentiment(text):
    lowered = text.lower()

    positive = sum(
        word.lower() in lowered
        for word in POSITIVE_WORDS
    )

    negative = sum(
        word.lower() in lowered
        for word in NEGATIVE_WORDS
    )

    if positive > negative:
        return "positive"

    if negative > positive:
        return "negative"

    return "neutral"


def get_affected(text):
    lowered = text.lower()
    affected = []

    mapping = {
        "कच्चा तेल": [
            "Oil & Gas",
            "Aviation",
            "Paints"
        ],
        "rbi": [
            "NIFTY",
            "BANKNIFTY",
            "Banks",
            "NBFC"
        ],
        "sebi": [
            "Capital Market",
            "Broking"
        ],
        "ब्याज दर": [
            "Banks",
            "NBFC",
            "Real Estate",
            "Auto"
        ],
        "युद्ध": [
            "Defence",
            "Crude Oil",
            "Gold"
        ],
        "भारी बारिश": [
            "Agriculture",
            "Insurance",
            "Logistics"
        ],
        "बाढ़": [
            "Agriculture",
            "Insurance",
            "Logistics"
        ],
        "कंपनी नतीजे": [
            "Stock Specific"
        ]
    }

    for keyword, sectors in mapping.items():
        if keyword in lowered:
            affected.extend(sectors)

    unique = []

    for item in affected:
        if item not in unique:
            unique.append(item)

    return unique[:6] or ["General Market"]


def create_news_id(title, link):
    raw = f"{title}|{link}".encode(
        "utf-8",
        errors="ignore"
    )

    return hashlib.sha1(
        raw
    ).hexdigest()[:16]


def create_summary(title, description):
    description = clean_text(description)

    if not description:
        return title

    # Google News summary में source आदि हटाने का प्रयास
    description = re.sub(
        r"\s+View Full Coverage.*$",
        "",
        description,
        flags=re.IGNORECASE
    )

    if len(description) > 400:
        description = (
            description[:397]
            .rsplit(" ", 1)[0]
            + "..."
        )

    return description


def fetch_source(source):
    try:
        response = requests.get(
            source["url"],
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 GoldenEyeNews/1.0"
            }
        )

        response.raise_for_status()

        feed = feedparser.parse(
            response.content
        )

    except Exception as error:
        print(
            "RSS FETCH ERROR:",
            source["name"],
            error
        )

        return []

    news_items = []

    for entry in feed.entries[:10]:
        title = clean_text(
            entry.get("title", "")
        )

        if not title:
            continue

        link = entry.get("link", "")

        description = (
            entry.get("summary", "")
            or entry.get("description", "")
        )

        summary = create_summary(
            title,
            description
        )

        combined_text = f"{title} {summary}"

        priority, impact = get_priority(
            combined_text
        )

        news_items.append({
            "id": create_news_id(
                title,
                link
            ),
            "title": title,
            "summary": summary,
            "details": summary,
            "category": source["category"],
            "priority": priority,
            "impact": impact,
            "sentiment": get_sentiment(
                combined_text
            ),
            "affected": get_affected(
                combined_text
            ),
            "source": source["name"],
            "published": get_published_time(
                entry
            ),
            "link": link,
            "verified": True
        })

    return news_items


def remove_duplicates(news_items):
    unique_news = []
    seen = set()

    for item in news_items:
        key = re.sub(
            r"[^a-zA-Z0-9\u0900-\u097F]+",
            " ",
            item["title"].lower()
        ).strip()

        key = " ".join(
            key.split()[:10]
        )

        if key in seen:
            continue

        seen.add(key)
        unique_news.append(item)

    return unique_news


def news_timestamp(item):
    try:
        published = date_parser.parse(
            item.get("published", "")
        )

        if published.tzinfo is None:
            published = published.replace(
                tzinfo=timezone.utc
            )

        return published.timestamp()

    except Exception:
        return 0


def sort_news(news_items):
    # सबसे नई खबर हमेशा सबसे ऊपर
    return sorted(
        news_items,
        key=news_timestamp,
        reverse=True
    )


def get_news(category="all", limit=80):
    selected_sources = [
        source
        for source in NEWS_SOURCES
        if (
            category == "all"
            or source["category"] == category
        )
    ]

    all_news = []

    # सभी feeds parallel load होंगी
    with ThreadPoolExecutor(
        max_workers=6
    ) as executor:

        futures = [
            executor.submit(
                fetch_source,
                source
            )
            for source in selected_sources
        ]

        for future in as_completed(futures):
            try:
                all_news.extend(
                    future.result()
                )
            except Exception as error:
                print(
                    "SOURCE THREAD ERROR:",
                    error
                )

    all_news = remove_duplicates(
        all_news
    )

    all_news = sort_news(
        all_news
    )

    if not all_news:
        return [{
            "id": "golden-eye-feed-error",
            "title": "अभी live news feed उपलब्ध नहीं हो पाई",
            "summary": (
                "कुछ news sources ने समय पर उत्तर नहीं दिया। "
                "एक मिनट बाद Refresh दबाएँ।"
            ),
            "details": (
                "Golden Eye server चल रहा है, लेकिन RSS sources "
                "से फिलहाल data प्राप्त नहीं हुआ।"
            ),
            "category": "market",
            "priority": "medium",
            "impact": "medium",
            "sentiment": "neutral",
            "affected": ["Golden Eye"],
            "source": "Golden Eye",
            "published": datetime.now(
                timezone.utc
            ).isoformat(),
            "link": "",
            "verified": False
        }]

    return all_news[:limit]
