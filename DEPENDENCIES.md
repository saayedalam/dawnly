# Dawnly — Dependency Map
# Last updated: 2026-05-03
#
# Use this file whenever you make a change to the project.
# For each file you touch, check every entry in its "then update" column.
# Update this file itself whenever new dependencies are discovered.

---

## Sources

| If you change | Then also update |
|---------------|-----------------|
| `sources.py` — add or remove a source | `removed_sources.json` (log removed sources), `source_health.json` (remove ghost entries), `about.html` (source count + named examples), `README.md` (source count + tier list) |
| `sources.py` — change a region label | `about.html` (if that region is named), `README.md` (if that region is named) |
| `sources.py` — change a weight or tier | `rank.py` (verify weight lookup still works — `get_source_weight()`) |
| `sources.py` — add/remove continent tag | `rank.py` (geo diversity scoring reads continent), `fetch.py` (passes continent forward on articles) |
| `removed_sources.json` | Nothing — this is a terminal file, nothing reads it |

---

## Pipeline

| If you change | Then also update |
|---------------|-----------------|
| `fetch.py` — add a new article field | `cluster.py` (check if field needs to be passed through), `rank.py` (check if field is used), `publish.py` (check if field needs to be written to top10.json) |
| `fetch.py` — change fetch window or caps | `about.html` (if timing claims change), `README.md` |
| `cluster.py` — change embedding model | `requirements.txt` (model dependency), `README.md` (if model is mentioned) |
| `rank.py` — add a new output field to a story | `publish.py` (must pass field through to top10.json), `index.html` (if field is displayed), `send_newsletter.py` (if field is used in email) |
| `rank.py` — change ranking signals or weights | `about.html` (any public claims about how ranking works — never expose specific weights) |
| `summarize.py` — change summary prompt | No downstream files — but log the change and monitor output quality |
| `publish.py` — change top10.json schema | `index.html` (reads every field from top10.json), `send_newsletter.py` (reads story fields), `rank.py` (verify all output fields are written) |
| `publish.py` — change archive path | `pipeline.yml` (git commit step must match archive path) |
| `source_health.py` — change health log schema | `send_health_report.py` (reads health log fields) |

---

## Frontend

| If you change | Then also update |
|---------------|-----------------|
| `index.html` — any layout change | Test desktop AND mobile — they break each other. Test card front, card back, and overlay separately |
| `index.html` — reads a new field from top10.json | `rank.py` (must output that field), `publish.py` (must write that field) |
| `index.html` — meta-bar, flip elements | Test all three flip elements (edition, centre, date) on both desktop and mobile |
| `about.html` | Check all claims against current pipeline state — source count, ranking description, named sources |
| `confirmed.html` | Check URLs point to `dawnly.news` |

---

## Infrastructure

| If you change | Then also update |
|---------------|-----------------|
| Domain or URLs | `README.md`, `about.html`, `confirmed.html`, `send_newsletter.py`, Buttondown (redirect URLs, sending domain), GitHub Pages settings |
| `pipeline.yml` — schedule or steps | Verify commit step matches `publish.py` output paths. Verify secrets are still valid |
| `requirements.txt` | Test pipeline locally before pushing — a bad dependency breaks the 6AM run |
| GitHub secrets | `pipeline.yml` (verify secret names match), update Anthropic/Buttondown dashboards as needed |

---

## Newsletter

| If you change | Then also update |
|---------------|-----------------|
| `send_newsletter.py` — subject line format | `about.html` or `README.md` if newsletter is described there |
| `send_newsletter.py` — story fields used | `publish.py` (verify those fields exist in top10.json), `rank.py` (verify those fields are output) |
| Buttondown settings (sending domain, redirects) | `confirmed.html` (post-confirmation redirect URL), `send_newsletter.py` (API calls) |

---

## Public-facing content

| If you change | Then also update |
|---------------|-----------------|
| Source count | `about.html` (two mentions), `README.md` (three mentions including file tree) |
| Tier counts or composition | `README.md` (tier breakdown section) |
| Named sources in public copy | `about.html` (Step 01 Gather section names specific sources) |
| Ranking description | `about.html` (principles section — never expose specific weights or signals) |
| Product philosophy or taglines | `about.html`, `README.md`, `confirmed.html`, `send_newsletter.py` footer |

---

## Rules
- Never expose ranking weights or specific signals in any public-facing file
- "algorithmically" is banned from public copy — use "ranked by global coverage"
- When removing sources, always update `removed_sources.json` before committing
- Region labels in `sources.py` must be distinct enough that no two sources produce redundant labels on the same story card
