# Dark-Intel

Competitive intelligence platform. Drop in a business name, an industry, and a question — the pipeline scrapes relevant public sources, pulls each competitor's own website, extracts an entity graph, and returns a Claude-generated analysis with a head-to-head comparison table.

Two frontends over one SQLite store:

- **PySide6 desktop console** (primary) — `python desktop.py`
- **Flask web app** (also embedded by the desktop app) — `python run.py`

## What it does

- **Multi-source scraping** — news & company sites, Hacker News, Reddit, LinkedIn (official REST API v2), X / Twitter (official v2 API, paid plan), Trustpilot reviews, and each competitor's own website (`/about`, `/pricing`, `/products`, `/blog`, …).
- **Auto-discovered competitors** — leave the Competitors field blank and Claude Opus picks them from the industry. Or paste `Name (domain), Name2 (domain2)` to skip discovery.
- **Entity graph** — spaCy NER per document, Claude Haiku classifies pairwise relations (`competitor_of`, `partner_of`, `acquired_by`, …). Graph is D3 force-directed, scoped per analysis.
- **RAG answer** — FAISS retrieval over the scraped corpus (OpenAI embeddings) + Claude Opus 4.7 with adaptive thinking. The prompt is augmented with the competitor list so the answer contrasts product / pricing / positioning.
- **Head-to-head comparison table** — second Claude Opus pass with structured JSON output, persisted and rendered server-side. Columns: product focus, pricing, target market, key differentiator, recent moves.
- **Plotly dashboard** — source mix, sentiment distribution, avg sentiment by channel, top entities, mentions over time, per-competitor coverage, per-competitor sentiment, top-entities-per-competitor heatmap.
- **Follow-up Q&A** — each completed analysis has its own chat thread (`/chat?analysis_id=N`). Ask anything; Claude Opus answers from the same scraped corpus (rebuilt from `Source.text`, cached per analysis) with cited sources, and the thread is persisted so you can come back to it later.
- **Lazy sentiment scoring** — first dashboard load of an analysis backfills sentiment via Claude Haiku, capped at 200 snippets, cached on `Mention.sentiment_score`.

## Quick start

```bash
# Deps (spaCy model isn't in requirements.txt)
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Config
cp .env.example .env
# Fill in at minimum:
#   ANTHROPIC_API_KEY — Claude (RAG answer, relations, sentiment, competitor discovery, comparison)
#   OPENAI_API_KEY    — only used for FAISS embeddings (text-embedding-3-small)

# Run
python desktop.py   # Qt operator console; spawns Flask on a free port for the embedded views
python run.py       # or just the web UI on http://127.0.0.1:5000
```

## Source channels

| Channel     | Auth                                      | On by default | Notes |
|-------------|-------------------------------------------|---------------|-------|
| `news`      | none                                      | yes           | Industry-aware seed list + company about page. |
| `hn`        | none                                      | yes           | Algolia HN search API. |
| `reddit`    | `REDDIT_CLIENT_ID` / `SECRET`             | yes*          | asyncpraw across relevant subs. *No-ops when creds absent. |
| `competitor`| Anthropic (for discovery)                 | yes           | Uses user-supplied list, or auto-discovers. Fetches curated paths per competitor. |
| `linkedin`  | `LINKEDIN_ACCESS_TOKEN`                   | no            | Official REST API v2. Reachable surface is limited without LinkedIn Marketing Developer Platform approval. |
| `x`         | `X_BEARER_TOKEN` (paid Basic+)            | no            | Official v2 recent-search endpoint. |
| `reviews`   | `ENABLE_REVIEW_SCRAPERS=1`                | no            | Trustpilot. ToS-restricted; see `SCRAPING.md`. |

See `SCRAPING.md` for the legal / ToS posture per channel before enabling anything opt-in.

## LLM provider

Pick one of three providers with `LLM_PROVIDER=anthropic | gemini | grok`. Each has a default model (long-form tasks) and a relation model (high-volume classification):

