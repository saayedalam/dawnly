# fetch.py
# Purpose: Async RSS fetcher for Agora — pulls headlines from all sources
# concurrently with retry logic, date filtering, and deduplication

import asyncio
import aiohttp
import feedparser
import logging
import hashlib
import re
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from sources import SOURCES

load_dotenv()


# -------------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Config
# -------------------------------------------------------------------------

MAX_ARTICLES_PER_SOURCE = 50        # cap per source feed
MAX_ARTICLE_AGE_HOURS   = 48        # discard articles older than this
MAX_RETRIES             = 3         # retry attempts per feed
RETRY_BACKOFF_SECONDS   = 2         # base delay — doubles each retry
REQUEST_TIMEOUT_SECONDS = 10        # per-request timeout
CONCURRENCY_LIMIT       = 10        # max simultaneous feed requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; DawnlyPipeline/1.0; "
        "+https://dawnly.news)"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


# -------------------------------------------------------------------------
# Date helpers
# -------------------------------------------------------------------------

def parse_date(entry: feedparser.FeedParserDict) -> datetime | None:
    '''
    Parse the published date from a feed entry.
    Returns a timezone-aware datetime or None if unparseable.
    '''
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def is_recent(published: datetime | None, max_age_hours: int = MAX_ARTICLE_AGE_HOURS) -> bool:
    '''
    Return True if the article was published within the allowed age window.
    Articles with no date are accepted to avoid dropping valid content.
    '''
    if published is None:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    return published >= cutoff


# -------------------------------------------------------------------------
# Text helpers
# -------------------------------------------------------------------------

def strip_html(text: str) -> str:
    '''Remove HTML tags and normalize whitespace from a string.'''
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_url_hash(url: str) -> str:
    '''Generate a short MD5 hash for a URL — used as deduplication key.'''
    return hashlib.md5(url.encode()).hexdigest()


# -------------------------------------------------------------------------
# Single source fetcher
# -------------------------------------------------------------------------

async def fetch_source(
    session: aiohttp.ClientSession,
    source: dict,
    semaphore: asyncio.Semaphore,
) -> list[dict]:
    '''
    Fetch and parse a single RSS source asynchronously.
    Retries up to MAX_RETRIES times with exponential backoff.
    Returns a list of clean article dicts or empty list on failure.
    '''
    name   = source["name"]
    url    = source["url"]
    weight = source["weight"]
    tier   = source["tier"]
    region = source["region"]

    async with semaphore:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
                async with session.get(url, headers=HEADERS, timeout=timeout) as response:
                    if response.status != 200:
                        raise aiohttp.ClientResponseError(
                            response.request_info,
                            response.history,
                            status=response.status,
                        )
                    raw = await response.text()

                feed     = feedparser.parse(raw)
                articles = []

                for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
                    title = strip_html(getattr(entry, "title", "") or "")
                    link  = (getattr(entry, "link",  "") or "").strip()

                    if not title or not link:
                        continue

                    published = parse_date(entry)

                    if not is_recent(published):
                        continue

                    articles.append({
                        "title":         title,
                        "link":          link,
                        "url_hash":      make_url_hash(link),
                        "published":     published.isoformat() if published else None,
                        "source_name":   name,
                        "source_tier":   tier,
                        "source_weight": weight,
                        "source_region": region,
                    })

                logger.info(f"  ✓ {name:<35} {len(articles):>3} articles")
                return articles

            except Exception as e:
                wait = RETRY_BACKOFF_SECONDS ** attempt
                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"  ↻ {name} — attempt {attempt} failed: {e}. "
                        f"Retrying in {wait}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"  ✗ {name} — all {MAX_RETRIES} attempts failed: {e}")
                    return []

    return []


# -------------------------------------------------------------------------
# Deduplication
# -------------------------------------------------------------------------

def deduplicate(articles: list[dict]) -> list[dict]:
    '''
    Remove duplicate articles by URL hash.
    Keeps the first occurrence — global sources appear first because
    sources are sorted by weight before fetching, so the highest-weight
    version of any duplicate is always preserved.
    '''
    seen    = set()
    unique  = []
    dropped = 0

    for article in articles:
        h = article["url_hash"]
        if h not in seen:
            seen.add(h)
            unique.append(article)
        else:
            dropped += 1

    if dropped:
        logger.info(f"  Deduplication removed {dropped} duplicate URLs")

    return unique


# -------------------------------------------------------------------------
# Main fetch orchestrator
# -------------------------------------------------------------------------

async def fetch_all_async(sources: list[dict] = SOURCES) -> list[dict]:
    '''
    Fetch all RSS sources concurrently and return a deduplicated
    flat list of article dicts, sorted by source weight descending.
    '''
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    # Sort so global tier is processed first — dedup keeps highest-weight version
    sorted_sources = sorted(sources, key=lambda s: s["weight"], reverse=True)

    logger.info(
        f"Fetching {len(sorted_sources)} sources "
        f"(concurrency={CONCURRENCY_LIMIT})...\n"
    )

    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_source(session, source, semaphore)
            for source in sorted_sources
        ]
        results = await asyncio.gather(*tasks)

    all_articles = [article for batch in results for article in batch]
    all_articles = deduplicate(all_articles)

    logger.info(
        f"\nFetch complete — {len(all_articles)} unique articles ready for clustering"
    )
    return all_articles


def fetch_all(sources: list[dict] = SOURCES) -> list[dict]:
    '''
    Synchronous wrapper around fetch_all_async.
    Call this from other pipeline modules.
    '''
    return asyncio.run(fetch_all_async(sources))


# -------------------------------------------------------------------------
# Summary helper
# -------------------------------------------------------------------------

def print_summary(articles: list[dict]) -> None:
    '''Print a breakdown of fetched articles by tier and top sources.'''
    from collections import Counter

    tier_counts   = Counter(a["source_tier"] for a in articles)
    source_counts = Counter(a["source_name"] for a in articles)

    print("\n" + "=" * 50)
    print("FETCH SUMMARY")
    print("=" * 50)
    for tier in ["global", "regional", "niche"]:
        print(f"  {tier.capitalize():<12} {tier_counts.get(tier, 0):>4} articles")
    print(f"  {'Total':<12} {len(articles):>4} articles")

    print("\nTOP SOURCES")
    print("-" * 50)
    for source, count in source_counts.most_common(10):
        print(f"  {source:<35} {count:>4} articles")
    print("=" * 50)


# -------------------------------------------------------------------------
# Entry point — run directly to test the fetcher
# -------------------------------------------------------------------------

if __name__ == "__main__":
    articles = fetch_all()
    print_summary(articles)
