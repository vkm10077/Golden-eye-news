import os
from urllib.parse import quote_plus


# =========================================================
# GOOGLE NEWS RSS BUILDER
# =========================================================

def google_news_rss(
    query,
    language="en",
    country="IN",
):
    """
    Google News RSS search URL banata hai।

    English feeds ko preference di gayi hai kyunki global
    market news sabse zyada English sources par milti hai।
    Audio baad mein Hindi reporter style mein chalega।
    """

    safe_query = str(query or "").strip()

    if "when:" not in safe_query.lower():
        safe_query = f"{safe_query} when:1d"

    encoded_query = quote_plus(
        safe_query
    )

    language = (
        str(language or "en")
        .strip()
        .lower()
    )

    country = (
        str(country or "IN")
        .strip()
        .upper()
    )

    locale_map = {
        "en": {
            "hl": "en-IN",
            "ceid": "IN:en",
        },
        "hi": {
            "hl": "hi",
            "ceid": "IN:hi",
        },
    }

    locale = locale_map.get(
        language,
        locale_map["en"],
    )

    return (
        "https://news.google.com/rss/search"
        f"?q={encoded_query}"
        f"&hl={locale['hl']}"
        f"&gl={country}"
        f"&ceid={locale['ceid']}"
    )


# =========================================================
# GLOBAL MARKET-MOVING NEWS SOURCES
# =========================================================

