import os
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from news_service import (
    get_cached_news,
    get_news_status,
    refresh_news_now,
    start_news_updater,
)


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)

app.config["JSON_SORT_KEYS"] = False
app.config["JSON_AS_ASCII"] = False

MAX_DASHBOARD_NEWS = 150

_updater_start_lock = threading.Lock()
_updater_started = False


# =========================================================
# COMMON HELPERS
# =========================================================

def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def safe_int(value, default, minimum=None, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default

    if minimum is not None:
        number = max(minimum, number)

    if maximum is not None:
        number = min(maximum, number)

    return number


def ensure_background_updater():
    """
    प्रत्येक Flask process में news updater केवल एक बार शुरू करेगा।
    यह function किसी external fetch के पूरा होने का इंतजार नहीं करता।
    """

    global _updater_started

    if _updater_started:
        return

    with _updater_start_lock:
        if _updater_started:
            return

        try:
            start_news_updater()
            _updater_started = True
            print(
                "BACKGROUND NEWS UPDATER STARTED",
                flush=True
            )

        except Exception as error:
            print(
                "BACKGROUND UPDATER START ERROR | "
                f"{type(error).__name__}: {error}",
                flush=True
            )


def normalize_article(article):
    """
    Dashboard के लिए हर news item का consistent structure बनाता है।
    """

    if not isinstance(article, dict):
        return {}

    important_points = article.get("important_points", [])

    if isinstance(important_points, str):
        important_points = [
            point.strip()
            for point in important_points.split("\n")
            if point.strip()
        ]

    if not isinstance(important_points, list):
        important_points = []

    return {
        "id": str(
            article.get("id")
            or article.get("news_id")
            or article.get("url")
            or ""
        ),

        "headline": str(
            article.get("headline")
            or article.get("title")
            or "महत्वपूर्ण बाजार समाचार"
        ).strip(),

        "title": str(
            article.get("headline")
            or article.get("title")
            or "महत्वपूर्ण बाजार समाचार"
        ).strip(),

        "country": str(
            article.get("country")
            or article.get("region")
            or "Global"
        ).strip(),

        "region": str(
            article.get("region")
            or article.get("country")
            or "Global"
        ).strip(),

        "category": str(
            article.get("category")
            or article.get("topic")
            or "Market"
        ).strip(),

        "impact": str(
            article.get("impact")
            or article.get("market_impact_level")
            or "Medium"
        ).strip(),

        "important_points": important_points[:5],

        "summary_hi": str(
            article.get("summary_hi")
            or article.get("hindi_summary")
            or article.get("summary")
            or article.get("description")
            or ""
        ).strip(),

        "detail_hi": str(
            article.get("detail_hi")
            or article.get("full_detail_hi")
            or article.get("full_summary")
            or article.get("content")
            or article.get("summary_hi")
            or article.get("summary")
            or ""
        ).strip(),

        "market_effect_hi": str(
            article.get("market_effect_hi")
            or article.get("market_impact")
            or article.get("impact_reason")
            or ""
        ).strip(),

        "source": str(
            article.get("source")
            or article.get("source_name")
            or "Unknown Source"
        ).strip(),

        "url": str(
            article.get("url")
            or article.get("link")
            or ""
        ).strip(),

        "published_at": str(
            article.get("published_at")
            or article.get("publishedAt")
            or article.get("datetime")
            or article.get("date")
            or article.get("time")
            or ""
        ).strip(),

        "fetched_at": str(
            article.get("fetched_at")
            or article.get("created_at")
            or ""
        ).strip(),

        "audio_text_hi": str(
            article.get("audio_text_hi")
            or article.get("detail_hi")
            or article.get("full_detail_hi")
            or article.get("summary_hi")
            or article.get("summary")
            or ""
        ).strip(),
    }


def build_news_response(articles):
    normalized_news = []

    for article in articles:
        normalized = normalize_article(article)

        if normalized and normalized.get("headline"):
            normalized_news.append(normalized)

    status = get_news_status()

    return {
        "success": True,
        "count": len(normalized_news),
        "news": normalized_news,
        "last_updated": status.get("last_updated"),
        "last_success": status.get("last_success"),
        "last_error": status.get("last_error"),
        "updater_running": status.get("updater_running", False),
        "server_time": utc_now_iso(),
    }


# =========================================================
# START BACKGROUND UPDATER
# =========================================================

@app.before_request
def start_services_before_request():
    ensure_background_updater()


# =========================================================
# DASHBOARD ROUTES
# =========================================================

@app.route("/", methods=["GET"])
@app.route("/dashboard", methods=["GET"])
def dashboard():
    """
    Dashboard HTML केवल एक बार load होगा।
    Live news JavaScript के द्वारा background में update होगी।
    """

    return render_template("dashboard.html")


# =========================================================
# CACHED NEWS API
# =========================================================

@app.route("/api/news", methods=["GET"])
def api_news():
    """
    केवल cached news तुरंत return करता है।

    यह route external websites से news fetch नहीं करता,
    इसलिए dashboard loading पर नहीं अटकेगा।
    """

    try:
        limit = safe_int(
            request.args.get("limit"),
            default=MAX_DASHBOARD_NEWS,
            minimum=1,
            maximum=MAX_DASHBOARD_NEWS,
        )

        articles = get_cached_news(limit=limit)

        response_data = build_news_response(articles)

        response = jsonify(response_data)
        response.status_code = 200

        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return response

    except Exception as error:
        print(
            "API NEWS ERROR | "
            f"{type(error).__name__}: {error}",
            flush=True
        )

        return jsonify({
            "success": False,
            "count": 0,
            "news": [],
            "last_updated": None,
            "last_success": None,
            "last_error": (
                f"{type(error).__name__}: {error}"
            ),
            "updater_running": False,
            "server_time": utc_now_iso(),
            "message": "News temporarily unavailable",
        }), 500


# =========================================================
# MANUAL REFRESH API
# =========================================================

@app.route("/api/news/refresh", methods=["POST"])
def api_news_refresh():
    """
    Manual refresh request को background thread में चलाता है।

    Browser को external source fetching पूरा होने तक
    wait नहीं करना पड़ता।
    """

    try:
        refresh_started = refresh_news_now(
            run_in_background=True
        )

        status = get_news_status()

        return jsonify({
            "success": True,
            "refresh_started": bool(refresh_started),
            "message": (
                "News refresh background में शुरू हो गया है।"
                if refresh_started
                else "News refresh पहले से चल रहा है।"
            ),
            "last_updated": status.get("last_updated"),
            "last_success": status.get("last_success"),
            "last_error": status.get("last_error"),
            "updater_running": status.get(
                "updater_running",
                False
            ),
            "server_time": utc_now_iso(),
        }), 202

    except Exception as error:
        print(
            "API REFRESH ERROR | "
            f"{type(error).__name__}: {error}",
            flush=True
        )

        return jsonify({
            "success": False,
            "refresh_started": False,
            "message": "News refresh शुरू नहीं हो पाया।",
            "error": (
                f"{type(error).__name__}: {error}"
            ),
            "server_time": utc_now_iso(),
        }), 500


# =========================================================
# NEWS STATUS API
# =========================================================

@app.route("/api/news/status", methods=["GET"])
def api_news_status():
    try:
        status = get_news_status()

        return jsonify({
            "success": True,
            "status": status,
            "server_time": utc_now_iso(),
        }), 200

    except Exception as error:
        return jsonify({
            "success": False,
            "status": {},
            "error": (
                f"{type(error).__name__}: {error}"
            ),
            "server_time": utc_now_iso(),
        }), 500


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health", methods=["GET"])
def health():
    try:
        articles = get_cached_news(limit=1)
        status = get_news_status()

        return jsonify({
            "status": "ok",
            "service": "Golden AI Market News",
            "cached_news_available": bool(articles),
            "updater_running": status.get(
                "updater_running",
                False
            ),
            "last_updated": status.get("last_updated"),
            "server_time": utc_now_iso(),
        }), 200

    except Exception as error:
        return jsonify({
            "status": "degraded",
            "service": "Golden AI Market News",
            "error": (
                f"{type(error).__name__}: {error}"
            ),
            "server_time": utc_now_iso(),
        }), 200


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def page_not_found(error):
    return jsonify({
        "success": False,
        "message": "Requested route not found",
        "path": request.path,
        "server_time": utc_now_iso(),
    }), 404


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({
        "success": False,
        "message": "Internal server error",
        "server_time": utc_now_iso(),
    }), 500


# =========================================================
# LOCAL RUN
# =========================================================

if __name__ == "__main__":
    ensure_background_updater()

    port = safe_int(
        os.environ.get("PORT"),
        default=10000,
        minimum=1,
        maximum=65535,
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        threaded=True,
    )