| Provider    | Default model                       | Relation model                        | Env keys                                            |
|-------------|-------------------------------------|---------------------------------------|-----------------------------------------------------|
| `anthropic` | `CLAUDE_MODEL=claude-opus-4-7`      | `CLAUDE_MODEL_RELATION=claude-haiku-4-5` | `ANTHROPIC_API_KEY`                              |
| `gemini`    | `GEMINI_MODEL=gemini-2.5-pro`       | `GEMINI_MODEL_RELATION=gemini-2.5-flash` | `GEMINI_API_KEY`                                 |
| `grok`      | `GROK_MODEL=grok-4`                 | `GROK_MODEL_RELATION=grok-3-mini`     | `GROK_API_KEY`                                      |

Anthropic keeps full fidelity (strict JSON schemas + adaptive thinking). Gemini and Grok get best-effort equivalents (JSON mime / `json_object` mode with the schema passed as a system-prompt hint, and provider-native reasoning toggles where supported).

Embeddings always go through OpenAI — `OPENAI_API_KEY` and `EMBEDDING_MODEL=text-embedding-3-small` (default) are required regardless of `LLM_PROVIDER`. The adapter lives in `app/llm/`; no call site imports the Anthropic SDK directly.

## Architecture at a glance

```
Qt / web form ─► run_pipeline ─► resolve competitors (user-supplied or Claude discovery)
                                │
                                ├─► gather_documents (parallel scrapers)
                                │       news · hn · reddit · linkedin · x
                                │       reviews · competitor (per domain × curated paths)
                                │
                                ├─► per doc: spaCy NER → Mentions +
                                │             pairwise Haiku relation classification
                                │
                                ├─► FAISS + Claude Opus RAG → Analysis.summary
                                │
                                └─► Claude Opus structured comparison table
                                         → Analysis.comparison_json

       Dashboard (/dashboard?analysis_id=N) pulls aggregations + lazy sentiment.
       Graph (/graph?analysis_id=N) renders the per-analysis subgraph.
```

See [CLAUDE.md](./CLAUDE.md) for the deeper tour (schema, migration policy, embedded Flask lifecycle, caveats).

## Project layout

```
app/
├── scrapers/          # One file per source family; BaseScraper + REGISTRY
├── intel/             # Competitor discovery (Claude + JSON schema)
├── pipeline/          # Orchestrator, entity extraction, relation inference, RAG
├── analysis/          # Lazy sentiment, SQL aggregations, head-to-head comparison
├── templates/         # index / results / graph / dashboard (Jinja2 + Tailwind CDN)
├── static/js/         # d3graph.js, dashboard.js (Plotly)
├── routes.py
├── models.py          # SQLModel tables + ALTER TABLE migration helper
└── config.py          # python-dotenv wrapper

desktop/
├── main.py            # PySide6 MainWindow with sidebar form + tabbed WebEngineViews
├── server.py          # Spawns Flask as a subprocess on a free port, atexit cleanup
└── worker.py          # QThread that runs the pipeline and emits Qt signals

run.py                 # Flask entry
desktop.py             # Qt entry
SCRAPING.md            # Per-channel auth + ToS posture
CLAUDE.md              # Architecture notes for AI assistants
```

## Caveats

- No automated tests, linter, or CI — AST parse + manual run is the verification loop today.
- Pipeline cost scales with entity density: 4 channels × ~20 docs × ~8 entities/doc ≈ 640 Haiku classification calls plus an Opus answer and an Opus comparison. Dial `ScrapeQuery.limit_per_source` if costs climb.
- SQLite with two writers (QThread worker + embedded Flask subprocess) — fine for single-user, watch out if you run concurrent analyses.
- Migration policy is deliberately trivial: at import time `_migrate()` runs `ALTER TABLE ADD COLUMN` for any new column not yet present. No Alembic. Renames / type changes need a one-shot script.
- The embedded Flask lifecycle uses `atexit`; a hard kill of the Qt process (`SIGKILL`, IDE force-stop) can orphan it — `pkill -f "create_app().run"` if that happens.

## Tech stack

Python · Flask · PySide6 · Qt WebEngine · SQLModel / SQLAlchemy · SQLite · httpx · BeautifulSoup · spaCy · rapidfuzz · FAISS · LangChain (community + OpenAI embeddings) · Anthropic SDK · asyncpraw · Plotly · D3.js · Tailwind (CDN)
