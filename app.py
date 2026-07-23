import os
import threading
from flask import Flask, jsonify, render_template

from news_service import get_cached_news, start_news_updater


app = Flask(__name__)

app.config["JSON_AS_ASCII"] = False
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "golden-ai-intelligence-secret-key"
)


# ---------------------------------------------------------
# BACKGROUND NEWS SERVICE
# ---------------------------------------------------------

_news_thread_started = False
_news_thread_lock = threading.Lock()


def start_background_news_service():
    """
    News background updater को केवल एक बार start करता है।
    इससे duplicate threads और duplicate API requests नहीं बनेंगी।
    """
    global _news_thread_started

    with _news_thread_lock:
        if _news_thread_started:
            return

        start_news_updater()
        _news_thread_started = True

        print("GOLDEN AI NEWS UPDATER STARTED")


start_background_news_service()


# ---------------------------------------------------------
# MAIN DASHBOARD
# ---------------------------------------------------------

@app.route("/")
def home():
    """
    Dashboard page open करता है।
    News dashboard.html में JavaScript द्वारा /api/news से load होगी।
    """
    return render_template("dashboard.html")


@app.route("/dashboard")
def dashboard():
    """
    /dashboard URL को भी main dashboard पर open करता है।
    """
    return render_template("dashboard.html")


# ---------------------------------------------------------
# LIVE NEWS API
# ---------------------------------------------------------

@app.route("/api/news")
def api_news():
    """
    Background cache से news देता है।
    यह route external websites को सीधे call नहीं करता।
    """
    try:
        articles = get_cached_news()

        return jsonify({
            "success": True,
            "count": len(articles),
            "news": articles
        }), 200

    except Exception as error:
        print(
            f"API NEWS ERROR | "
            f"{type(error).__name__}: {error}"
        )

        return jsonify({
            "success": False,
            "count": 0,
            "news": [],
            "message": "News temporarily unavailable"
        }), 500


# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------

@app.route("/health")
def health():
    """
    Render health check और server testing के लिए।
    """
    try:
        articles = get_cached_news()

        return jsonify({
            "status": "healthy",
            "service": "Golden AI Intelligence News",
            "cached_news": len(articles)
        }), 200

    except Exception as error:
        return jsonify({
            "status": "unhealthy",
            "service": "Golden AI Intelligence News",
            "error": str(error)
        }), 500


# ---------------------------------------------------------
# ERROR HANDLERS
# ---------------------------------------------------------

@app.errorhandler(404)
def page_not_found(error):
    return jsonify({
        "success": False,
        "message": "Page not found"
    }), 404


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({
        "success": False,
        "message": "Internal server error"
    }), 500


# ---------------------------------------------------------
# LOCAL SERVER
# ---------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        threaded=True
    )
