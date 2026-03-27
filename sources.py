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
#
# Optional per-source fields:
#   continent           : coarse geographic zone for map layout (all sources)
#   max_articles        : override for per-source fetch cap (default: 50)
#   fallback_url        : secondary URL tried if primary fails
#   user_agent_override : custom User-Agent string for bot-blocking sources

SOURCES = [

    # -------------------------------------------------------------------------
    # GLOBAL TIER — weight: 1.0
    # Major international wire services and broadcasters
    # -------------------------------------------------------------------------
    {
        "name":      "BBC News",
        "url":       "http://feeds.bbci.co.uk/news/rss.xml",
        "tier":      "global",
        "weight":    1.0,
        "region":    "UK",
        "continent": "Europe",
    },
    {
        "name":      "Al Jazeera English",
        "url":       "https://www.aljazeera.com/xml/rss/all.xml",
        "tier":      "global",
        "weight":    1.0,
        "region":    "Qatar",
        "continent": "Middle East & North Africa",
    },
    {
        "name":      "The Guardian",
        "url":       "https://www.theguardian.com/world/rss",
        "tier":      "global",
        "weight":    1.0,
        "region":    "UK",
        "continent": "Europe",
    },
    {
        "name":      "NPR News",
        "url":       "https://feeds.npr.org/1001/rss.xml",
        "tier":      "global",
        "weight":    1.0,
        "region":    "US",
        "continent": "North America",
    },
    {
        "name":      "Deutsche Welle",
        "url":       "https://rss.dw.com/xml/rss-en-all",
        "tier":      "global",
        "weight":    1.0,
        "region":    "Germany",
        "continent": "Europe",
    },
    {
        "name":      "Der Spiegel International",
        "url":       "https://www.spiegel.de/international/index.rss",
        "tier":      "global",
        "weight":    1.0,
        "region":    "Germany",
        "continent": "Europe",
    },
    {
        "name":      "NHK World Japan",
        "url":       "https://www3.nhk.or.jp/rss/news/cat0.xml",
        "tier":      "global",
        "weight":    1.0,
        "region":    "Japan",
        "continent": "East Asia",
    },

    # -------------------------------------------------------------------------
    # REGIONAL TIER — weight: 0.7
    # Major national outlets with strong international coverage
    # -------------------------------------------------------------------------
    {
        "name":      "The New York Times",
        "url":       "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "tier":      "regional",
        "weight":    0.7,
        "region":    "US",
        "continent": "North America",
    },
    {
        "name":      "Financial Times",
        "url":       "https://www.ft.com/rss/home",
        "tier":      "regional",
        "weight":    0.7,
        "region":    "UK",
        "continent": "Europe",
    },
    {
        "name":         "South China Morning Post",
        "url":          "https://www.scmp.com/rss/91/feed",
        "tier":         "regional",
        "weight":       0.7,
        "region":       "Hong Kong",
        "continent":    "East Asia",
        "max_articles": 75,
    },
    {
        "name":         "The Hindu",
        "url":          "https://www.thehindu.com/news/international/?service=rss",
        "tier":         "regional",
        "weight":       0.7,
        "region":       "India",
        "continent":    "South Asia",
        "max_articles": 75,
    },
    {
        "name":      "Dawn Pakistan",
        "url":       "https://www.dawn.com/feed",
        "tier":      "regional",
        "weight":    0.7,
        "region":    "Pakistan",
        "continent": "South Asia",
    },
    {
        "name":         "The Diplomat",
        "url":          "https://thediplomat.com/feed",
        "tier":         "regional",
        "weight":       0.7,
        "region":       "Asia-Pacific",
        "continent":    "East Asia",
        "fallback_url": "https://thediplomat.com/feed/",
    },
    {
        "name":      "Hong Kong Free Press",
        "url":       "https://hongkongfp.com/feed",
        "tier":      "regional",
        "weight":    0.7,
        "region":    "Hong Kong",
        "continent": "East Asia",
    },
    {
        "name":      "Middle East Eye",
        "url":       "https://www.middleeasteye.net/rss",
        "tier":      "regional",
        "weight":    0.7,
        "region":    "Middle East",
        "continent": "Middle East & North Africa",
    },
    {
        "name":      "Sydney Morning Herald",
        "url":       "https://www.smh.com.au/rss/world.xml",
        "tier":      "regional",
        "weight":    0.7,
        "region":    "Australia",
        "continent": "Oceania",
    },
    {
        "name":         "The Globe and Mail",
        "url":          "https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/world/",
        "tier":         "regional",
        "weight":       0.7,
        "region":       "Canada",
        "continent":    "North America",
        "fallback_url": "https://www.theglobeandmail.com/arc/outboundfeeds/rss/",
    },
    {
        "name":      "Africanews",
        "url":       "https://www.africanews.com/feed/rss",
        "tier":      "regional",
        "weight":    0.7,
        "region":    "Africa",
        "continent": "Africa",
    },
    {
        "name":         "The Star Kenya",
        "url":          "https://www.thestar.co.ke/feed",
        "tier":         "regional",
        "weight":       0.7,
        "region":       "East Africa",
        "continent":    "Africa",
        "fallback_url": "https://allafrica.com/tools/headlines/rdf/eastafrica/headlines.rdf",
    },
    {
        "name":      "Channel NewsAsia",
        "url":       "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml",
        "tier":      "regional",
        "weight":    0.7,
        "region":    "Southeast Asia",
        "continent": "Southeast Asia",
    },
    {
        "name":      "MercoPress",
        "url":       "https://en.mercopress.com/rss",
        "tier":      "regional",
        "weight":    0.7,
        "region":    "South America",
        "continent": "South America",
    },
    {
        "name":         "Kyiv Post",
        "url":          "https://www.kyivpost.com/feed",
        "tier":         "regional",
        "weight":       0.7,
        "region":       "Ukraine",
        "continent":    "Europe",
        "fallback_url": "https://www.kyivpost.com/ukraine/feed",
    },

    # -------------------------------------------------------------------------
    # NICHE TIER — weight: 0.4
    # Analysis, investigative, and specialist outlets
    # -------------------------------------------------------------------------
    {
        "name":      "ProPublica",
        "url":       "https://feeds.propublica.org/propublica/main",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "US",
        "continent": "North America",
    },
    {
        "name":      "Foreign Policy",
        "url":       "https://foreignpolicy.com/feed",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "Global",
        "continent": "Global",
    },
    {
        "name":      "Rest of World",
        "url":       "https://restofworld.org/feed",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "Global",
        "continent": "Global",
    },
    {
        "name":      "The Intercept",
        "url":       "https://theintercept.com/feed/?rss",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "US",
        "continent": "North America",
    },
    {
        "name":      "Quartz",
        "url":       "https://qz.com/feed",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "Global",
        "continent": "Global",
    },
    {
        "name":      "Balkan Insight",
        "url":       "https://balkaninsight.com/feed",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "Eastern Europe",
        "continent": "Europe",
    },
    {
        "name":      "Buenos Aires Times",
        "url":       "https://www.batimes.com.ar/feed",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "South America",
        "continent": "South America",
    },
    {
        "name":      "Global Voices",
        "url":       "https://globalvoices.org/feed/",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "Global",
        "continent": "Global",
    },
    {
        "name":      "The Moscow Times",
        "url":       "https://www.themoscowtimes.com/rss/news",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "Russia",
        "continent": "Europe",
    },
    {
        "name":      "Mail & Guardian",
        "url":       "https://mg.co.za/feed",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "South Africa",
        "continent": "Africa",
    },
    {
        "name":      "Premium Times Nigeria",
        "url":       "https://www.premiumtimesng.com/feed",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "West Africa",
        "continent": "Africa",
    },
    {
        "name":      "Rio Times",
        "url":       "https://riotimesonline.com/feed/",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "Brazil",
        "continent": "South America",
    },
    {
        "name":      "Daily Maverick",
        "url":       "https://www.dailymaverick.co.za/dmrss/",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "South Africa",
        "continent": "Africa",
    },
    {
        "name":      "Egypt Independent",
        "url":       "https://www.egyptindependent.com/feed",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "North Africa",
        "continent": "Middle East & North Africa",
    },
    {
        "name":      "Mexico News Daily",
        "url":       "https://mexiconewsdaily.com/feed",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "Mexico",
        "continent": "North America",
    },
    {
        "name":      "Radio Free Europe",
        "url":       "https://www.rferl.org/api/epiqq",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "Central Asia & Eastern Europe",
        "continent": "Europe",
    },
    {
        "name":      "Emerging Europe",
        "url":       "https://emerging-europe.com/feed",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "Eastern Europe",
        "continent": "Europe",
    },
    {
        "name":      "Coconuts Media",
        "url":       "https://coconuts.co/feed",
        "tier":      "niche",
        "weight":    0.4,
        "region":    "Southeast Asia",
        "continent": "Southeast Asia",
    },

]


# -------------------------------------------------------------------------
# Quick lookup helpers
# -------------------------------------------------------------------------

def get_sources_by_tier(tier: str) -> list[dict]:
    '''Return all sources matching a given tier name.'''
    return [s for s in SOURCES if s["tier"] == tier]


def get_sources_by_continent(continent: str) -> list[dict]:
    '''Return all sources matching a given continent.'''
    return [s for s in SOURCES if s.get("continent") == continent]


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
            cap_note = f"  [cap={s['max_articles']}]" if "max_articles" in s else ""
            fallback_note = "  [fallback]" if "fallback_url" in s else ""
            print(f"  {s['name']} ({s['region']}) — weight: {s['weight']}{cap_note}{fallback_note}")
    print(f"\nTotal sources: {len(SOURCES)}")


if __name__ == "__main__":
    summary()
