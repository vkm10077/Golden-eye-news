import os
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from news_service import (
    get_cached_news,
    get_news_by_id,
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

MAX_DASHBOARD_NEWS = int(
    os.environ.get(
        "MAX_DASHBOARD_NEWS",
        "150",
    )
)

_updater_start_lock = threading.Lock()
_updater_started = False


# =========================================================
# COMMON HELPERS
# =========================================================

def utc_now_iso():
    return datetime.now(
        timezone.utc
    ).isoformat()


def safe_int(
    value,
    default,
    minimum=None,
    maximum=None,
):
    try:
        number = int(value)

    except (
        TypeError,
        ValueError,
    ):
        number = default

    if minimum is not None:
        number = max(
            minimum,
            number,
        )

    if maximum is not None:
        number = min(
            maximum,
            number,
        )

    return number


def no_cache_response(response):
    response.headers[
        "Cache-Control"
    ] = (
        "no-store, no-cache, must-revalidate, "
        "max-age=0"
    )

    response.headers[
        "Pragma"
    ] = "no-cache"

    response.headers[
        "Expires"
    ] = "0"

    return response


# =========================================================
# BACKGROUND NEWS UPDATER
# =========================================================

def ensure_background_updater():
    """
    प्रत्येक Flask process में background updater
    केवल एक बार शुरू होगा।
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
                "GOLDEN AI BACKGROUND UPDATER STARTED",
                flush=True,
            )

        except Exception as error:
            print(
                "BACKGROUND UPDATER START ERROR | "
                f"{type(error).__name__}: {error}",
                flush=True,
            )


@app.before_request
def start_services_before_request():
    ensure_background_updater()


# =========================================================
# ARTICLE NORMALIZATION
# =========================================================

def normalize_market_impact(article):
    value = str(
        article.get(
            "market_impact"
        )
        or article.get(
            "impact"
        )
        or article.get(
            "sentiment"
        )
        or "Neutral"
    ).strip()

    lowered = value.lower()

    mapping = {
        "positive": "Positive",
        "negative": "Negative",
        "neutral": "Neutral",
        "high": "Neutral",
        "medium": "Neutral",
        "low": "Neutral",
    }

    return mapping.get(
        lowered,
        value,
    )


def normalize_importance(article):
    value = str(
        article.get(
            "importance"
        )
        or article.get(
            "priority"
        )
        or "Medium"
    ).strip()

    lowered = value.lower()

    mapping = {
        "critical": "High",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    }

    return mapping.get(
        lowered,
        "Medium",
    )


def normalize_points(value):
    if isinstance(
        value,
        list,
    ):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ][:5]

    if isinstance(
        value,
        str,
    ):
        return [
            item.strip()
            for item in value.split("\n")
            if item.strip()
        ][:5]

    return []


def normalize_article(article):
    """
    News-service और पुराने news-engine दोनों के
    field names को dashboard के लिए एक consistent
    structure में बदलता है।
    """

    if not isinstance(
        article,
        dict,
    ):
        return {}

    headline = str(
        article.get(
            "headline"
        )
        or article.get(
            "title"
        )
        or "Important market news"
    ).strip()

    article_id = str(
        article.get(
            "id"
        )
        or article.get(
            "news_id"
        )
        or article.get(
            "url"
        )
        or article.get(
            "link"
        )
        or headline
    ).strip()

    market_impact = normalize_market_impact(
        article
    )

    importance = normalize_importance(
        article
    )

    summary = str(
        article.get(
            "summary"
        )
        or article.get(
            "description"
        )
        or article.get(
            "summary_hi"
        )
        or headline
    ).strip()

    full_news = str(
        article.get(
            "full_news"
        )
        or article.get(
            "details"
        )
        or article.get(
            "content"
        )
        or article.get(
            "summary"
        )
        or headline
    ).strip()

    headline_hi = str(
        article.get(
            "headline_hi"
        )
        or article.get(
            "hindi_headline"
        )
        or headline
    ).strip()

    full_news_hi = str(
        article.get(
            "full_news_hi"
        )
        or article.get(
            "detail_hi"
        )
        or article.get(
            "full_detail_hi"
        )
        or article.get(
            "summary_hi"
        )
        or article.get(
            "hindi_summary"
        )
        or full_news
    ).strip()

    market_reason_hi = str(
        article.get(
            "market_reason_hi"
        )
        or article.get(
            "market_effect_hi"
        )
        or article.get(
            "impact_reason"
        )
        or ""
    ).strip()

    audio_text_hi = str(
        article.get(
            "audio_text_hi"
        )
        or full_news_hi
        or headline_hi
    ).strip()

    published_at = str(
        article.get(
            "published_at"
        )
        or article.get(
            "published"
        )
        or article.get(
            "publishedAt"
        )
        or article.get(
            "datetime"
        )
        or article.get(
            "date"
        )
        or article.get(
            "time"
        )
        or ""
    ).strip()

    url = str(
        article.get(
            "url"
        )
        or article.get(
            "link"
        )
        or article.get(
            "original_url"
        )
        or ""
    ).strip()

    return {
        "id": article_id,

        # Dashboard card
        "headline": headline,
        "title": headline,
        "market_impact": market_impact,
        "impact": market_impact,
        "importance": importance,
        "is_breaking": bool(
            article.get(
                "is_breaking",
                False,
            )
        ),

        # Market explanation
        "market_reason_hi": market_reason_hi,
        "market_effect_hi": market_reason_hi,

        # Full news
        "summary": summary,
        "full_news": full_news,
        "headline_hi": headline_hi,
        "full_news_hi": full_news_hi,
        "summary_hi": str(
            article.get(
                "summary_hi"
            )
            or full_news_hi
        ).strip(),
        "detail_hi": str(
            article.get(
                "detail_hi"
            )
            or full_news_hi
        ).strip(),

        # Audio
        "audio_text_hi": audio_text_hi,

        # Additional analysis
        "important_points": normalize_points(
            article.get(
                "important_points",
                [],
            )
        ),
        "affected": normalize_points(
            article.get(
                "affected",
                [],
            )
        ),

        # Metadata
        "country": str(
            article.get(
                "country"
            )
            or article.get(
                "region"
            )
            or "Global"
        ).strip(),

        "region": str(
            article.get(
                "region"
            )
            or article.get(
                "country"
            )
            or "Global"
        ).strip(),

        "category": str(
            article.get(
                "category"
            )
            or article.get(
                "topic"
            )
            or "Market"
        ).strip(),

        "source": str(
            article.get(
                "source"
            )
            or article.get(
                "source_name"
            )
            or "News Source"
        ).strip(),

        "url": url,
        "link": url,
        "published_at": published_at,

        "fetched_at": str(
            article.get(
                "fetched_at"
            )
            or article.get(
                "created_at"
            )
            or ""
        ).strip(),

        "verified": bool(
            article.get(
                "verified",
                True,
            )
        ),
    }


def build_news_response(articles):
    normalized_news = []

    for article in articles:
        normalized = normalize_article(
            article
        )

        if (
            normalized
            and normalized.get(
                "headline"
            )
        ):
            normalized_news.append(
                normalized
            )

    status = get_news_status()

    return {
        "success": True,
        "count": len(
            normalized_news
        ),
        "news": normalized_news,
        "last_updated": status.get(
            "last_updated"
        ),
        "last_success": status.get(
            "last_success"
        ),
        "last_error": status.get(
            "last_error"
        ),
        "updater_running": status.get(
            "updater_running",
            False,
        ),
        "refresh_running": status.get(
            "refresh_running",
            False,
        ),
        "cached_count": status.get(
            "cached_count",
            len(normalized_news),
        ),
        "server_time": utc_now_iso(),
    }


# =========================================================
# DASHBOARD
# =========================================================

@app.route(
    "/",
    methods=["GET"],
)
@app.route(
    "/dashboard",
    methods=["GET"],
)
def dashboard():
    """
    Dashboard HTML एक बार load होगा।
    उसके बाद JavaScript /api/news से live updates लेगा।
    """

    return render_template(
        "dashboard.html"
    )


# =========================================================
# ALL CACHED NEWS API
# =========================================================

@app.route(
    "/api/news",
    methods=["GET"],
)
def api_news():
    """
    यह route केवल cached news return करता है।
    External RSS fetching request के दौरान नहीं होती।
    """

    try:
        limit = safe_int(
            request.args.get(
                "limit"
            ),
            default=MAX_DASHBOARD_NEWS,
            minimum=1,
            maximum=MAX_DASHBOARD_NEWS,
        )

        articles = get_cached_news(
            limit=limit
        )

        response = jsonify(
            build_news_response(
                articles
            )
        )

        response.status_code = 200

        return no_cache_response(
            response
        )

    except Exception as error:
        print(
            "API NEWS ERROR | "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        response = jsonify({
            "success": False,
            "count": 0,
            "news": [],
            "last_updated": None,
            "last_success": None,
            "last_error": (
                f"{type(error).__name__}: {error}"
            ),
            "updater_running": False,
            "refresh_running": False,
            "server_time": utc_now_iso(),
            "message": (
                "News temporarily unavailable"
            ),
        })

        response.status_code = 500

        return no_cache_response(
            response
        )


# =========================================================
# SINGLE FULL NEWS API
# =========================================================

@app.route(
    "/api/news/<article_id>",
    methods=["GET"],
)
def api_single_news(article_id):
    """
    'Puri Khabar' button इस API से selected article की
    पूरी जानकारी प्राप्त करेगा।
    """

    try:
        article = get_news_by_id(
            article_id
        )

        if not article:
            return jsonify({
                "success": False,
                "message": (
                    "Requested news article not found"
                ),
                "server_time": utc_now_iso(),
            }), 404

        normalized = normalize_article(
            article
        )

        response = jsonify({
            "success": True,
            "article": normalized,
            "server_time": utc_now_iso(),
        })

        response.status_code = 200

        return no_cache_response(
            response
        )

    except Exception as error:
        print(
            "SINGLE NEWS API ERROR | "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        return jsonify({
            "success": False,
            "message": (
                "Full news temporarily unavailable"
            ),
            "error": (
                f"{type(error).__name__}: {error}"
            ),
            "server_time": utc_now_iso(),
        }), 500


# =========================================================
# MANUAL NEWS REFRESH
# =========================================================

@app.route(
    "/api/news/refresh",
    methods=["POST"],
)
def api_news_refresh():
    """
    Manual refresh background thread में चलेगा।
    Browser को RSS fetching पूरी होने का इंतजार नहीं करना होगा।
    """

    try:
        refresh_started = refresh_news_now(
            run_in_background=True
        )

        status = get_news_status()

        response = jsonify({
            "success": True,
            "refresh_started": bool(
                refresh_started
            ),
            "message": (
                "News refresh background में शुरू हो गया है।"
                if refresh_started
                else "News refresh पहले से चल रहा है।"
            ),
            "last_updated": status.get(
                "last_updated"
            ),
            "last_success": status.get(
                "last_success"
            ),
            "last_error": status.get(
                "last_error"
            ),
            "updater_running": status.get(
                "updater_running",
                False,
            ),
            "refresh_running": status.get(
                "refresh_running",
                False,
            ),
            "server_time": utc_now_iso(),
        })

        response.status_code = 202

        return no_cache_response(
            response
        )

    except Exception as error:
        print(
            "API REFRESH ERROR | "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        return jsonify({
            "success": False,
            "refresh_started": False,
            "message": (
                "News refresh शुरू नहीं हो पाया।"
            ),
            "error": (
                f"{type(error).__name__}: {error}"
            ),
            "server_time": utc_now_iso(),
        }), 500


# =========================================================
# NEWS STATUS
# =========================================================

@app.route(
    "/api/news/status",
    methods=["GET"],
)
def api_news_status():
    try:
        status = get_news_status()

        response = jsonify({
            "success": True,
            "status": status,
            "server_time": utc_now_iso(),
        })

        response.status_code = 200

        return no_cache_response(
            response
        )

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

@app.route(
    "/health",
    methods=["GET"],
)
def health():
    try:
        articles = get_cached_news(
            limit=1
        )

        status = get_news_status()

        return jsonify({
            "status": "ok",
            "service": (
                "Golden AI Market Intelligence"
            ),
            "cached_news_available": bool(
                articles
            ),
            "cached_count": status.get(
                "cached_count",
                0,
            ),
            "updater_running": status.get(
                "updater_running",
                False,
            ),
            "refresh_running": status.get(
                "refresh_running",
                False,
            ),
            "last_updated": status.get(
                "last_updated"
            ),
            "last_success": status.get(
                "last_success"
            ),
            "last_error": status.get(
                "last_error"
            ),
            "server_time": utc_now_iso(),
        }), 200

    except Exception as error:
        return jsonify({
            "status": "degraded",
            "service": (
                "Golden AI Market Intelligence"
            ),
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
        "message": (
            "Requested route not found"
        ),
        "path": request.path,
        "server_time": utc_now_iso(),
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "success": False,
        "message": (
            "Requested method is not allowed"
        ),
        "path": request.path,
        "server_time": utc_now_iso(),
    }), 405


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({
        "success": False,
        "message": (
            "Internal server error"
        ),
        "server_time": utc_now_iso(),
    }), 500


# =========================================================
# LOCAL RUN
# =========================================================

if __name__ == "__main__":
    ensure_background_updater()

    port = safe_int(
        os.environ.get(
            "PORT"
        ),
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
