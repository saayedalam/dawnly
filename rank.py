# rank.py
# Purpose: Rank story clusters by global significance using 3 signals:
# 1. Mention count — how many articles cover this story
# 2. Coverage reach weight — how globally reaching are the sources
# 3. Geographic diversity — how many distinct regions covered it

import logging
from collections import Counter

import spacy

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# spaCy model — loaded once and cached
# -------------------------------------------------------------------------

_nlp = None

def get_nlp():
    '''Load the spaCy model once and cache it for reuse.'''
    global _nlp
    if _nlp is None:
        logger.info("Loading spaCy model: en_core_web_sm")
        _nlp = spacy.load("en_core_web_sm")
        logger.info("spaCy model loaded")
    return _nlp


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
    "Financial Times":          0.7,
    "South China Morning Post": 0.7,
    "The Hindu":                0.7,
    "Dawn Pakistan":            0.7,
    "Middle East Eye":          0.7,
    "Sydney Morning Herald":    0.7,
    "Toronto Star":             0.7,
    "The Diplomat":             0.7,
    "Hong Kong Free Press":     0.7,
    "African Arguments":        0.7,
    "Channel NewsAsia":         0.7,
    "Guardian Africa":          0.7,
    "Guardian Americas":        0.7,
    "MercoPress":               0.7,
    "NPR News":                 0.7,

    # Tier C — 0.4
    "Foreign Policy":   0.4,
    "Rest of World":    0.4,
    "ProPublica":       0.4,
    "The Intercept":    0.4,
    "Politico":         0.4,
    "Axios":            0.4,
    "Quartz":           0.4,
    "Balkan Insight":       0.4,
    "Buenos Aires Times":   0.4,
    "The Africa Report":    0.4,
    "The Moscow Times":     0.4,
    "Guardian Russia":      0.4,
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
# NER — cluster-level entity extraction
# -------------------------------------------------------------------------

# Entity label types we care about for topic grouping.
# GPE  = countries, cities, regions (Iran, Gaza, Ukraine)
# NORP = nationalities, religions, groups (Iranians, Hamas, NATO)
# ORG  = organisations (Taliban, EU, Fed)
# PERSON is intentionally excluded — person names are too volatile
# and often refer to actors rather than the subject of the story
# (e.g. "Trump says..." makes the story about Iran, not Trump)
_ENTITY_LABELS = {"GPE", "NORP", "ORG"}

# Entities to ignore — too generic to be meaningful event identifiers.
# These appear in almost every international story and carry no signal.
_IGNORED_ENTITIES = {
    "us", "u.s.", "united states", "america",
    "un", "united nations",
    "eu", "european union",
    "nato",
    "white house", "pentagon", "congress", "senate",
    "government", "parliament", "ministry",
}


def get_cluster_entity(cluster: list[dict]) -> str:
    '''
    Identify the dominant named entity for a story cluster by running NER
    across ALL article titles in the cluster, not just the best headline.

    This is the core of the event-detection approach: two clusters about
    the same underlying crisis (e.g. "Iran supreme leader" and "Hormuz
    blockade") will both have "iran" as their most frequent entity across
    their combined article titles, and will therefore be grouped together
    for quota and big-story purposes.

    Returns the most frequently mentioned qualifying entity (lowercased),
    or "other" if no meaningful entity is found.
    '''
    nlp = get_nlp()
    entity_counts: Counter = Counter()

    for article in cluster:
        title = article.get("title", "")
        if not title:
            continue
        doc = nlp(title)
        for ent in doc.ents:
            if ent.label_ in _ENTITY_LABELS:
                text = ent.text.lower().strip()
                if text not in _IGNORED_ENTITIES and len(text) > 1:
                    entity_counts[text] += 1

    if not entity_counts:
        return "other"

    # Return the single most common entity across all cluster titles
    return entity_counts.most_common(1)[0][0]


# -------------------------------------------------------------------------
# Big story grouping — collapse same-entity clusters into one grouped card
# -------------------------------------------------------------------------

BIG_STORY_THRESHOLD  = 3   # entity must appear this many times to trigger grouping
MAX_ANGLES_PER_GROUP = 3   # max individual story angles to show per grouped card

