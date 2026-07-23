import os
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from news_service import (
    get_cached_news,
    get_news_status,
    start_news_updater,
    update_news_cache_once
)


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(__name__)

app.config["JSON_AS_ASCII"] = False
app.config["JSON_SORT_KEYS"] = False

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "golden-ai-intelligence-secret-key"
)


# =========================================================
# BACKGROUND NEWS SERVICE
# =========================================================

_background_service_started = False
_background_service_lock = threading.Lock()

_initial_cache_attempted = False
_initial_cache_lock = threading.Lock()

_manual_refresh_lock = threading.Lock()


def start_background_news_service():
    """
    प्रत्येक Python process में background updater को केवल एक बार
    start करता है।
    """
    global _background_service_started

    with _background_service_lock:
        if _background_service_started:
            return

        start_news_updater()

        _background_service_started = True

        print(
            "GOLDEN AI BACKGROUND SERVICE STARTED",
            flush=True
        )


def ensure_news_cache():
    """
    अगर current process में news cache खाली है तो एक synchronous
    update चलाता है।

    इससे ऐसा नहीं होगा कि background updater किसी दूसरे process में
    cache बनाए और API वाला process 0 news return करे।
    """
    global _initial_cache_attempted

    cached_articles = get_cached_news()

    if cached_articles:
        return cached_articles

    with _initial_cache_lock:
        cached_articles = get_cached_news()

        if cached_articles:
            return cached_articles

        if not _initial_cache_attempted:
            _initial_cache_attempted = True

            print(
                "GOLDEN AI INITIAL CACHE UPDATE STARTED",
                flush=True
            )

            try:
                update_news_cache_once()

            except Exception as error:
                print(
                    "GOLDEN AI INITIAL CACHE ERROR | "
                    f"{type(error).__name__}: {error}",
                    flush=True
                )

        return get_cached_news()


start_background_news_service()


# =========================================================
# RESPONSE HELPERS
# =========================================================

def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def build_news_response(articles):
    status = get_news_status()

    return {
        "success": True,
        "count": len(articles),
        "news": articles,
        "last_updated": status.get("last_updated"),
        "last_error": status.get("last_error"),
        "update_interval_seconds": status.get(
            "update_interval_seconds",
            60
        ),
        "server_time": utc_now_iso()
    }


# =========================================================
# MAIN DASHBOARD
# =========================================================

@app.route("/", methods=["GET", "HEAD"])
def home():
    """
    Main dashboard route.

    Render की HEAD health-check request को भी support करता है।
    """
    if request.method == "HEAD":
        return "", 200

    return render_template("dashboard.html")


@app.route("/dashboard", methods=["GET", "HEAD"])
def dashboard():
    """
    Alternate dashboard URL.
    """
    if request.method == "HEAD":
        return "", 200

    return render_template("dashboard.html")


# =========================================================
# LIVE NEWS API
# =========================================================

@app.route("/api/news", methods=["GET"])
def api_news():
    """
    Cached news return करता है।

    अगर cache खाली मिले तो API उसी समय पहली cache update की
    कोशिश करती है।
    """
    try:
        articles = ensure_news_cache()

        response_data = build_news_response(articles)

        print(
            "API NEWS SUCCESS | "
            f"{len(articles)} articles",
            flush=True
        )

        return jsonify(response_data), 200

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
            "last_error": (
                f"{type(error).__name__}: {error}"
            ),
            "update_interval_seconds": 60,
            "server_time": utc_now_iso(),
            "message": "News temporarily unavailable"
        }), 500


# =========================================================
# MANUAL NEWS REFRESH API
# =========================================================

@app.route("/api/news/refresh", methods=["GET", "POST"])
def refresh_news():
    """
    Manual Refresh News button के लिए।

    एक समय में केवल एक manual refresh चलेगा।
    """
    if not _manual_refresh_lock.acquire(blocking=False):
        articles = get_cached_news()

        return jsonify({
            "success": True,
            "refreshing": True,
            "message": "News refresh already running",
            **build_news_response(articles)
        }), 200

    try:
        print(
            "MANUAL NEWS REFRESH STARTED",
            flush=True
        )

        update_news_cache_once()

        articles = get_cached_news()

        print(
            "MANUAL NEWS REFRESH COMPLETED | "
            f"{len(articles)} articles",
            flush=True
        )

        return jsonify({
            "success": True,
            "refreshing": False,
            "message": "News refreshed successfully",
            **build_news_response(articles)
        }), 200

    except Exception as error:
        print(
            "MANUAL NEWS REFRESH ERROR | "
            f"{type(error).__name__}: {error}",
            flush=True
        )

        articles = get_cached_news()

        return jsonify({
            "success": False,
            "refreshing": False,
            "message": "Manual news refresh failed",
            "count": len(articles),
            "news": articles,
            "last_error": (
                f"{type(error).__name__}: {error}"
            ),
            "server_time": utc_now_iso()
        }), 500

    finally:
        _manual_refresh_lock.release()


# =========================================================
# NEWS STATUS API
# =========================================================

@app.route("/api/news/status", methods=["GET"])
def news_status():
    """
    Cache status की पूरी जानकारी दिखाता है।
    """
    try:
        status = get_news_status()
        articles = get_cached_news()

        return jsonify({
            "success": True,
            "cached_news": len(articles),
            "last_updated": status.get("last_updated"),
            "last_error": status.get("last_error"),
            "update_interval_seconds": status.get(
                "update_interval_seconds",
                60
            ),
            "server_time": utc_now_iso()
        }), 200

    except Exception as error:
        return jsonify({
            "success": False,
            "cached_news": 0,
            "last_updated": None,
            "last_error": (
                f"{type(error).__name__}: {error}"
            ),
            "server_time": utc_now_iso()
        }), 500


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health", methods=["GET", "HEAD"])
def health():
    """
    Render health-check और browser testing के लिए।
    """
    if request.method == "HEAD":
        return "", 200

    try:
        articles = get_cached_news()
        status = get_news_status()

        return jsonify({
            "status": "healthy",
            "service": "Golden AI Intelligence News",
            "cached_news": len(articles),
            "last_updated": status.get("last_updated"),
            "last_error": status.get("last_error"),
            "server_time": utc_now_iso()
        }), 200

    except Exception as error:
        return jsonify({
            "status": "unhealthy",
            "service": "Golden AI Intelligence News",
            "cached_news": 0,
            "last_updated": None,
            "last_error": (
                f"{type(error).__name__}: {error}"
            ),
            "server_time": utc_now_iso()
        }), 500


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def page_not_found(error):
    return jsonify({
        "success": False,
        "message": "Page not found",
        "server_time": utc_now_iso()
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "success": False,
        "message": "Method not allowed",
        "server_time": utc_now_iso()
    }), 405


@app.errorhandler(500)
def internal_server_error(error):
    print(
        "FLASK INTERNAL SERVER ERROR | "
        f"{type(error).__name__}: {error}",
        flush=True
    )

    return jsonify({
        "success": False,
        "message": "Internal server error",
        "server_time": utc_now_iso()
    }), 500


# =========================================================
# LOCAL DEVELOPMENT SERVER
# =========================================================

if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        threaded=True,
        use_reloader=False
    )
