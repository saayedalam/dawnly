# publish.py
# Purpose: Run the full Dawnly pipeline and publish top10.json
# This is the master script that orchestrates all pipeline steps

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Config
# -------------------------------------------------------------------------

OUTPUT_FILE    = "top10.json"
ARCHIVE_DIR    = "archive/top10"
MIN_STORIES    = 10     # minimum stories required to publish


# -------------------------------------------------------------------------
# Output builder
# -------------------------------------------------------------------------

def build_output(stories: list[dict]) -> dict:
    '''
    Build the final top10.json structure from ranked + summarized stories.
    Handles both grouped stories (is_grouped=True) and regular stories.
    Strips internal pipeline data — only keeps what the frontend needs.
    '''
    published_at = datetime.now(timezone.utc).isoformat()

    items = []
    for i, story in enumerate(stories, 1):
        if story.get("is_grouped"):
            items.append({
                "rank":        i,
                "headline":    story["headline"],
                "summary":     story["summary"],
                "is_grouped":  True,
                "angle_count": story["angle_count"],
                "angles": [
                    {
                        "headline": angle["headline"],
                        "summary":  story["summaries"][j]
                                    if j < len(story.get("summaries", []))
                                    else angle["headline"],
                    }
                    for j, angle in enumerate(story["angles"])
                ],
                "sources":      story["sources"],
                "source_count": story.get("source_count", len(story["sources"])),
                "regions":      story["regions"],
                "score":        story["score"],
                "mentions":     story["mention_count"],
                "diversity":    story["diversity"],
            })
        else:
            items.append({
                "rank":        i,
                "headline":    story["headline"],
                "summary":     story["summary"],
                "is_grouped":  False,
                "angle_count": 1,
                "angles":      [],
                "sources":      story["sources"],
                "source_count": story.get("source_count", len(story["sources"])),
                "regions":      story["regions"],
                "score":        story["score"],
                "mentions":     story["mention_count"],
                "diversity":    story["diversity"],
            })

    return {
        "published_at":  published_at,
        "story_count":   len(items),
        "stories":       items,
    }


# -------------------------------------------------------------------------
# File writers
# -------------------------------------------------------------------------

def write_output(data: dict) -> None:
    '''
    Write top10.json to the repo root for the frontend to consume.
    '''
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Published {data['story_count']} stories to {OUTPUT_FILE}")


def archive_output(data: dict) -> None:
    '''
    Save a dated copy of top10.json to archive/top10/YYYY-MM-DD.json.
    Creates the archive directory if it does not exist.
    Skips archiving if the file for today already exists.
    '''
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    archive_path = os.path.join(ARCHIVE_DIR, f"{date_str}.json")

    if os.path.exists(archive_path):
        logger.info(f"Archive already exists for {date_str} — skipping")
        return

    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Archived to {archive_path}")


def archive_hdbscan_output(data: dict) -> None:
    '''
    Save the HDBSCAN shadow run output to archive/top10/YYYY-MM-DD_hdbscan.json.
    Used for side-by-side comparison with the production DBSCAN output.
    Never touches the live top10.json or the production archive entry.
    '''
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    archive_path = os.path.join(ARCHIVE_DIR, f"{date_str}_hdbscan.json")

    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"HDBSCAN shadow output archived to {archive_path}")


# -------------------------------------------------------------------------
# Main pipeline orchestrator
# -------------------------------------------------------------------------

def run_pipeline() -> None:
    '''
    Run the full Dawnly pipeline:
    fetch → cluster → rank → summarize → publish → archive → health log
    '''
    from fetch import fetch_all
    from cluster import cluster_articles
    from rank import rank_clusters
    from summarize import summarize_all
    from source_health import update_health_log

    logger.info("=" * 60)
    logger.info("DAWNLY PIPELINE STARTING")
    logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 60)

    # Step 1 — Fetch
    logger.info("\n[1/5] Fetching articles...")
    articles, source_health = fetch_all()
    logger.info(f"Fetched {len(articles)} articles")

    # Step 2 — Cluster
    logger.info("\n[2/5] Clustering articles...")
    clusters = cluster_articles(articles)
    logger.info(f"Found {len(clusters)} qualified clusters")

    # Step 3 — Rank
    logger.info("\n[3/5] Ranking clusters...")
    stories = rank_clusters(clusters)
    logger.info(f"Ranked top {len(stories)} stories")

    # Step 4 — Summarize
    logger.info("\n[4/5] Summarizing stories...")
    stories = summarize_all(stories)

    # Safety check — warn if fewer than minimum stories
    if len(stories) < MIN_STORIES:
        logger.warning(
            f"Only {len(stories)} stories produced — "
            f"minimum is {MIN_STORIES}. Publishing with fewer stories."
        )

    # Build, write, and archive output
    output = build_output(stories)
    write_output(output)
    archive_output(output)

    # Step 5 — Source health log
    logger.info("\n[5/5] Updating source health log...")
    update_health_log(source_health)

    # Shadow — HDBSCAN comparison run (non-fatal, no API cost)
    run_shadow_hdbscan(articles)

    logger.info("\n" + "=" * 60)
    logger.info("DAWNLY PIPELINE COMPLETE")
    logger.info(f"Published at: {output['published_at']}")
    logger.info(f"Stories: {output['story_count']}")
    logger.info("=" * 60)


def run_shadow_hdbscan(articles: list[dict]) -> None:
    '''
    Run the HDBSCAN shadow pipeline on already-fetched articles.
    Does not summarize (no API cost) — headline and cluster structure only.
    Output goes to archive/top10/YYYY-MM-DD_hdbscan.json for manual comparison.
    Never affects the live site or production output.
    '''
    from cluster import cluster_articles_hdbscan
    from rank import rank_clusters

    logger.info("\n[Shadow] Running HDBSCAN comparison pipeline...")

    try:
        clusters = cluster_articles_hdbscan(articles)
        logger.info(f"[Shadow] HDBSCAN: {len(clusters)} qualified clusters")

        stories = rank_clusters(clusters)
        logger.info(f"[Shadow] Ranked {len(stories)} stories")

        # Build lightweight output — no summaries, just structure for comparison
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        items = []
        for i, story in enumerate(stories, 1):
            items.append({
                "rank":        i,
                "headline":    story["headline"],
                "is_grouped":  story.get("is_grouped", False),
                "angle_count": story.get("angle_count", 1),
                "angles":      [{"headline": a["headline"]} for a in story.get("angles", [])],
                "sources":     story["sources"],
                "source_count": story.get("source_count", len(story["sources"])),
                "regions":     story["regions"],
                "score":       story["score"],
                "mentions":    story["mention_count"],
                "diversity":   story["diversity"],
            })

        shadow_output = {
            "published_at": datetime.now(timezone.utc).isoformat(),
            "algorithm":    "hdbscan",
            "story_count":  len(items),
            "stories":      items,
        }

        archive_hdbscan_output(shadow_output)
        logger.info("[Shadow] HDBSCAN shadow run complete")

    except Exception as e:
        # Shadow pipeline must never crash the main pipeline
        logger.warning(f"[Shadow] HDBSCAN shadow run failed (non-fatal): {e}")


# -------------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    run_pipeline()

    # Preview the output
    with open(OUTPUT_FILE, "r") as f:
        data = json.load(f)

    print(f"\n{'='*60}")
    print(f"top10.json preview — {data['published_at']}")
    print(f"{'='*60}")
    for story in data["stories"]:
        print(f"\n#{story['rank']} {story['headline'][:65]}")
        print(f"   {story['summary'][:80]}")
        print(f"   Sources: {', '.join(s['name'] for s in story['sources'])}")
