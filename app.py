from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request


app = Flask(__name__)


def get_news(category="all", limit=80):
    news_items = [
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
        news_items = [
            item
            for item in news_items
            if item["category"] == category
        ]

    return news_items[:limit]


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "project": "Golden Eye",
        "message": "Server is running"
    })


@app.route("/api/news")
def api_news():
    category = request.args.get(
        "category",
        "all"
    ).strip().lower()

    try:
        limit = int(request.args.get("limit", 80))
        limit = max(1, min(limit, 150))
    except ValueError:
        limit = 80

    news = get_news(
        category=category,
        limit=limit
    )

    return jsonify({
        "status": "ok",
        "count": len(news),
        "category": category,
        "news": news
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
