# fetch.py
# Purpose: Async RSS fetcher for Dawnly — pulls headlines from all sources
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
MAX_ARTICLE_AGE_HOURS   = 24        # discard articles older than this (24hr lookback from run time)
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


def is_recent(published: datetime | None, max_age_hours: int = MAX_ARTICLE_AGE_HOURS) -> tuple[bool, bool]:
    '''
    Return (is_recent, is_undated).
    - is_recent : True if the article falls within the age window.
    - is_undated: True if the article had no parseable published date.
    Articles with no date are accepted (is_recent=True) to avoid dropping
    valid content, but flagged so callers can log the count.
    '''
    if published is None:
        return True, True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    return published >= cutoff, False


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
) -> tuple[list[dict], int]:
    '''
    Fetch and parse a single RSS source asynchronously.
    Retries up to MAX_RETRIES times with exponential backoff.
    Returns (articles, undated_count) — articles is a list of clean article
    dicts, undated_count is how many accepted articles had no publish date.
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

                feed          = feedparser.parse(raw)
                articles      = []
                undated_count = 0

                for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
                    title = strip_html(getattr(entry, "title", "") or "")
                    link  = (getattr(entry, "link",  "") or "").strip()

                    if not title or not link:
                        continue

                    published             = parse_date(entry)
                    recent, is_undated    = is_recent(published)

                    if not recent:
                        continue

                    if is_undated:
                        undated_count += 1

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

                undated_note = f"  ({undated_count} undated)" if undated_count else ""
                logger.info(f"  ✓ {name:<35} {len(articles):>3} articles{undated_note}")
                return articles, undated_count

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
                    return [], 0

    return [], 0


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

async def fetch_all_async(
    sources: list[dict] = SOURCES,
) -> tuple[list[dict], list[dict]]:
    '''
    Fetch all RSS sources concurrently and return:
      - A deduplicated flat list of article dicts (sorted by source weight).
      - A per-source health list: one dict per source with fetch results.

    Health dict fields per source:
      name          : source name
      tier          : source tier
      region        : source region
      articles_fetched : count of articles within the 24h window
      undated_count : articles accepted with no publish date
      status        : "ok" | "empty" | "error"
      error         : error message string or None
    '''
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    # Sort so global tier is processed first — dedup keeps highest-weight version
    sorted_sources = sorted(sources, key=lambda s: s["weight"], reverse=True)

    logger.info(
        f"Fetching {len(sorted_sources)} sources "
        f"(concurrency={CONCURRENCY_LIMIT}, window={MAX_ARTICLE_AGE_HOURS}h)...\n"
    )

    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_source(session, source, semaphore)
            for source in sorted_sources
        ]
        results = await asyncio.gather(*tasks)

    # Build per-source health records
    source_health: list[dict] = []
    for source, (articles, undated_count) in zip(sorted_sources, results):
        fetched = len(articles)
        # fetch_source returns [] on error; distinguish empty feed from fetch error
        # by checking whether logger recorded an error — we use fetched count only
        if fetched == 0 and undated_count == 0:
            # Could be a real empty feed or a fetch error; treat as error
            # (fetch_source already logged the error message)
            status = "error"
        elif fetched == 0:
            status = "empty"
        else:
            status = "ok"

        source_health.append({
            "name":             source["name"],
            "tier":             source["tier"],
            "region":           source["region"],
            "articles_fetched": fetched,
            "undated_count":    undated_count,
            "status":           status,
            "error":            None,  # detailed error captured in logs
        })

    all_articles  = [article for batch, _ in results for article in batch]
    total_undated = sum(count for _, count in results)
    all_articles  = deduplicate(all_articles)

    if total_undated:
        logger.warning(
            f"  {total_undated} undated articles accepted "
            f"(no publish date — cannot verify age)"
        )

    logger.info(
        f"\nFetch complete — {len(all_articles)} unique articles ready for clustering"
    )
    return all_articles, source_health


def fetch_all(sources: list[dict] = SOURCES) -> tuple[list[dict], list[dict]]:
    '''
    Synchronous wrapper around fetch_all_async.
    Returns (articles, source_health) — same as fetch_all_async.
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
    articles, health = fetch_all()
    print_summary(articles)
