from urllib.parse import quote_plus


def google_news_rss(query):
    encoded_query = quote_plus(query)

    return (
        "https://news.google.com/rss/search"
        f"?q={encoded_query}"
        "&hl=hi"
        "&gl=IN"
        "&ceid=IN:hi"
    )


NEWS_SOURCES = [
    {
        "name": "भारतीय शेयर बाजार",
        "category": "market",
        "url": google_news_rss(
            "निफ्टी OR सेंसेक्स OR बैंक निफ्टी OR शेयर बाजार when:1d"
        )
    },
    {
        "name": "RBI और SEBI",
        "category": "market",
        "url": google_news_rss(
            "RBI OR SEBI OR मौद्रिक नीति OR ब्याज दर when:2d"
        )
    },
    {
        "name": "कंपनी समाचार",
        "category": "company",
        "url": google_news_rss(
            "कंपनी नतीजे OR डिविडेंड OR बोनस OR अधिग्रहण OR इस्तीफा when:2d"
        )
    },
    {
        "name": "वैश्विक बाजार",
        "category": "global",
        "url": google_news_rss(
            "Federal Reserve OR वैश्विक बाजार OR महंगाई OR मंदी when:1d"
        )
    },
    {
        "name": "कमोडिटी",
        "category": "commodity",
        "url": google_news_rss(
            "कच्चा तेल OR सोना OR चांदी OR OPEC OR प्राकृतिक गैस when:1d"
        )
    },
    {
        "name": "भू-राजनीतिक समाचार",
        "category": "geopolitical",
        "url": google_news_rss(
            "युद्ध OR प्रतिबंध OR युद्धविराम OR सीमा तनाव when:1d"
        )
    },
    {
        "name": "सैन्य समाचार",
        "category": "military",
        "url": google_news_rss(
            "मिसाइल हमला OR एयर स्ट्राइक OR सैन्य संघर्ष OR रक्षा मंत्रालय when:1d"
        )
    },
    {
        "name": "मौसम समाचार",
        "category": "weather",
        "url": google_news_rss(
            "IMD OR भारी बारिश OR चक्रवात OR हीटवेव OR मौसम चेतावनी when:1d"
        )
    },
    {
        "name": "प्राकृतिक आपदा",
        "category": "disaster",
        "url": google_news_rss(
            "भूकंप OR बाढ़ OR सुनामी OR भूस्खलन OR प्राकृतिक आपदा when:1d"
        )
    }
]        
