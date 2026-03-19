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
BACKUP_FILE    = "top10.backup.json"
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
                "sources":   story["sources"],
                "regions":   story["regions"],
                "score":     story["score"],
                "mentions":  story["mention_count"],
                "diversity": story["diversity"],
            })
        else:
            items.append({
                "rank":        i,
                "headline":    story["headline"],
                "summary":     story["summary"],
                "is_grouped":  False,
                "angle_count": 1,
                "angles":      [],
                "sources":     story["sources"],
                "regions":     story["regions"],
                "score":       story["score"],
                "mentions":    story["mention_count"],
                "diversity":   story["diversity"],
            })

    return {
        "published_at":  published_at,
        "story_count":   len(items),
        "stories":       items,
    }


# -------------------------------------------------------------------------
# File writer with fallback protection
# -------------------------------------------------------------------------

def write_output(data: dict) -> None:
    '''
    Write top10.json safely.
    Backs up the previous version before overwriting.
    If writing fails, the backup is preserved.
    '''
    # Back up previous output if it exists
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r") as f:
                previous = f.read()
            with open(BACKUP_FILE, "w") as f:
                f.write(previous)
            logger.info(f"Previous output backed up to {BACKUP_FILE}")
        except Exception as e:
            logger.warning(f"Could not back up previous output: {e}")

    # Write new output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Published {data['story_count']} stories to {OUTPUT_FILE}")


def load_backup() -> dict | None:
    '''
    Load the backup top10.json if it exists.
    Used as fallback when the pipeline produces insufficient stories.
    '''
    if os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, "r") as f:
            return json.load(f)
    return None


# -------------------------------------------------------------------------
# Main pipeline orchestrator
# -------------------------------------------------------------------------

def run_pipeline() -> None:
    '''
    Run the full Dawnly pipeline:
    fetch → cluster → rank → summarize → publish → health log
    Falls back to previous output if pipeline produces insufficient stories.
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

    # Safety check — fallback if not enough stories
    if len(stories) < MIN_STORIES:
        logger.warning(
            f"Only {len(stories)} stories produced — "
            f"minimum is {MIN_STORIES}. Checking for backup..."
        )
        backup = load_backup()
        if backup:
            logger.warning("Using previous top10.json as fallback")
        else:
            logger.warning("No backup available — publishing with fewer stories")

    # Build and write output
    output = build_output(stories)
    write_output(output)

    # Step 5 — Source health log
    logger.info("\n[5/5] Updating source health log...")
    update_health_log(source_health)

    logger.info("\n" + "=" * 60)
    logger.info("DAWNLY PIPELINE COMPLETE")
    logger.info(f"Published at: {output['published_at']}")
    logger.info(f"Stories: {output['story_count']}")
    logger.info("=" * 60)


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