def group_big_stories(scored: list[dict]) -> list[dict]:
    '''
    Identify entities that appear in 3+ story clusters in the ranked list.
    Merge all clusters for that entity into one grouped story card occupying
    a single slot, freeing up the remaining slots for other stories.

    For example, if Iran appears in clusters ranked #1, #2, #3, #8:
      - All four are merged into one grouped card at position #1
      - Stories #4, #5, #6, #7, #9, #10 move up to fill slots #2–#7
      - Final list has 10 stories with Iran taking only 1 slot

    The grouped story dict has:
      - headline       : top-scoring angle's headline
      - entity         : shared entity
      - is_grouped     : True
      - angles         : list of {headline, articles} for each angle (up to MAX_ANGLES)
      - sources        : combined unique sources across all angles (top 3 by reach)
      - regions        : combined unique regions across all angles
      - score          : top-scoring angle's score
      - mention_count  : total mentions across all angles
      - diversity      : combined unique region count

    Regular (non-grouped) stories have is_grouped: False.
    '''
    # Count entity frequency in the full scored list
    entity_counts = Counter(
        s["entity"] for s in scored
        if s.get("entity", "other") != "other"
    )

    big_entities = {
        entity for entity, count in entity_counts.items()
        if count >= BIG_STORY_THRESHOLD
    }

    if big_entities:
        logger.info(f"  Big story entities detected: {', '.join(sorted(big_entities))}")

    # Separate stories into grouped buckets and remainder
    grouped_buckets: dict[str, list[dict]] = {e: [] for e in big_entities}
    remainder: list[dict] = []

    for story in scored:
        entity = story.get("entity", "other")
        if entity in big_entities:
            grouped_buckets[entity].append(story)
        else:
            remainder.append(story)

    # Build one grouped story dict per big entity
    grouped_stories: list[dict] = []
    for entity, angles in grouped_buckets.items():
        # Already in score order — take top MAX_ANGLES for display
        top_angles   = angles[:MAX_ANGLES_PER_GROUP]
        best         = top_angles[0]  # highest-scoring angle leads

        # Combine regions and sources across all angles
        all_regions  = sorted(set(
            r for a in angles for r in a.get("regions", [])
        ))
        seen_sources = set()
        all_sources  = []
        for a in sorted(angles, key=lambda x: x["score"], reverse=True):
            for s in a.get("sources", []):
                if s["name"] not in seen_sources:
                    all_sources.append(s)
                    seen_sources.add(s["name"])
                if len(all_sources) == 3:
                    break
            if len(all_sources) == 3:
                break

        grouped_stories.append({
            "headline":      best["headline"],
            "entity":        entity,
            "is_grouped":    True,
            "angle_count":   len(angles),
            "angles":        [
                {
                    "headline": a["headline"],
                    "articles": a["articles"],
                }
                for a in top_angles
            ],
            "score":         best["score"],
            "mention_count": sum(a["mention_count"] for a in angles),
            "avg_reach":     best["avg_reach"],
            "diversity":     len(all_regions),
            "regions":       all_regions,
            "sources":       all_sources,
        })

    # Mark regular stories
    for story in remainder:
        story["is_grouped"] = False

    # Merge: grouped stories first (in score order), then remainder
    grouped_stories.sort(key=lambda x: x["score"], reverse=True)
    final = grouped_stories + remainder

    # Trim to TOP_N
    final = final[:TOP_N]

    logger.info(
        f"  After grouping: {len(grouped_stories)} grouped + "
        f"{len(final) - len(grouped_stories)} individual = {len(final)} total"
    )
    return final


# -------------------------------------------------------------------------
# Main ranking function
# -------------------------------------------------------------------------

def rank_clusters(clusters: list[list[dict]]) -> list[dict]:
    '''
    Score and rank all clusters, apply topic quota and big story flagging.
    Returns top N stories as enriched dicts ready for summarization.

    Pipeline:
      1. Score every cluster
      2. Assign a dominant NER entity to each story
      3. Sort by score descending
      4. Apply per-entity quota (max MAX_STORIES_PER_TOPIC per entity)
      5. Flag stories where one entity dominates 3+ slots
    '''
    if not clusters:
        logger.warning("No clusters to rank")
        return []

    scored = []
    for cluster in clusters:
        score   = score_cluster(cluster)
        best    = max(cluster, key=lambda a: get_coverage_reach(a["source_name"]))
        regions = sorted(set(a["source_region"] for a in cluster))

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
            "entity":        get_cluster_entity(cluster),
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

    logger.info(f"Ranked {len(clusters)} clusters — grouping big stories...")

    # Group same-entity clusters into single cards, fill remainder to TOP_N
    final = group_big_stories(scored)

    logger.info(f"Final selection: {len(final)} stories")
    return final


# -------------------------------------------------------------------------
# Summary helper
# -------------------------------------------------------------------------

def print_ranking(stories: list[dict]) -> None:
    '''Print a clean ranking table for inspection.'''
    print(f"\n{'='*70}")
    print(f"DAWNLY TOP {len(stories)} — {__import__('datetime').date.today()}")
    print(f"{'='*70}")

    for i, story in enumerate(stories, 1):
        if story.get("is_grouped"):
            print(f"\n#{i} ★ GROUPED ({story['angle_count']} angles) "
                  f"— entity: {story['entity']} — score: {story['score']}")
            for j, angle in enumerate(story["angles"], 1):
                print(f"   Angle {j}: {angle['headline'][:65]}")
        else:
            print(f"\n#{i} — Score: {story['score']} "
                  f"({story['mention_count']} mentions × "
                  f"{story['avg_reach']} reach × "
                  f"{story['diversity']} regions)")
            print(f"  Entity  : {story.get('entity', 'other')}")
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