NEWS_SOURCES = [
    # -----------------------------------------------------
    # INDIA — STOCK MARKET, RBI, SEBI AND ECONOMY
    # -----------------------------------------------------
    {
        "name": "India Stock Market",
        "category": "stock_market",
        "region": "India",
        "priority": "high",
        "url": google_news_rss(
            (
                "India stock market OR Nifty OR Sensex "
                "OR Bank Nifty OR NSE OR BSE "
                "market moving news"
            )
        ),
    },
    {
        "name": "RBI Monetary Policy",
        "category": "economy",
        "region": "India",
        "priority": "high",
        "url": google_news_rss(
            (
                "RBI OR Reserve Bank of India "
                "OR repo rate OR monetary policy "
                "OR banking liquidity OR inflation India"
            )
        ),
    },
    {
        "name": "SEBI Regulations",
        "category": "regulation",
        "region": "India",
        "priority": "high",
        "url": google_news_rss(
            (
                "SEBI regulation OR NSE circular "
                "OR BSE circular OR F&O rules "
                "OR stock market regulation India"
            )
        ),
    },
    {
        "name": "India Economy",
        "category": "economy",
        "region": "India",
        "priority": "high",
        "url": google_news_rss(
            (
                "India GDP OR inflation OR CPI "
                "OR IIP OR PMI OR fiscal deficit "
                "OR economic growth market impact"
            )
        ),
    },
    {
        "name": "India Government Policy",
        "category": "policy",
        "region": "India",
        "priority": "high",
        "url": google_news_rss(
            (
                "India government policy OR tax "
                "OR budget OR import duty OR export duty "
                "OR PLI scheme market impact"
            )
        ),
    },

    # -----------------------------------------------------
    # INDIA — COMPANY AND INDUSTRY NEWS
    # -----------------------------------------------------
    {
        "name": "Indian Company Results",
        "category": "corporate",
        "region": "India",
        "priority": "high",
        "url": google_news_rss(
            (
                "Indian company quarterly results "
                "OR earnings OR profit OR revenue "
                "OR guidance stock market"
            )
        ),
    },
    {
        "name": "Indian Corporate Actions",
        "category": "corporate",
        "region": "India",
        "priority": "high",
        "url": google_news_rss(
            (
                "India company merger OR acquisition "
                "OR IPO OR dividend OR bonus issue "
                "OR buyback OR stock split"
            )
        ),
    },
    {
        "name": "Indian Company Orders",
        "category": "corporate",
        "region": "India",
        "priority": "high",
        "url": google_news_rss(
            (
                "Indian listed company order win "
                "OR contract win OR regulatory approval "
                "OR stake sale OR fundraising"
            )
        ),
    },
    {
        "name": "India Banking Sector",
        "category": "banking",
        "region": "India",
        "priority": "high",
        "url": google_news_rss(
            (
                "India banking sector OR bank results "
                "OR bad loans OR NPA OR credit growth "
                "OR deposit growth"
            )
        ),
    },
    {
        "name": "India IT Sector",
        "category": "technology",
        "region": "India",
        "priority": "medium",
        "url": google_news_rss(
            (
                "India IT company deal OR technology contract "
                "OR software exports OR AI investment "
                "Indian IT stocks"
            )
        ),
    },
    {
        "name": "India Pharma Sector",
        "category": "pharma",
        "region": "India",
        "priority": "medium",
        "url": google_news_rss(
            (
                "Indian pharma USFDA approval "
                "OR drug approval OR clinical trial "
                "OR pharma company results"
            )
        ),
    },
    {
        "name": "India Auto Sector",
        "category": "automobile",
        "region": "India",
        "priority": "medium",
        "url": google_news_rss(
            (
                "India automobile sales OR EV policy "
                "OR auto company results OR vehicle prices "
                "OR battery supply"
            )
        ),
    },
    {
        "name": "India Defence Sector",
        "category": "defence",
        "region": "India",
        "priority": "medium",
        "url": google_news_rss(
            (
                "India defence contract OR defence order "
                "OR military procurement OR aerospace company "
                "stock market"
            )
        ),
    },
    {
        "name": "India Energy and Power",
        "category": "energy",
        "region": "India",
        "priority": "medium",
        "url": google_news_rss(
            (
                "India power sector OR renewable energy "
                "OR electricity demand OR energy policy "
                "OR oil company results"
            )
        ),
    },
    {
        "name": "India Infrastructure",
        "category": "infrastructure",
        "region": "India",
        "priority": "medium",
        "url": google_news_rss(
            (
                "India infrastructure project "
                "OR railway order OR road project "
                "OR construction contract market impact"
            )
        ),
    },

    # -----------------------------------------------------
    # USA — FED, WALL STREET AND ECONOMY
    # -----------------------------------------------------
    {
        "name": "Federal Reserve",
        "category": "economy",
        "region": "USA",
        "priority": "high",
        "url": google_news_rss(
            (
                "Federal Reserve OR Fed rate decision "
                "OR Jerome Powell OR interest rates "
                "OR US monetary policy"
            )
        ),
    },
    {
        "name": "US Inflation and Jobs",
        "category": "economy",
        "region": "USA",
        "priority": "high",
        "url": google_news_rss(
            (
                "US inflation OR CPI OR PPI "
                "OR jobs report OR unemployment "
                "OR retail sales market impact"
            )
        ),
    },
    {
        "name": "Wall Street",
        "category": "stock_market",
        "region": "USA",
        "priority": "high",
        "url": google_news_rss(
            (
                "Wall Street OR Dow Jones OR Nasdaq "
                "OR S&P 500 market rally "
                "OR market selloff"
            )
        ),
    },
    {
        "name": "US Corporate Earnings",
        "category": "corporate",
        "region": "USA",
        "priority": "high",
        "url": google_news_rss(
            (
                "US company earnings OR profit warning "
                "OR revenue forecast OR guidance "
                "stock market impact"
            )
        ),
    },
    {
        "name": "US Banking and Credit",
        "category": "banking",
        "region": "USA",
        "priority": "high",
        "url": google_news_rss(
            (
                "US banking crisis OR bank failure "
                "OR liquidity crisis OR credit rating "
                "OR debt default market"
            )
        ),
    },
    {
        "name": "US Technology and AI",
        "category": "technology",
        "region": "USA",
        "priority": "high",
        "url": google_news_rss(
            (
                "US technology stocks OR AI investment "
                "OR semiconductor OR chip restriction "
                "OR big tech earnings"
            )
        ),
    },

    # -----------------------------------------------------
    # EUROPE AND UNITED KINGDOM
    # -----------------------------------------------------
    {
        "name": "European Central Bank",
        "category": "economy",
        "region": "Europe",
        "priority": "high",
        "url": google_news_rss(
            (
                "ECB OR European Central Bank "
                "OR eurozone inflation OR rate decision "
                "market impact"
            )
        ),
    },
    {
        "name": "European Markets",
        "category": "stock_market",
        "region": "Europe",
        "priority": "medium",
        "url": google_news_rss(
            (
                "European stock markets OR DAX OR CAC 40 "
                "OR Euro Stoxx OR Europe economy"
            )
        ),
    },
    {
        "name": "Bank of England",
        "category": "economy",
        "region": "United Kingdom",
        "priority": "medium",
        "url": google_news_rss(
            (
                "Bank of England OR UK inflation "
                "OR UK interest rates OR FTSE 100 "
                "market impact"
            )
        ),
    },

    # -----------------------------------------------------
    # CHINA, JAPAN AND ASIAN MARKETS
    # -----------------------------------------------------
    {
        "name": "China Economy",
        "category": "economy",
        "region": "China",
        "priority": "high",
        "url": google_news_rss(
            (
                "China economy OR PBOC "
                "OR China stimulus OR property crisis "
                "OR manufacturing PMI market"
            )
        ),
    },
    {
        "name": "China Trade and Technology",
        "category": "trade",
        "region": "China",
        "priority": "high",
        "url": google_news_rss(
            (
                "China export restriction OR trade war "
                "OR semiconductor restriction "
                "OR rare earth export market impact"
            )
        ),
    },
    {
        "name": "Japan Economy",
        "category": "economy",
        "region": "Japan",
        "priority": "high",
        "url": google_news_rss(
            (
                "Bank of Japan OR yen OR Japan inflation "
                "OR Japan interest rates OR Nikkei"
            )
        ),
    },
    {
        "name": "Asian Stock Markets",
        "category": "stock_market",
        "region": "Asia",
        "priority": "medium",
        "url": google_news_rss(
            (
                "Asian stock markets OR Hang Seng "
                "OR Nikkei OR Kospi OR Shanghai Composite "
                "market moving news"
            )
        ),
    },

    # -----------------------------------------------------
    # CURRENCY, BONDS AND LIQUIDITY
    # -----------------------------------------------------
    {
        "name": "Global Currency Market",
        "category": "currency",
        "region": "Global",
        "priority": "high",
        "url": google_news_rss(
            (
                "forex market OR dollar index OR rupee "
                "OR yen OR yuan OR euro currency movement"
            )
        ),
    },
    {
        "name": "Global Bond Market",
        "category": "bonds",
        "region": "Global",
        "priority": "high",
        "url": google_news_rss(
            (
                "bond yields OR US Treasury yields "
                "OR government bond market "
                "OR debt market selloff"
            )
        ),
    },

    # -----------------------------------------------------
    # CRUDE OIL, GAS AND COMMODITIES
    # -----------------------------------------------------
    {
        "name": "Crude Oil and OPEC",
        "category": "energy",
        "region": "Global",
        "priority": "high",
        "url": google_news_rss(
            (
                "crude oil OR Brent OR WTI "
                "OR OPEC OR OPEC+ production "
                "OR oil supply disruption"
            )
        ),
    },
    {
        "name": "Natural Gas",
        "category": "energy",
        "region": "Global",
        "priority": "medium",
        "url": google_news_rss(
            (
                "natural gas prices OR LNG supply "
                "OR gas pipeline disruption "
                "OR energy market"
            )
        ),
    },
    {
        "name": "Gold and Silver",
        "category": "precious_metals",
        "region": "Global",
        "priority": "high",
        "url": google_news_rss(
            (
                "gold prices OR silver prices "
                "OR precious metals OR bullion market "
                "OR central bank gold buying"
            )
        ),
    },
    {
        "name": "Industrial Metals",
        "category": "commodities",
        "region": "Global",
        "priority": "medium",
        "url": google_news_rss(
            (
                "copper prices OR aluminium OR steel "
                "OR lithium OR industrial metals "
                "supply demand"
            )
        ),
    },
    {
        "name": "Agriculture Commodities",
        "category": "commodities",
        "region": "Global",
        "priority": "medium",
        "url": google_news_rss(
            (
                "wheat OR rice OR sugar OR soybean "
                "OR coffee commodity prices "
                "OR crop supply market"
            )
        ),
    },

    # -----------------------------------------------------
    # GEOPOLITICS, WAR AND TRADE ROUTES
    # -----------------------------------------------------
    {
        "name": "Global Geopolitical Risk",
        "category": "geopolitics",
        "region": "Global",
        "priority": "high",
        "url": google_news_rss(
            (
                "war OR military attack OR missile attack "
                "OR sanctions OR ceasefire "
                "market impact oil gold"
            )
        ),
    },
    {
        "name": "Middle East Market Risk",
        "category": "geopolitics",
        "region": "Middle East",
        "priority": "high",
        "url": google_news_rss(
            (
                "Iran Israel conflict OR Middle East tension "
                "OR Strait of Hormuz OR oil supply "
                "market impact"
            )
        ),
    },
    {
        "name": "Russia Ukraine Market Risk",
        "category": "geopolitics",
        "region": "Europe",
        "priority": "high",
        "url": google_news_rss(
            (
                "Russia Ukraine war OR sanctions "
                "OR gas supply OR oil exports "
                "global market impact"
            )
        ),
    },
    {
        "name": "Red Sea Shipping",
        "category": "supply_chain",
        "region": "Global",
        "priority": "high",
        "url": google_news_rss(
            (
                "Red Sea shipping disruption "
                "OR Suez Canal disruption "
                "OR freight rates OR supply chain market"
            )
        ),
    },
    {
        "name": "Global Trade Restrictions",
        "category": "trade",
        "region": "Global",
        "priority": "high",
        "url": google_news_rss(
            (
                "tariff OR trade war OR export ban "
                "OR import restriction OR sanctions "
                "market impact"
            )
        ),
    },

    # -----------------------------------------------------
    # WEATHER, NATURAL DISASTER AND SUPPLY CHAIN
    # -----------------------------------------------------
    {
        "name": "Global Weather Market Impact",
        "category": "weather",
        "region": "Global",
        "priority": "medium",
        "url": google_news_rss(
            (
                "cyclone OR hurricane OR flood OR drought "
                "OR heatwave supply chain commodity "
                "market impact"
            )
        ),
    },
    {
        "name": "Earthquake and Infrastructure",
        "category": "disaster",
        "region": "Global",
        "priority": "medium",
        "url": google_news_rss(
            (
                "earthquake OR tsunami OR landslide "
                "factory shutdown port closure "
                "market supply chain impact"
            )
        ),
    },
    {
        "name": "India Weather Market Impact",
        "category": "weather",
        "region": "India",
        "priority": "medium",
        "url": google_news_rss(
            (
                "India monsoon OR IMD cyclone "
                "OR flood OR drought OR crop damage "
                "commodity inflation market impact"
            )
        ),
    },

    # -----------------------------------------------------
    # CRYPTO MARKET
    # -----------------------------------------------------
    {
        "name": "Crypto Market",
        "category": "crypto",
        "region": "Global",
        "priority": "medium",
        "url": google_news_rss(
            (
                "Bitcoin OR Ethereum OR crypto ETF "
                "OR cryptocurrency regulation "
                "OR digital asset market"
            )
        ),
    },

    # -----------------------------------------------------
    # HINDI INDIA MARKET FEEDS
    # -----------------------------------------------------
    {
        "name": "Hindi Indian Market News",
        "category": "stock_market",
        "region": "India",
        "priority": "medium",
        "url": google_news_rss(
            (
                "शेयर बाजार OR निफ्टी OR सेंसेक्स "
                "OR बैंक निफ्टी OR RBI OR SEBI"
            ),
            language="hi",
        ),
    },
    {
        "name": "Hindi Business News",
        "category": "corporate",
        "region": "India",
        "priority": "medium",
        "url": google_news_rss(
            (
                "कंपनी नतीजे OR बड़ा ऑर्डर "
                "OR अधिग्रहण OR विलय OR डिविडेंड "
                "OR बोनस शेयर"
            ),
            language="hi",
        ),
    },
    {
        "name": "Hindi Global Market News",
        "category": "global",
        "region": "Global",
        "priority": "medium",
        "url": google_news_rss(
            (
                "वैश्विक बाजार OR फेडरल रिजर्व "
                "OR कच्चा तेल OR सोना OR युद्ध "
                "OR प्रतिबंध"
            ),
            language="hi",
        ),
    },
]


