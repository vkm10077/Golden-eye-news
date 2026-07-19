from datetime import datetime, timezone


def get_news(category="all", limit=80):
    all_news = [
        {
            "id": "golden-eye-1",
            "title": "Golden Eye monitoring system is active",
            "summary": (
                "Market, geopolitical, military, weather, disaster "
                "and company news monitoring has started."
            ),
            "category": "market",
            "priority": "high",
            "impact": "high",
            "sentiment": "neutral",
            "affected": [
                "NIFTY",
                "BANKNIFTY",
                "Global Markets"
            ],
            "source": "Golden Eye",
            "published": datetime.now(timezone.utc).isoformat(),
            "link": "",
            "verified": False
        },
        {
            "id": "golden-eye-2",
            "title": "Weather and disaster monitoring is ready",
            "summary": (
                "Cyclone, heavy rain, flood and earthquake alerts "
                "will appear in this section."
            ),
            "category": "weather",
            "priority": "medium",
            "impact": "medium",
            "sentiment": "neutral",
            "affected": [
                "Agriculture",
                "Insurance",
                "Logistics"
            ],
            "source": "Golden Eye",
            "published": datetime.now(timezone.utc).isoformat(),
            "link": "",
            "verified": False
        },
        {
            "id": "golden-eye-3",
            "title": "Geopolitical and military monitoring is ready",
            "summary": (
                "War, sanctions, missile attacks and military "
                "escalation alerts will be monitored."
            ),
            "category": "geopolitical",
            "priority": "high",
            "impact": "high",
            "sentiment": "negative",
            "affected": [
                "Crude Oil",
                "Gold",
                "Defence",
                "Global Markets"
            ],
            "source": "Golden Eye",
            "published": datetime.now(timezone.utc).isoformat(),
            "link": "",
            "verified": False
        }
    ]

    if category != "all":
        all_news = [
            item
            for item in all_news
            if item["category"] == category
        ]

    return all_news[:limit]
