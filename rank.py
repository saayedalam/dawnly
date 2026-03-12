# rank.py
# Purpose: Rank story clusters by global significance using 3 signals:
# 1. Mention count — how many articles cover this story
# 2. Coverage reach weight — how globally reaching are the sources
# 3. Geographic diversity — how many distinct regions covered it

import logging
from collections import Counter

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Config
# -------------------------------------------------------------------------

# Coverage reach weights per source tier
# These are separate from the source tier weights in sources.py
# Tier A = truly global outlets covering all regions equally
# Tier B = strong international but regionally anchored
# Tier C = specialist/niche with global focus

COVERAGE_REACH = {
    # Tier A — 1.0
    "BBC News":             1.0,
    "Associated Press":     1.0,
    "Al Jazeera English":   1.0,
    "Deutsche Welle":       1.0,
    "France 24":            1.0,
    "NHK World Japan":      1.0,

    # Tier B — 0.7
    "The New York Times":       0.7,
    "The Washington Post":      0.7,
    "The Guardian":             0.7,
    "Wall Street Journal":      0.7,
    "Financial Times":          0.7,
    "South China Morning Post": 0.7,
    "The Hindu":                0.7,
    "Dawn Pakistan":            0.7,
    "Middle East Eye":          0.7,
    "Sydney Morning Herald":    0.7,
    "Toronto Star":             0.7,
    "CBC News":                 0.7,
    "Globe and Mail":           0.7,
    "The Diplomat":             0.7,
    "Hong Kong Free Press":     0.7,
    "African Arguments":        0.7,
    "Southeast Asia Globe":     0.7,
    "NPR News":                 0.7,

    # Tier C — 0.4
    "Foreign Policy":   0.4,
    "Rest of World":    0.4,
    "ProPublica":       0.4,
    "The Intercept":    0.4,
    "Politico":         0.4,
    "Axios":            0.4,
    "Quartz":           0.4,
}

DEFAULT_REACH = 0.4     # fallback for any source not in the list
TOP_N        = 10       # number of stories to return


# -------------------------------------------------------------------------
# Scoring functions
# -------------------------------------------------------------------------

def get_coverage_reach(source_name: str) -> float:
    '''Return the coverage reach weight for a given source name.'''
    return COVERAGE_REACH.get(source_name, DEFAULT_REACH)


def geographic_diversity_score(cluster: list[dict]) -> int:
    '''
    Count the number of distinct regions covering this story.
    More regions = more globally significant.
    '''
    regions = set(a["source_region"] for a in cluster)
    return len(regions)


def average_coverage_reach(cluster: list[dict]) -> float:
    '''
    Calculate the average coverage reach weight across all
    articles in the cluster.
    '''
    reaches = [get_coverage_reach(a["source_name"]) for a in cluster]
    return sum(reaches) / len(reaches)


def score_cluster(cluster: list[dict]) -> float:
    '''
    Calculate the final score for a story cluster using 3 signals:

    SCORE = mention_count x avg_coverage_reach x geographic_diversity

    - mention_count       : total articles in cluster
    - avg_coverage_reach  : how globally reaching the sources are
    - geographic_diversity: how many distinct regions covered it
    '''
    mention_count        = len(cluster)
    avg_reach            = average_coverage_reach(cluster)
    diversity            = geographic_diversity_score(cluster)

    score = mention_count * avg_reach * diversity
    return round(score, 4)


# -------------------------------------------------------------------------
# Main ranking function
# -------------------------------------------------------------------------

def rank_clusters(clusters: list[list[dict]]) -> list[dict]:
    '''
    Score and rank all clusters, return top N as enriched story dicts.
    Each story dict contains the cluster articles plus scoring metadata.
    '''
    if not clusters:
        logger.warning("No clusters to rank")
        return []

    scored = []
    for cluster in clusters:
        score       = score_cluster(cluster)
        best        = max(cluster, key=lambda a: get_coverage_reach(a["source_name"]))
        sources     = sorted(
                        set(a["source_name"] for a in cluster),
                        key=lambda s: get_coverage_reach(s),
                        reverse=True
                      )
        regions     = sorted(set(a["source_region"] for a in cluster))

        # Top 3 sources by coverage reach for display
        top_sources = []
        seen        = set()
        for a in sorted(cluster, key=lambda x: get_coverage_reach(x["source_name"]), reverse=True):
            if a["source_name"] not in seen:
                top_sources.append({
                    "name": a["source_name"],
                    "link": a["link"],
                })
                seen.add(a["source_name"])
            if len(top_sources) == 3:
                break

        scored.append({
            "headline":      best["title"],
            "score":         score,
            "mention_count": len(cluster),
            "avg_reach":     round(average_coverage_reach(cluster), 4),
            "diversity":     geographic_diversity_score(cluster),
            "regions":       regions,
            "sources":       top_sources,
            "articles":      cluster,
        })

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)

    top = scored[:TOP_N]
    logger.info(f"Ranked {len(clusters)} clusters — returning top {len(top)}")
    return top


# -------------------------------------------------------------------------
# Summary helper
# -------------------------------------------------------------------------

def print_ranking(stories: list[dict]) -> None:
    '''Print a clean ranking table for inspection.'''
    print(f"\n{'='*70}")
    print(f"DAWNLY TOP {len(stories)} — {__import__('datetime').date.today()}")
    print(f"{'='*70}")

    for i, story in enumerate(stories, 1):
        print(f"\n#{i} — Score: {story['score']} "
              f"({story['mention_count']} mentions × "
              f"{story['avg_reach']} reach × "
              f"{story['diversity']} regions)")
        print(f"  {story['headline'][:75]}")
        print(f"  Regions : {', '.join(story['regions'])}")
        print(f"  Sources : {', '.join(s['name'] for s in story['sources'])}")


# -------------------------------------------------------------------------
# Entry point — run directly to test ranking
# -------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    from fetch import fetch_all
    from cluster import cluster_articles

    articles = fetch_all()
    clusters = cluster_articles(articles)
    stories  = rank_clusters(clusters)

    print_ranking(stories)
