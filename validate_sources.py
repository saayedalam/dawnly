# validate_sources.py
# Purpose: Standalone diagnostic tool — validates all Dawnly RSS sources
# without touching the pipeline. Run manually anytime to check source health.
#
# Usage:
#   python3 validate_sources.py
#
# What it checks per source:
#   - Primary URL returns HTTP 200 and valid XML
#   - Feed contains at least 1 article
#   - Fallback URL (if defined) is also tested independently
#
# Exit codes:
#   0 — all sources passed
#   1 — one or more sources failed

import asyncio
import aiohttp
import feedparser
import time
import sys
from dataclasses import dataclass, field
from sources import SOURCES


# -------------------------------------------------------------------------
# Config
# -------------------------------------------------------------------------

REQUEST_TIMEOUT_SECONDS = 15    # slightly more generous than pipeline
CONCURRENCY_LIMIT       = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; DawnlyPipeline/1.0; "
        "+https://dawnly.news)"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


# -------------------------------------------------------------------------
# Result dataclass
# -------------------------------------------------------------------------

@dataclass
class ValidationResult:
    name:             str
    primary_url:      str
    primary_ok:       bool
    primary_status:   int | None
    primary_articles: int
    primary_error:    str | None
    fallback_url:     str | None          = None
    fallback_ok:      bool | None         = None
    fallback_status:  int | None          = None
    fallback_articles: int                = 0
    fallback_error:   str | None          = None

    @property
    def passed(self) -> bool:
        return self.primary_ok


# -------------------------------------------------------------------------
# Single URL validator
# -------------------------------------------------------------------------

async def validate_url(
    session: aiohttp.ClientSession,
    url: str,
    headers: dict,
) -> tuple[bool, int | None, int, str | None]:
    '''
    Fetch a single URL and check it returns a valid, non-empty RSS feed.
    Returns (ok, http_status, article_count, error_message).
    '''
    try:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        async with session.get(url, headers=headers, timeout=timeout) as response:
            status = response.status
            if status != 200:
                return False, status, 0, f"HTTP {status}"
            raw = await response.text()

        feed = feedparser.parse(raw)

        if feed.bozo and not feed.entries:
            return False, status, 0, "Invalid XML or empty feed"

        article_count = len(feed.entries)
        if article_count == 0:
            return False, status, 0, "Feed is empty (0 articles)"

        return True, status, article_count, None

    except asyncio.TimeoutError:
        return False, None, 0, f"Timeout after {REQUEST_TIMEOUT_SECONDS}s"
    except Exception as e:
        return False, None, 0, str(e)


# -------------------------------------------------------------------------
# Per-source validator
# -------------------------------------------------------------------------

async def validate_source(
    session: aiohttp.ClientSession,
    source: dict,
    semaphore: asyncio.Semaphore,
) -> ValidationResult:
    '''Validate a single source — primary URL and fallback URL if defined.'''
    name         = source["name"]
    primary_url  = source["url"]
    fallback_url = source.get("fallback_url")
    ua_override  = source.get("user_agent_override")
    headers      = {**HEADERS, "User-Agent": ua_override} if ua_override else HEADERS

    async with semaphore:
        p_ok, p_status, p_articles, p_error = await validate_url(
            session, primary_url, headers
        )

        result = ValidationResult(
            name             = name,
            primary_url      = primary_url,
            primary_ok       = p_ok,
            primary_status   = p_status,
            primary_articles = p_articles,
            primary_error    = p_error,
            fallback_url     = fallback_url,
        )

        if fallback_url:
            f_ok, f_status, f_articles, f_error = await validate_url(
                session, fallback_url, headers
            )
            result.fallback_ok       = f_ok
            result.fallback_status   = f_status
            result.fallback_articles = f_articles
            result.fallback_error    = f_error

        return result


# -------------------------------------------------------------------------
# Main validator
# -------------------------------------------------------------------------

async def validate_all() -> list[ValidationResult]:
    '''Validate all sources concurrently and return results.'''
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async with aiohttp.ClientSession() as session:
        tasks = [
            validate_source(session, source, semaphore)
            for source in SOURCES
        ]
        results = await asyncio.gather(*tasks)

    return list(results)


# -------------------------------------------------------------------------
# Report printer
# -------------------------------------------------------------------------

def print_report(results: list[ValidationResult], elapsed: float) -> None:
    '''Print a clean pass/fail validation report.'''
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    total         = len(results)
    with_fallback = [r for r in results if r.fallback_url is not None]

    print()
    print("=" * 60)
    print(f"  DAWNLY SOURCE VALIDATION — {total} sources")
    print("=" * 60)

    # --- Passed ---
    if passed:
        print(f"\n✓ PASS ({len(passed)})\n")
        for r in sorted(passed, key=lambda x: x.name):
            fallback_note = ""
            if r.fallback_url:
                if r.fallback_ok:
                    fallback_note = f"  [fallback ✓ {r.fallback_articles} art.]"
                else:
                    fallback_note = f"  [fallback ✗ {r.fallback_error}]"
            print(
                f"  {r.name:<35} "
                f"HTTP {r.primary_status}  "
                f"{r.primary_articles:>3} articles"
                f"{fallback_note}"
            )

    # --- Failed ---
    if failed:
        print(f"\n✗ FAIL ({len(failed)})\n")
        for r in sorted(failed, key=lambda x: x.name):
            fallback_note = ""
            if r.fallback_url:
                if r.fallback_ok:
                    fallback_note = (
                        f"\n    → fallback WORKS  "
                        f"HTTP {r.fallback_status}  "
                        f"{r.fallback_articles} articles — "
                        f"update primary URL when ready"
                    )
                else:
                    fallback_note = (
                        f"\n    → fallback also failed: {r.fallback_error}"
                    )
            status_str = f"HTTP {r.primary_status}" if r.primary_status else "no response"
            print(
                f"  {r.name:<35} "
                f"{status_str}  "
                f"{r.primary_error}"
                f"{fallback_note}"
            )

    # --- Summary ---
    print()
    print("-" * 60)
    print(
        f"  {len(passed)}/{total} passed · "
        f"{len(with_fallback)} with fallback URLs · "
        f"completed in {elapsed:.1f}s"
    )
    print("=" * 60)
    print()


# -------------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------------

def main() -> int:
    '''Run validation and return exit code (0 = all pass, 1 = failures).'''
    print(f"\nValidating {len(SOURCES)} sources...")
    start   = time.monotonic()
    results = asyncio.run(validate_all())
    elapsed = time.monotonic() - start

    print_report(results, elapsed)

    failed = [r for r in results if not r.passed]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
