# summarize.py
# Purpose: Generate a clean 2-sentence summary per story using Claude Haiku.
#
# Replaces the previous BART-based approach. BART was receiving only headlines
# as input — not enough signal to summarize from. Claude can infer context
# from headlines and produce consistent, well-formed prose.
#
# Best practices applied:
#   - Prompt caching: system prompt is cached after the first call,
#     reducing input token cost by ~90% for calls 2-10 each run.
#   - Single model load: API client initialized once, reused for all stories.
#   - Graceful fallback: if the API call fails, the best headline is used.
#   - Consistent voice: system prompt enforces Dawnly's tone contract.

import logging
import os

import anthropic

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Config
# -------------------------------------------------------------------------

MODEL          = "claude-haiku-4-5-20251001"
MAX_HEADLINES  = 5       # headlines fed as context per story
MAX_TOKENS     = 120     # output cap — 2 sentences fits comfortably in ~80 tokens
MAX_HEADLINE_TOKENS = 18 # grouped headline — short, punchy, one clause

# System prompt — defines Dawnly's summary voice.
# Cached after the first API call each pipeline run.
SYSTEM_PROMPT = """\
You write two-sentence summaries for Dawnly, a calm global news digest.

Rules:
- Exactly two sentences. No more, no less.
- Present tense, active voice.
- Neutral and factual — no alarm language, no superlatives, no opinion.
- Do not repeat the headline. Add context or detail the headline omits.
- Do not begin with "According to", "Reports say", or similar attribution phrases.
- Do not use the word "meanwhile".
- Write as if informing a thoughtful adult who wants to understand what happened and why it matters.
- Each sentence should be complete and stand on its own.
"""

# System prompt for grouped card headlines — cached separately.
HEADLINE_SYSTEM_PROMPT = """\
You write short, precise headlines for Dawnly, a calm global news digest.

Rules:
- Maximum 10 words.
- Present tense, active voice.
- Neutral — no alarm language, no superlatives, no opinion.
- Capture the overarching story, not just one angle.
- No punctuation at the end.
- Do not start with a proper noun if avoidable — lead with the action or situation.
"""


# -------------------------------------------------------------------------
# API client — initialized once per pipeline run
# -------------------------------------------------------------------------

_client = None


def get_client() -> anthropic.Anthropic:
    """
    Initialize the Anthropic client once and cache it.
    Reads ANTHROPIC_API_KEY from environment.
    """
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Add it to your GitHub Actions secrets."
            )
        _client = anthropic.Anthropic(api_key=api_key)
        logger.info("Anthropic client initialized")
    return _client


# -------------------------------------------------------------------------
# Core summarization function
# -------------------------------------------------------------------------

def summarize_story(story: dict) -> str:
    """
    Generate a 2-sentence summary for a ranked story using Claude Haiku.

    Uses prompt caching on the system prompt — the first call in a pipeline
    run pays full input token cost for the system prompt; all subsequent
    calls read it from cache at ~10% of the standard price.

    Falls back to the best headline if the API call fails.
    """
    # Build input from top headlines sorted by source weight
    articles = sorted(
        story["articles"],
        key=lambda a: a["source_weight"],
        reverse=True,
    )[:MAX_HEADLINES]

    headlines = "\n".join(
        f"- {a['title']}" for a in articles
    )

    user_message = (
        f"Story headline: {story['headline']}\n\n"
        f"Related headlines from other sources:\n{headlines}\n\n"
        f"Write a two-sentence summary."
    )

    try:
        client = get_client()

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {"role": "user", "content": user_message}
            ],
        )

        summary = response.content[0].text.strip()

        # Log cache status for cost monitoring
        usage = response.usage
        cache_read  = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_note  = ""
        if cache_write:
            cache_note = " [cache write]"
        elif cache_read:
            cache_note = " [cache hit]"

        logger.info(f"  ✓ {story['headline'][:50]}...{cache_note}")
        return summary

    except Exception as e:
        logger.error(f"  ✗ Summary failed for '{story['headline'][:50]}': {e}")
        # Fallback — return best headline rather than crashing the pipeline
        best = max(story["articles"], key=lambda a: a["source_weight"])
        return best["title"]


