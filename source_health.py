# source_health.py
# Purpose: Log daily per-source fetch health to source_health.json.
#
# Runs once per pipeline cycle (called from publish.py).
# Maintains a rolling 60-day history per source so trends are visible
# over time — which sources are consistently empty, erroring, or healthy.
#
# Output: source_health.json (written to OUTPUT_PATH, deployed to public repo
# alongside top10.json so it's accessible via GitHub Pages).

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Config
# -------------------------------------------------------------------------

OUTPUT_PATH   = Path("source_health.json")
RETENTION_DAYS = 60   # rolling window — entries older than this are pruned


# -------------------------------------------------------------------------
# Core update function
# -------------------------------------------------------------------------

def update_health_log(source_health: list[dict]) -> None:
    '''
    Merge today's per-source fetch results into the rolling health log.

    source_health is a list of dicts produced by fetch.fetch_all(), one
    per source, each containing:
      name, tier, region, articles_fetched, undated_count, status, error

    The health log is keyed by source name. Each source stores parallel
    arrays (one entry per day) for: dates, articles, undated, status, errors.
    Entries older than RETENTION_DAYS are pruned on each write.
    '''
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    ).strftime("%Y-%m-%d")

    # Load existing log if present
    existing: dict = {}
    if OUTPUT_PATH.exists():
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read existing health log — starting fresh: {e}")

    sources_log: dict = existing.get("sources", {})

    for record in source_health:
        name = record["name"]

        if name not in sources_log:
            sources_log[name] = {
                "tier":     record["tier"],
                "region":   record["region"],
                "dates":    [],
                "articles": [],
                "undated":  [],
                "status":   [],
                "errors":   [],
            }

        entry = sources_log[name]

        # Avoid duplicate entries for the same day (idempotent on re-run)
        if today in entry["dates"]:
            idx = entry["dates"].index(today)
            entry["articles"][idx] = record["articles_fetched"]
            entry["undated"][idx]  = record["undated_count"]
            entry["status"][idx]   = record["status"]
            entry["errors"][idx]   = record["error"]
        else:
            entry["dates"].append(today)
            entry["articles"].append(record["articles_fetched"])
            entry["undated"].append(record["undated_count"])
            entry["status"].append(record["status"])
            entry["errors"].append(record["error"])

        # Prune entries older than retention window
        pruned_indices = [
            i for i, d in enumerate(entry["dates"]) if d >= cutoff
        ]
        entry["dates"]    = [entry["dates"][i]    for i in pruned_indices]
        entry["articles"] = [entry["articles"][i] for i in pruned_indices]
        entry["undated"]  = [entry["undated"][i]  for i in pruned_indices]
        entry["status"]   = [entry["status"][i]   for i in pruned_indices]
        entry["errors"]   = [entry["errors"][i]   for i in pruned_indices]

        # Keep tier/region current in case sources.py is updated
        entry["tier"]   = record["tier"]
        entry["region"] = record["region"]

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "retention_days": RETENTION_DAYS,
        "source_count": len(sources_log),
        "sources": sources_log,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    _log_summary(source_health, today)


# -------------------------------------------------------------------------
# Summary logger
# -------------------------------------------------------------------------

def _log_summary(source_health: list[dict], date: str) -> None:
    '''Log a concise health summary to the pipeline log after each run.'''
    ok     = [s for s in source_health if s["status"] == "ok"]
    empty  = [s for s in source_health if s["status"] == "empty"]
    errors = [s for s in source_health if s["status"] == "error"]

    logger.info(
        f"\nSource health — {date}: "
        f"{len(ok)} ok · {len(empty)} empty · {len(errors)} error"
    )

    if empty:
        logger.warning(
            "  Empty feeds: " + ", ".join(s["name"] for s in empty)
        )
    if errors:
        logger.error(
            "  Failed feeds: " + ", ".join(s["name"] for s in errors)
        )

    if ok:
        top = sorted(ok, key=lambda s: s["articles_fetched"], reverse=True)[:5]
        logger.info(
            "  Top sources: "
            + ", ".join(f"{s['name']} ({s['articles_fetched']})" for s in top)
        )


# -------------------------------------------------------------------------
# Entry point — run directly to inspect current log
# -------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if not OUTPUT_PATH.exists():
        print("No source_health.json found. Run the pipeline first.")
        sys.exit(0)

    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"\nSource Health Log — last updated: {data['last_updated']}")
    print(f"Retention: {data['retention_days']} days  |  Sources tracked: {data['source_count']}")
    print("=" * 70)

    for name, entry in sorted(data["sources"].items()):
        dates    = entry["dates"]
        articles = entry["articles"]
        statuses = entry["status"]

        if not dates:
            continue

        days_tracked  = len(dates)
        ok_days       = statuses.count("ok")
        error_days    = statuses.count("error")
        empty_days    = statuses.count("empty")
        avg_articles  = round(sum(articles) / days_tracked, 1) if days_tracked else 0
        latest_status = statuses[-1] if statuses else "—"
        latest_count  = articles[-1] if articles else 0

        status_icon = {"ok": "✓", "empty": "○", "error": "✗"}.get(latest_status, "?")

        print(
            f"  {status_icon} {name:<35} "
            f"today: {latest_count:>3} art  "
            f"avg: {avg_articles:>5}  "
            f"ok:{ok_days:>3}d  err:{error_days:>3}d  "
            f"[{entry['tier']:<8} {entry['region']}]"
        )

    print("=" * 70)
