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
# NER — entity extraction
# -------------------------------------------------------------------------

# Entity label types we care about for topic grouping
_ENTITY_LABELS = {"GPE", "ORG", "NORP", "PERSON"}

# Entities to ignore — too generic to be meaningful topic identifiers
_IGNORED_ENTITIES = {
    "us", "u.s.", "united states", "un", "united nations",
    "eu", "european union", "nato", "white house",
}

def get_story_entity(headline: str) -> str:
    '''
    Extract the dominant named entity from a headline using spaCy NER.
    Returns the first GPE/ORG/NORP/PERSON entity found (lowercased),
    skipping generic geopolitical terms that aren't useful topic identifiers.
    Falls back to "other" if no meaningful entity is found.
    '''
    nlp = get_nlp()
    doc = nlp(headline)

    for ent in doc.ents:
        if ent.label_ in _ENTITY_LABELS:
            text = ent.text.lower().strip()
            if text not in _IGNORED_ENTITIES and len(text) > 1:
                return text

    return "other"


# -------------------------------------------------------------------------
# Topic quota — max N stories per entity in the final top 10
# -------------------------------------------------------------------------

MAX_STORIES_PER_TOPIC = 3   # max slots any single entity can occupy

def apply_topic_quota(
    stories: list[dict],
    max_per_topic: int = MAX_STORIES_PER_TOPIC,
) -> list[dict]:
    '''
    Enforce a per-entity quota on the ranked story list.
    Stories are processed in score order (best first).
    Once an entity hits the quota, further stories with that entity
    are skipped and replaced by the next highest-scoring story
    from a different entity.
    Returns a list of up to TOP_N stories with quota applied.
    '''
    entity_counts: dict[str, int] = {}
    filtered: list[dict] = []

    for story in stories:
        entity = story.get("entity", "other")
        count  = entity_counts.get(entity, 0)

        if entity == "other" or count < max_per_topic:
            filtered.append(story)
            entity_counts[entity] = count + 1
        else:
            logger.info(
                f"  Topic quota: skipping '{story['headline'][:55]}...' "
                f"(entity='{entity}', count={count + 1})"
            )

        if len(filtered) == TOP_N:
            break

    return filtered


# -------------------------------------------------------------------------
# Big story flag — mark stories where one entity dominates 3+ slots
# -------------------------------------------------------------------------

BIG_STORY_THRESHOLD = 3     # entity must appear this many times to be flagged
MAX_RELATED_HEADLINES = 2   # number of related headlines to show on card back

def flag_big_stories(stories: list[dict]) -> list[dict]:
    '''
    Identify entities that appear in 3 or more story slots in the final list.
    For each such entity, flag all its stories with big_story=True and attach
    a list of related headlines from the other stories sharing that entity.
    Stories with entity "other" are never flagged.
    '''
    # Count how many slots each entity occupies
    entity_counts = Counter(
        s["entity"] for s in stories
        if s.get("entity", "other") != "other"
    )

    big_entities = {
        entity for entity, count in entity_counts.items()
        if count >= BIG_STORY_THRESHOLD
    }

    if big_entities:
        logger.info(f"  Big story entities: {', '.join(sorted(big_entities))}")

    for story in stories:
        entity = story.get("entity", "other")
        if entity in big_entities:
            # Collect headlines from other stories with the same entity
            related = [
                s["headline"] for s in stories
                if s.get("entity") == entity and s["headline"] != story["headline"]
            ][:MAX_RELATED_HEADLINES]

            story["big_story"]        = True
            story["related_headlines"] = related
        else:
            story["big_story"]        = False
            story["related_headlines"] = []

    return stories


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
            "entity":        get_story_entity(best["title"]),
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

    logger.info(f"Ranked {len(clusters)} clusters — applying topic quota...")

    # Apply per-entity quota then flag big stories
    top = apply_topic_quota(scored)
    top = flag_big_stories(top)

    logger.info(f"Final selection: {len(top)} stories")
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
        big_flag = " ★ BIG STORY" if story.get("big_story") else ""
        print(f"\n#{i} — Score: {story['score']} "
              f"({story['mention_count']} mentions × "
              f"{story['avg_reach']} reach × "
              f"{story['diversity']} regions)"
              f"{big_flag}")
        print(f"  Entity  : {story.get('entity', 'other')}")
        print(f"  {story['headline'][:75]}")
        print(f"  Regions : {', '.join(story['regions'])}")
        print(f"  Sources : {', '.join(s['name'] for s in story['sources'])}")
        if story.get("related_headlines"):
            for rh in story["related_headlines"]:
                print(f"  Related : {rh[:70]}")


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
