# Dawnly

[![Pipeline](https://github.com/saayedalam/dawnly/actions/workflows/pipeline.yml/badge.svg)](https://github.com/saayedalam/dawnly/actions/workflows/pipeline.yml)
[![Live](https://img.shields.io/badge/live-dawnly.news-c8820a?style=flat&logo=googlechrome&logoColor=white)](https://saayedalam.me/dawnly)
[![Python](https://img.shields.io/badge/python-3.11-3776ab?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Runs Daily](https://img.shields.io/badge/runs-daily%206AM%20EST-2a2410?style=flat&logo=github-actions&logoColor=white)](https://github.com/saayedalam/dawnly/actions)

**The morning paper, rebuilt for today.**

Dawnly publishes a daily top 10 global news digest — algorithmically ranked, locked for 24 hours, reset at 6AM EST. No breaking news. No infinite scroll. No personalization. You read it once. You put it down. You live your day.

→ **[dawnly.news](https://saayedalam.me/dawnly)**

---

## How It Works

Every morning at 6AM EST, a GitHub Actions pipeline runs automatically:

1. **Fetch** — pulls headlines from 33 RSS sources across global, regional, and niche tiers
2. **Cluster** — groups semantically similar articles using sentence-BERT embeddings and DBSCAN
3. **Rank** — scores each story cluster across three signals: mention volume, source quality, and geographic spread
4. **Summarize** — generates a one-sentence summary per story using a local BART model
5. **Publish** — writes `top10.json` and commits it back to the repo; GitHub Pages serves the frontend

The frontend reads `top10.json` on load. No server. No database. No API keys in production.

---

## Stack

| Layer | Technology |
|---|---|
| Fetching | `aiohttp`, `feedparser` — async with retry and dedup |
| Clustering | `sentence-transformers` (all-MiniLM-L6-v2), DBSCAN |
| NER & Grouping | `spaCy` (en_core_web_sm) |
| Ranking | Custom scoring — normalized, weighted additive formula |
| Summarization | `facebook/bart-large-cnn` — runs locally, no API |
| Automation | GitHub Actions — daily cron + manual dispatch |
| Frontend | Vanilla HTML/CSS/JS — newspaper layout, no frameworks |
| Hosting | GitHub Pages |

---

## Project Structure

```
dawnly/
├── fetch.py          # Async RSS fetcher — 33 sources, 24hr window
├── cluster.py        # Sentence-BERT embeddings + DBSCAN clustering
├── rank.py           # Scoring, NER entity detection, big story grouping
├── summarize.py      # BART summarization (local model)
├── sources.py        # Master source list — tiers, weights, regions
├── publish.py        # Pipeline orchestrator — runs all steps, writes output
├── index.html        # Frontend — newspaper design, card grid, dark/light mode
├── top10.json        # Daily output — consumed by the frontend
└── .github/
    └── workflows/
        └── pipeline.yml  # Daily automation — 6AM EST
```

---

## Sources

33 RSS sources across three tiers, covering every major region:

- **Global (7):** BBC, Al Jazeera, The Guardian, NPR, Deutsche Welle, France 24, NHK World
- **Regional (15):** NYT, FT, SCMP, The Hindu, Dawn, The Diplomat, Middle East Eye, Sydney Morning Herald, Toronto Star, African Arguments, CNA, Guardian Africa, Guardian Americas, MercoPress, Hong Kong Free Press
- **Niche (11):** Foreign Policy, ProPublica, Politico, Rest of World, The Intercept, Quartz, Balkan Insight, Buenos Aires Times, The Africa Report, The Moscow Times, Guardian Russia

---

## Design Philosophy

- **One edition a day.** Nothing in between.
- **No personalization.** Everyone sees the same 10 stories.
- **Calm by default.** No breaking news alerts, no push notifications, no doomscroll.
- **The algorithm is the editor.** Rankings are determined by cross-source coverage, source quality, and geographic reach — not engagement or clicks.

---

## Status

- **Edition 1** launched March 12, 2026
- Pipeline has run successfully every day since launch
- Ranking algorithm: v2 (weighted additive, log-scaled, normalized per-signal)
- Grouping: major stories spanning multiple clusters collapse into a single card

---

*Built by [Saayed Alam](https://github.com/saayedalam)*