# =========================================================
# OPTIONAL CUSTOM RSS SOURCES FROM RENDER
# =========================================================

def get_custom_feed_urls():
    """
    Render environment variable:

    NEWS_RSS_FEEDS=url1,url2,url3

    Iske madhyam se baad mein additional RSS feeds add
    ki ja sakti hain।
    """

    configured = os.environ.get(
        "NEWS_RSS_FEEDS",
        "",
    ).strip()

    if not configured:
        return []

    return [
        item.strip()
        for item in configured.split(",")
        if item.strip()
    ]


# =========================================================
# PUBLIC FUNCTIONS
# =========================================================

def get_news_sources():
    """
    NEWS_SOURCES ki safe copy return karta hai।
    """

    return [
        dict(source)
        for source in NEWS_SOURCES
    ]


def get_feed_urls():
    """
    Sabhi default aur custom feed URLs return karta hai।
    Duplicate URLs automatically remove hote hain।
    """

    feed_urls = [
        source["url"]
        for source in NEWS_SOURCES
        if source.get("url")
    ]

    feed_urls.extend(
        get_custom_feed_urls()
    )

    unique_urls = []
    seen_urls = set()

    for url in feed_urls:
        normalized_url = str(
            url
        ).strip()

        if (
            not normalized_url
            or normalized_url in seen_urls
        ):
            continue

        seen_urls.add(
            normalized_url
        )

        unique_urls.append(
            normalized_url
        )

    return unique_urls


def get_high_priority_sources():
    return [
        dict(source)
        for source in NEWS_SOURCES
        if source.get(
            "priority"
        ) == "high"
    ]


def get_sources_by_region(region):
    required_region = str(
        region or ""
    ).strip().lower()

    return [
        dict(source)
        for source in NEWS_SOURCES
        if str(
            source.get(
                "region",
                "",
            )
        ).strip().lower()
        == required_region
    ]


def get_sources_by_category(category):
    required_category = str(
        category or ""
    ).strip().lower()

    return [
        dict(source)
        for source in NEWS_SOURCES
        if str(
            source.get(
                "category",
                "",
            )
        ).strip().lower()
        == required_category
    ]
