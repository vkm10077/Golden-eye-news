from urllib.parse import quote_plus


def google_news_rss(query):
    encoded_query = quote_plus(query)

    return (
        "https://news.google.com/rss/search"
        f"?q={encoded_query}"
        "&hl=en-IN"
        "&gl=IN"
        "&ceid=IN:en"
    )


NEWS_SOURCES = [
    {
        "name": "Indian Market News",
        "category": "market",
        "url": google_news_rss(
            "NIFTY OR SENSEX OR BANKNIFTY OR Indian stock market when:1d"
        )
    },
    {
        "name": "RBI and SEBI News",
        "category": "market",
        "url": google_news_rss(
            "RBI OR SEBI OR interest rate OR monetary policy India when:2d"
        )
    },
    {
        "name": "Company News",
        "category": "company",
        "url": google_news_rss(
            "India company results OR earnings OR dividend OR bonus "
            "OR acquisition OR resignation when:2d"
        )
    },
    {
        "name": "Global Market News",
        "category": "global",
        "url": google_news_rss(
            "Federal Reserve OR inflation OR global stock market "
            "OR recession OR bond yields when:1d"
        )
    },
    {
        "name": "Commodity News",
        "category": "commodity",
        "url": google_news_rss(
            "crude oil OR gold OR silver OR OPEC OR natural gas when:1d"
        )
    },
    {
        "name": "Geopolitical News",
        "category": "geopolitical",
        "url": google_news_rss(
            "war OR sanctions OR ceasefire OR border tension "
            "OR geopolitical crisis when:1d"
        )
    },
    {
        "name": "Military News",
        "category": "military",
        "url": google_news_rss(
            "missile attack OR airstrike OR military conflict "
            "OR defence ministry when:1d"
        )
    },
    {
        "name": "India Weather News",
        "category": "weather",
        "url": google_news_rss(
            "IMD OR heavy rain OR cyclone OR heatwave "
            "OR weather alert India when:1d"
        )
    },
    {
        "name": "Disaster News",
        "category": "disaster",
        "url": google_news_rss(
            "earthquake OR tsunami OR flood OR landslide "
            "OR natural disaster when:1d"
        )
    }
]
