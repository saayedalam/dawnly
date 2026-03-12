# summarize.py
# Purpose: Generate one calm, neutral sentence summary per story
# using facebook/bart-large-cnn — free, local, no API required

import logging
from transformers import BartForConditionalGeneration, BartTokenizer

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Config
# -------------------------------------------------------------------------

MODEL         = "facebook/bart-large-cnn"
MAX_HEADLINES = 5       # max headlines to use as input per story
MIN_LENGTH    = 20      # minimum summary length in tokens
MAX_LENGTH    = 60      # maximum summary length in tokens


# -------------------------------------------------------------------------
# Model loader — loads once, reused for all stories
# -------------------------------------------------------------------------

_model     = None
_tokenizer = None


def get_summarizer():
    '''
    Load the BART model and tokenizer once and cache them.
    First run downloads ~1.6GB — cached locally after that.
    '''
    global _model, _tokenizer
    if _model is None:
        logger.info(f"Loading summarization model: {MODEL}")
        logger.info("First run will download ~1.6GB — cached after that...")
        _tokenizer = BartTokenizer.from_pretrained(MODEL)
        _model     = BartForConditionalGeneration.from_pretrained(MODEL)
        logger.info("Model loaded")
    return _model, _tokenizer


# -------------------------------------------------------------------------
# Core function
# -------------------------------------------------------------------------

def summarize_story(story: dict) -> str:
    '''
    Generate a one-sentence summary for a ranked story.
    Concatenates top headlines as input to BART.
    Returns a clean, neutral summary string.
    Falls back to best headline if summarization fails.
    '''
    # Pull top headlines by source weight for context
    articles = sorted(
        story["articles"],
        key=lambda a: a["source_weight"],
        reverse=True
    )[:MAX_HEADLINES]

    # Concatenate headlines into a single input string
    input_text = " ".join(a["title"] for a in articles)

    try:
        model, tokenizer = get_summarizer()

        inputs = tokenizer(
            input_text,
            return_tensors="pt",
            max_length=512,
            truncation=True,
        )

        summary_ids = model.generate(
            inputs["input_ids"],
            min_length=MIN_LENGTH,
            max_length=MAX_LENGTH,
            length_penalty=2.0,
            num_beams=4,
            early_stopping=True,
        )

        summary = tokenizer.decode(
            summary_ids[0],
            skip_special_tokens=True,
        ).strip()

        logger.info(f"  ✓ {story['headline'][:50]}...")
        return summary

    except Exception as e:
        logger.error(f"  ✗ Summary failed: {e}")
        # Fallback — use the best headline as summary
        best = max(story["articles"], key=lambda a: a["source_weight"])
        return best["title"]


# -------------------------------------------------------------------------
# Main function
# -------------------------------------------------------------------------

def summarize_all(stories: list[dict]) -> list[dict]:
    '''
    Add a one-sentence summary to each story dict.
    Returns the same list with summary field added.
    '''
    logger.info(f"Summarizing {len(stories)} stories...")

    for story in stories:
        story["summary"] = summarize_story(story)

    logger.info("Summarization complete")
    return stories


# -------------------------------------------------------------------------
# Entry point — run directly to test
# -------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    from fetch import fetch_all
    from cluster import cluster_articles
    from rank import rank_clusters

    articles = fetch_all()
    clusters = cluster_articles(articles)
    stories  = rank_clusters(clusters)
    stories  = summarize_all(stories)

    print(f"\n{'='*70}")
    print("DAWNLY SUMMARIES")
    print(f"{'='*70}")
    for i, story in enumerate(stories, 1):
        print(f"\n#{i} {story['headline'][:65]}")
        print(f"    → {story['summary']}")
