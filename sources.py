# sources.py
# Purpose: Master source list for Dawnly — all RSS feeds, tiers, and weights.
#
# The `weight` field is the coverage reach score used by rank.py to signal
# how globally reaching a source is. It is the single source of truth for
# this value — rank.py reads directly from here, not from its own lookup.
#
# Tier weights:
#   Global   (1.0) — major international wire services and broadcasters
#   Regional (0.7) — strong national outlets with international coverage
#   Niche    (0.4) — specialist, investigative, and regional-focus outlets

SOURCES = [

    # -------------------------------------------------------------------------
    # GLOBAL TIER — weight: 1.0
    # Major international wire services and broadcasters
    # -------------------------------------------------------------------------
    {
        "name": "BBC News",
        "url": "http://feeds.bbci.co.uk/news/rss.xml",
        "tier": "global",
        "weight": 1.0,
        "region": "UK",
    },

    {
        "name": "Al Jazeera English",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "tier": "global",
        "weight": 1.0,
        "region": "Qatar",
    },
    {
        "name": "The Guardian",
        "url": "https://www.theguardian.com/world/rss",
        "tier": "global",
        "weight": 1.0,
        "region": "UK",
    },
    {
        "name": "NPR News",
        "url": "https://feeds.npr.org/1001/rss.xml",
        "tier": "global",
        "weight": 1.0,
        "region": "US",
    },
    {
        "name": "Deutsche Welle",
        "url": "https://rss.dw.com/xml/rss-en-all",
        "tier": "global",
        "weight": 1.0,
        "region": "Germany",
    },
    {
        "name": "France 24",
        "url": "https://www.france24.com/en/world/rss",
        "tier": "global",
        "weight": 1.0,
        "region": "France",
    },
    {
        "name": "NHK World Japan",
        "url": "https://www3.nhk.or.jp/rss/news/cat0.xml",
        "tier": "global",
        "weight": 1.0,
        "region": "Japan",
    },

    # -------------------------------------------------------------------------
    # REGIONAL TIER — weight: 0.7
    # Major national outlets with strong international coverage
    # -------------------------------------------------------------------------
    {
        "name": "The New York Times",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "tier": "regional",
        "weight": 0.7,
        "region": "US",
    },
    {
        "name": "Financial Times",
        "url": "https://www.ft.com/rss/home",
        "tier": "regional",
        "weight": 0.7,
        "region": "UK",
    },
    {
        "name": "South China Morning Post",
        "url": "https://www.scmp.com/rss/91/feed",
        "tier": "regional",
        "weight": 0.7,
        "region": "Hong Kong",
    },
    {
        "name": "The Hindu",
        "url": "https://www.thehindu.com/news/international/?service=rss",
        "tier": "regional",
        "weight": 0.7,
        "region": "India",
    },
    {
        "name": "Dawn Pakistan",
        "url": "https://www.dawn.com/feed",
        "tier": "regional",
        "weight": 0.7,
        "region": "Pakistan",
    },
    {
        "name": "The Diplomat",
        "url": "https://thediplomat.com/feed",
        "tier": "regional",
        "weight": 0.7,
        "region": "Asia-Pacific",
    },
    {
        "name": "Hong Kong Free Press",
        "url": "https://hongkongfp.com/feed",
        "tier": "regional",
        "weight": 0.7,
        "region": "Hong Kong",
    },
    {
        "name": "Middle East Eye",
        "url": "https://www.middleeasteye.net/rss",
        "tier": "regional",
        "weight": 0.7,
        "region": "Middle East",
    },
    {
        "name": "Sydney Morning Herald",
        "url": "https://www.smh.com.au/rss/world.xml",
        "tier": "regional",
        "weight": 0.7,
        "region": "Australia",
    },
    {
        "name": "Toronto Star",
        "url": "https://www.thestar.com/content/thestar/feed.RSSManagerServlet.articles.topstories.rss",
        "tier": "regional",
        "weight": 0.7,
        "region": "Canada",
    },
    {
        "name": "African Arguments",
        "url": "https://africanarguments.org/feed",
        "tier": "regional",
        "weight": 0.7,
        "region": "Africa",
    },
    {
        "name": "Africanews",
        "url": "https://www.africanews.com/feed/rss",
        "tier": "regional",
        "weight": 0.7,
        "region": "Africa",
    },
    {
        "name": "Channel NewsAsia",
        "url": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml",
        "tier": "regional",
        "weight": 0.7,
        "region": "Southeast Asia",
    },
    {
        "name": "MercoPress",
        "url": "https://en.mercopress.com/rss",
        "tier": "regional",
        "weight": 0.7,
        "region": "South America",
    },

    # -------------------------------------------------------------------------
    # NICHE TIER — weight: 0.4
    # Analysis, investigative, and specialist outlets
    # -------------------------------------------------------------------------
    {
        "name": "ProPublica",
        "url": "https://feeds.propublica.org/propublica/main",
        "tier": "niche",
        "weight": 0.4,
        "region": "US",
    },
    {
        "name": "Politico",
        "url": "https://rss.politico.com/politics-news.xml",
        "tier": "niche",
        "weight": 0.4,
        "region": "US",
    },
    {
        "name": "Foreign Policy",
        "url": "https://foreignpolicy.com/feed",
        "tier": "niche",
        "weight": 0.4,
        "region": "Global",
    },
    {
        "name": "Rest of World",
        "url": "https://restofworld.org/feed",
        "tier": "niche",
        "weight": 0.4,
        "region": "Global",
    },
    {
        "name": "The Intercept",
        "url": "https://theintercept.com/feed/?rss",
        "tier": "niche",
        "weight": 0.4,
        "region": "US",
    },
    {
        "name": "Quartz",
        "url": "https://qz.com/feed",
        "tier": "niche",
        "weight": 0.4,
        "region": "Global",
    },
    {
        "name": "Balkan Insight",
        "url": "https://balkaninsight.com/feed",
        "tier": "niche",
        "weight": 0.4,
        "region": "Eastern Europe",
    },
    {
        "name": "Buenos Aires Times",
        "url": "https://www.batimes.com.ar/feed",
        "tier": "niche",
        "weight": 0.4,
        "region": "South America",
    },
    {
        "name": "Global Voices",
        "url": "https://globalvoices.org/feed/",
        "tier": "niche",
        "weight": 0.4,
        "region": "Global",
    },
    {
        "name": "The Moscow Times",
        "url": "https://www.themoscowtimes.com/rss/news",
        "tier": "niche",
        "weight": 0.4,
        "region": "Russia",
    },
    {
        "name": "Mail & Guardian",
        "url": "https://mg.co.za/feed",
        "tier": "niche",
        "weight": 0.4,
        "region": "South Africa",
    },
    {
        "name": "Premium Times Nigeria",
        "url": "https://www.premiumtimesng.com/feed",
        "tier": "niche",
        "weight": 0.4,
        "region": "West Africa",
    },
    {
        "name": "Rio Times",
        "url": "https://riotimesonline.com/feed/",
        "tier": "niche",
        "weight": 0.4,
        "region": "Brazil",
    },

]


# -------------------------------------------------------------------------
# Quick lookup helpers
# -------------------------------------------------------------------------

def get_sources_by_tier(tier: str) -> list[dict]:
    '''Return all sources matching a given tier name.'''
    return [s for s in SOURCES if s["tier"] == tier]


def get_source_weight(name: str) -> float:
    '''Return the weight for a source by name. Returns 0.0 if not found.'''
    for s in SOURCES:
        if s["name"] == name:
            return s["weight"]
    return 0.0


def summary() -> None:
    '''Print a summary of all sources by tier.'''
    for tier in ["global", "regional", "niche"]:
        tier_sources = get_sources_by_tier(tier)
        print(f"\n[{tier.upper()} — {len(tier_sources)} sources]")
        for s in tier_sources:
            print(f"  {s['name']} ({s['region']}) — weight: {s['weight']}")
    print(f"\nTotal sources: {len(SOURCES)}")


if __name__ == "__main__":
    summary()
