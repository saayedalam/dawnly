# cluster.py
# Purpose: Cluster semantically similar news headlines into story groups
# using Sentence-BERT embeddings and DBSCAN

import numpy as np
import logging
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import normalize

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Config
# -------------------------------------------------------------------------

EMBEDDING_MODEL    = "all-mpnet-base-v2"   # higher quality embeddings, 768-dim
DBSCAN_EPS         = 0.35                 # similarity threshold (lower = tighter clusters)
DBSCAN_MIN_SAMPLES = 2                    # minimum articles to form a cluster
MIN_SOURCES        = 3                    # minimum unique sources to qualify for top 10


# -------------------------------------------------------------------------
# Core functions
# -------------------------------------------------------------------------

def embed_headlines(articles: list[dict]) -> np.ndarray:
    '''
    Generate sentence embeddings for all articles.
    Uses title + description when available for richer semantic signal.
    Falls back to title alone when description is absent or empty.
    Returns a normalized numpy array of shape (n_articles, embedding_dim).
    '''
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    texts = []
    desc_count = 0
    for a in articles:
        desc = a.get("description", "").strip()
        if desc:
            texts.append(f"{a['title']}. {desc}")
            desc_count += 1
        else:
            texts.append(a["title"])

    logger.info(
        f"Embedding {len(texts)} articles "
        f"({desc_count} with description, "
        f"{len(texts) - desc_count} title-only)..."
    )

    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    # Normalize so cosine similarity works correctly with DBSCAN
    embeddings = normalize(embeddings)
    logger.info("Embeddings complete")
    return embeddings


def cluster_articles(articles: list[dict]) -> list[list[dict]]:
    '''
    Cluster articles into story groups using DBSCAN on headline embeddings.
    Returns a list of clusters, each cluster being a list of article dicts.
    Only returns clusters with at least MIN_SOURCES unique sources.
    '''
    if not articles:
        logger.warning("No articles to cluster")
        return []

    # Step 1 — embed headlines
    embeddings = embed_headlines(articles)

    # Step 2 — run DBSCAN
    # metric=cosine works well for normalized text embeddings
    logger.info("Running DBSCAN clustering...")
    db = DBSCAN(
        eps=DBSCAN_EPS,
        min_samples=DBSCAN_MIN_SAMPLES,
        metric="cosine",
        n_jobs=-1,
    ).fit(embeddings)

    labels = db.labels_

    # Step 3 — group articles by cluster label
    # label -1 means noise (no cluster) — discard these
    clusters = {}
    for i, label in enumerate(labels):
        if label == -1:
            continue
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(articles[i])

    logger.info(f"Found {len(clusters)} raw clusters")

    # Step 4 — filter clusters by minimum unique source count
    qualified = []
    for label, cluster_articles in clusters.items():
        unique_sources = set(a["source_name"] for a in cluster_articles)
        if len(unique_sources) >= MIN_SOURCES:
            qualified.append(cluster_articles)

    logger.info(
        f"{len(qualified)} clusters qualify "
        f"(>= {MIN_SOURCES} unique sources)"
    )

    return qualified


# -------------------------------------------------------------------------
# Summary helper
# -------------------------------------------------------------------------

def print_cluster_summary(clusters: list[list[dict]]) -> None:
    '''Print a summary of each cluster for inspection.'''
    print(f"\n{'='*60}")
    print(f"CLUSTER SUMMARY — {len(clusters)} story clusters")
    print(f"{'='*60}")

    for i, cluster in enumerate(clusters, 1):
        sources  = set(a["source_name"]   for a in cluster)
        regions  = set(a["source_region"] for a in cluster)
        # Show the headline from the highest weight source
        best     = max(cluster, key=lambda a: a["source_weight"])

        print(f"\nCluster {i:>2} — {len(cluster)} articles, "
              f"{len(sources)} sources, {len(regions)} regions")
        print(f"  Best headline : {best['title'][:80]}")
        print(f"  Sources       : {', '.join(list(sources)[:4])}"
              f"{'...' if len(sources) > 4 else ''}")
        print(f"  Regions       : {', '.join(regions)}")


# -------------------------------------------------------------------------
# Entry point — run directly to test clustering
# -------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    from fetch import fetch_all

    logger.info("Fetching articles...")
    articles = fetch_all()

    logger.info("Clustering articles...")
    clusters = cluster_articles(articles)

    print_cluster_summary(clusters)