def generate_grouped_headline(story: dict) -> str:
    """
    Generate a single clean headline for a grouped card using Claude Haiku.

    The grouped card currently inherits the headline of its highest-scoring
    angle — a single article's phrasing that often doesn't represent the
    full scope of the story. This replaces it with a headline that captures
    the overarching event across all angles.

    Falls back to the existing headline if the API call fails.
    """
    angles = story.get("angles", [])
    if not angles:
        return story["headline"]

    angle_headlines = "\n".join(
        f"- {a['headline']}" for a in angles
    )
    entity = story.get("entity", "")
    entity_note = f"\nDominant topic: {entity}" if entity and entity != "other" else ""

    user_message = (
        f"These headlines are different angles on the same story:{entity_note}\n\n"
        f"{angle_headlines}\n\n"
        f"Write a single headline (max 10 words) that captures the overarching story."
    )

    try:
        client = get_client()

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_HEADLINE_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": HEADLINE_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {"role": "user", "content": user_message}
            ],
        )

        headline = response.content[0].text.strip().strip('"').strip("'")
        logger.info(f"  ✓ Grouped headline: {headline}")
        return headline

    except Exception as e:
        logger.error(f"  ✗ Grouped headline failed: {e}")
        return story["headline"]




def summarize_all(stories: list[dict]) -> list[dict]:
    """
    Add summaries to each story dict in place.

    Regular stories get a single "summary" field.
    Grouped stories get a "summary" (lead angle) plus a "summaries" list
    with one summary per angle — each angle summarized separately.

    Returns the same list with summary fields added.
    Logs total token usage and estimated cost at the end of each run.
    """
    logger.info(f"Summarizing {len(stories)} stories via Claude Haiku...")

    total_input        = 0
    total_cached       = 0
    total_output       = 0

    def _summarize_and_track(story_dict: dict) -> str:
        '''Wrapper that calls summarize_story and accumulates token usage.'''
        nonlocal total_input, total_cached, total_output
        try:
            client = get_client()
            articles = sorted(
                story_dict["articles"],
                key=lambda a: a["source_weight"],
                reverse=True,
            )[:MAX_HEADLINES]
            headlines = "\n".join(f"- {a['title']}" for a in articles)
            user_message = (
                f"Story headline: {story_dict['headline']}\n\n"
                f"Related headlines from other sources:\n{headlines}\n\n"
                f"Write a two-sentence summary."
            )
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=[{"type": "text", "text": SYSTEM_PROMPT,
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_message}],
            )
            usage       = response.usage
            cache_read  = getattr(usage, "cache_read_input_tokens",    0) or 0
            cache_write = getattr(usage, "cache_creation_input_tokens",0) or 0
            input_toks  = getattr(usage, "input_tokens",               0) or 0
            output_toks = getattr(usage, "output_tokens",              0) or 0

            total_input  += input_toks
            total_cached += cache_read
            total_output += output_toks

            cache_note = ""
            if cache_write: cache_note = " [cache write]"
            elif cache_read: cache_note = " [cache hit]"
            logger.info(f"  ✓ {story_dict['headline'][:50]}...{cache_note}")
            return response.content[0].text.strip()

        except Exception as e:
            logger.error(f"  ✗ Summary failed for '{story_dict['headline'][:50]}': {e}")
            best = max(story_dict["articles"], key=lambda a: a["source_weight"])
            return best["title"]

    for story in stories:
        if story.get("is_grouped"):
            story["headline"] = generate_grouped_headline(story)
            angle_summaries = []
            for angle in story["angles"]:
                angle_summaries.append(_summarize_and_track({
                    "headline": angle["headline"],
                    "articles": angle["articles"],
                }))
            story["summaries"] = angle_summaries
            story["summary"]   = angle_summaries[0] if angle_summaries else story["headline"]
        else:
            story["summary"] = _summarize_and_track(story)

    # Log token usage and estimated cost
    # Haiku pricing: $0.80/M input (cached: $0.08/M), $4.00/M output
    cost_input  = (total_input  * 0.80  / 1_000_000)
    cost_cached = (total_cached * 0.08  / 1_000_000)
    cost_output = (total_output * 4.00  / 1_000_000)
    cost_total  = cost_input + cost_cached + cost_output

    logger.info(
        f"Summarization complete — "
        f"{total_input} input tokens ({total_cached} cached), "
        f"{total_output} output tokens — "
        f"est. ${cost_total:.4f}"
    )
    return stories


# -------------------------------------------------------------------------
# Entry point — run directly to test summarization
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

    articles, health = fetch_all()
    clusters = cluster_articles(articles)
    stories  = rank_clusters(clusters)
    stories  = summarize_all(stories)

    print(f"\n{'='*70}")
    print("DAWNLY SUMMARIES")
    print(f"{'='*70}")
    for i, story in enumerate(stories, 1):
        print(f"\n#{i} {story['headline'][:65]}")
        print(f"    → {story['summary']}")
