from flask import Flask, jsonify, render_template, request

from news_engine import get_news


app = Flask(__name__)


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
    category = request.args.get("category", "all").strip().lower()
    limit = request.args.get("limit", "80")

    try:
        limit = max(1, min(int(limit), 150))
    except ValueError:
        limit = 80

    news = get_news(category=category, limit=limit)

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
