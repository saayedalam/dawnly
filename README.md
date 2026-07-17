# Dawnly

[![Pipeline](https://github.com/saayedalam/dawnly/actions/workflows/pipeline.yml/badge.svg)](https://github.com/saayedalam/dawnly/actions/workflows/pipeline.yml)
[![Live](https://img.shields.io/badge/live-dawnly.news-c8820a?style=flat&logo=googlechrome&logoColor=white)](https://dawnly.news)
[![Python](https://img.shields.io/badge/python-3.11-3776ab?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Runs Daily](https://img.shields.io/badge/runs-daily-2a2410?style=flat&logo=github-actions&logoColor=white)](https://github.com/saayedalam/dawnly/actions)

**The morning paper, rebuilt for today.**

Dawnly publishes a daily top 10 global news digest ranked by coverage across a curated source set. Each edition remains fixed until the next morning's update. No breaking-news feed. No infinite scroll. No personalization. You read it once. You put it down. You live your day.

→ **[dawnly.news](https://dawnly.news)**

---

## How It Works

Once each morning, a GitHub Actions pipeline runs automatically:

1. **Fetch** — pulls headlines from 50 RSS sources across global, regional, and niche tiers
2. **Cluster** — groups semantically similar articles using sentence-BERT embeddings and DBSCAN
3. **Rank** — scores each story cluster across three signals: mention volume, source quality, and geographic spread
4. **Summarize** — generates a two-sentence summary per story using Claude Haiku, with headline fallback on API failure
5. **Publish** — writes `top10.json` and commits it back to the repo; GitHub Pages serves the frontend

The frontend reads `top10.json` on load. No application server or database is required, and API credentials remain in GitHub Actions secrets rather than being exposed to the browser.

---

## Stack

| Layer | Technology |
|---|---|
| Fetching | `aiohttp`, `feedparser` — async with retry and dedup |
| Clustering | `sentence-transformers` (all-mpnet-base-v2), DBSCAN |
| NER & Grouping | `spaCy` (en_core_web_md) |
| Ranking | Custom scoring — normalized, weighted additive formula |
| Summarization | Claude Haiku API — via Anthropic prompt caching |
| Automation | GitHub Actions — daily cron + manual dispatch |
| Frontend | Vanilla HTML/CSS/JS — newspaper layout, no frameworks |
| Hosting | GitHub Pages |

---

## Project Structure

```
dawnly/
├── fetch.py          # Async RSS fetcher — 50 sources, 24hr window
├── cluster.py        # Sentence-BERT embeddings + DBSCAN clustering
├── rank.py           # Scoring, NER entity detection, big story grouping
├── summarize.py      # Claude Haiku summaries with prompt caching and fallback
├── sources.py        # Master source list — tiers, weights, regions
├── publish.py        # Pipeline orchestrator — runs all steps, writes output
├── source_health.py  # Per-source availability monitoring
├── send_newsletter.py # Daily email edition
├── index.html        # Frontend — newspaper design, card grid, dark/light mode
├── about.html        # Product explanation and methodology
├── top10.json        # Daily output — consumed by the frontend
├── archive/top10/    # Dated production and shadow-clustering outputs
└── .github/
    └── workflows/
        ├── pipeline.yml      # Daily content pipeline
        ├── newsletter.yml    # Daily newsletter delivery
        └── health_report.yml # Weekly source-health report
```

---

## Sources

50 RSS sources across three tiers, covering every major region:

- **Global (6):** BBC, Al Jazeera, The Guardian, NPR, Deutsche Welle, NHK World
- **Regional (21):** Major outlets across North America, Europe, Asia, Africa, the Middle East, South America, and Oceania
- **Niche (23):** Specialist and regional outlets covering underrepresented geographies and topics

---

## Design Philosophy

- **One edition a day.** Nothing in between.
- **No personalization.** Everyone sees the same 10 stories.
- **Calm by default.** No breaking news alerts, no push notifications, no doomscroll.
- **Coverage drives the edition.** Rankings use mention volume, source reach, and geographic spread — not reader engagement or clicks.

---

## Interpretation & Limitations

- Rankings measure coverage within Dawnly's selected RSS sources; they do not measure objective importance, truth, or the full global news landscape.
- Source selection, reach weights, clustering thresholds, and ranking rules are human design decisions and may introduce bias.
- Summaries are AI-generated from source headlines and may omit context or contain errors. Each story links to its cited sources for verification.
- RSS availability varies by publisher, so the articles available to a given edition can change from day to day.

---

## Status

- **Edition 1** launched March 12, 2026
- The production pipeline runs automatically each day and publishes dated archive outputs
- Ranking algorithm: v2 (weighted additive, log-scaled, normalized per-signal)
- Grouping: major stories spanning multiple clusters collapse into a single card

---

*Built by [Saayed Alam](https://saayedalam.me)*
