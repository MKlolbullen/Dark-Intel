# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Install dependencies (the spaCy model is loaded at import time and is **not** in `requirements.txt`):

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Two API keys are required for any analysis to run:

```bash
cp .env.example .env
# then fill in at minimum:
#   ANTHROPIC_API_KEY  — used for relation classification, sentiment, and the RAG answer
#   OPENAI_API_KEY     — used only for FAISS embeddings (text-embedding-3-small)
```

Two entry points share one codebase:

```bash
python desktop.py   # PySide6 operator console; spawns its own Flask backend on a free port
python run.py       # Flask web app on http://127.0.0.1:5000 (debug=True). Same DB.
```

There is no test suite, linter, or CI. Verification of changes is by AST parse + manual run.

## Architecture

Dark-Intel is a business-intelligence pipeline with two front ends over the same SQLite store. The desktop console is the primary UI; the web app is what the embedded `QWebEngineView` tabs render and is also usable standalone.

### Request flow

`POST /` (web) and the Run-analysis button (Qt) both end at `app.pipeline.run_pipeline(business_name, industry, question, channels)`. The pipeline:

1. **Insert an `Analysis` row** (`app/models.py:create_analysis`) with the user's inputs and the RAG model name. Returns the `analysis_id` that everything downstream is keyed on.
2. **Gather documents** via `app/pipeline/source_selection.gather_documents`, which dispatches each requested channel in `REGISTRY` (`app/scrapers/__init__.py`) in parallel. Each scraper subclass (`news`, `reddit`, `hn`, `linkedin`, `x`, `reviews`) returns `ScrapedDoc`s, converted to LangChain `Document`s. A scraper that's not configured (no API token / opt-in flag) silently returns `[]` via `BaseScraper.enabled()`; a scraper that throws is swallowed in `BaseScraper.fetch` so one dead source doesn't kill the run.
3. **Per-document processing** (`process_doc`): upsert a global `Source` row, run spaCy NER (`app/pipeline/entities.py`), upsert a `Node` per entity, persist a `Mention(analysis_id, source_id, node_id, snippet)`, and add a `PAGE → entity` `Edge` scoped to the analysis. Then fan out N·(N−1)/2 pairwise `infer_relation_async` calls (Claude Haiku) and persist non-`no_relation` results as additional `Edge` rows.
4. **RAG answer** via `app/pipeline/rag.py`: build a FAISS index from the docs (OpenAI embeddings), retrieve top-6 for the question, send to Claude Opus 4.7 with `thinking: {type: "adaptive"}`, write the result back to `Analysis.summary`, return `(analysis_id, answer, details)`.

### Schema and persistence (`app/models.py`)

| Table      | Purpose |
|------------|---------|
| `Node`     | One row per distinct entity name (globally unique). |
| `Edge`     | Relation between two nodes, scoped to an `analysis_id`. |
| `Analysis` | One row per `run_pipeline` call. Stores inputs, model, and the final answer. |
| `Source`   | One row per fetched URL (deduped globally). |
| `Mention`  | Many-to-many over (`Analysis`, `Source`, `Node`) with a `snippet` and a nullable `sentiment_score` populated lazily on dashboard load. |

Migrations are intentionally trivial: at import time `_migrate()` introspects the `edge` table and runs `ALTER TABLE ADD COLUMN analysis_id` if the column is missing. Anything more involved (renames, type changes) needs a one-shot script — there is no Alembic.

### Two LLM tiers

Two separate model env vars to keep the cost sane:

| Env                        | Default               | Used by                                   |
|----------------------------|-----------------------|-------------------------------------------|
| `CLAUDE_MODEL`             | `claude-opus-4-7`     | RAG answer (`app/pipeline/rag.py`)        |
| `CLAUDE_MODEL_RELATION`    | `claude-haiku-4-5`    | Pairwise relations (`edge_infer.py`) and lazy sentiment scoring (`analysis/sentiment.py`) |

Sentiment scoring runs on first view of `/dashboard?analysis_id=N` — `score_unscored_sync` capped at `MAX_PER_RUN=200` mentions, `CONCURRENCY=8`, results cached on `Mention.sentiment_score`. Subsequent loads of the same analysis are instant.

### Frontends

`run.py` boots the Flask app via `app.create_app()`. Routes (`app/routes.py`):

- `GET /` and `POST /` — analysis form and result page (`templates/index.html` + `templates/results.html`).
- `GET /graph?analysis_id=N` — D3 force-directed graph; `static/js/d3graph.js` reads `analysis_id` from the URL and forwards it to the API.
- `GET /dashboard?analysis_id=N` — Plotly dashboard (`templates/dashboard.html` + `static/js/dashboard.js`). Pulls everything from `/api/analysis/<id>/charts`.
- `GET /api/analyses`, `/api/nodes?analysis_id=...`, `/api/edges?analysis_id=...`, `/api/analysis/<id>/charts`.

`desktop.py` boots the PySide6 main window (`desktop/main.py`):

- `desktop/server.py:FlaskServer` `subprocess.Popen`s `create_app().run(...)` on a free port, polls `/api/analyses` until ready, registers `atexit` cleanup. The Qt app and the embedded server run in different processes against the same SQLite file.
- `desktop/worker.py:PipelineWorker` is a `QThread` that runs `run_pipeline` (which itself calls `asyncio.run` in the worker thread — safe because there's no Qt event loop in there). Emits `finished_ok(analysis_id, answer, details)` on success.
- `MainWindow` has a sidebar form (one checkbox per `REGISTRY` entry) and three tabs: Results (`QTextBrowser`), Graph (`QWebEngineView` → embedded Flask `/graph`), Dashboard (`QWebEngineView` → embedded Flask `/dashboard`). The Graph and Dashboard tabs are reused web views, not reimplementations.

### Scraper plugin architecture (`app/scrapers/`)

Every scraper subclasses `BaseScraper` and exposes:
- `kind` — short channel name used as the dict key in `REGISTRY` and in the `Source.kind` column.
- `enabled()` — class method returning `False` when required credentials are absent. The pipeline calls scrapers regardless; disabled ones return `[]` from `fetch`.
- `_fetch(query: ScrapeQuery) -> list[ScrapedDoc]` — the actual work. Exceptions are swallowed by `BaseScraper.fetch`.

Adding a new channel: drop a new module in `app/scrapers/`, subclass `BaseScraper`, register it in `REGISTRY`, and (if it needs an env var) document it in `.env.example` and `SCRAPING.md`. The UI checkbox appears automatically.

LinkedIn note: `linkedin.py` uses the official LinkedIn REST API v2 (`vanityName` lookup → org's own posts via `r_organization_social`). The richer "search across LinkedIn for mentions of company X" requires Marketing Developer Platform approval (multi-week review) — see the module docstring.

## Caveats worth flagging

- **Cost surface.** A single analysis with 4 channels × 20 docs × ~8 entities/doc fires ~640 Haiku classification calls plus the lazy sentiment pass and the Opus answer. Cap docs via `ScrapeQuery.limit_per_source` and entities via `extract_entities`'s `thr` if cost becomes a problem.
- **Embedded Flask lifecycle.** `desktop/server.py` registers `atexit`, but a hard kill of the Qt process (`SIGKILL`, IDE force-stop) leaves the Flask child running on a free port. `pkill -f "create_app().run"` to clean up.
- **SQLite + two writers.** Both the `QThread` worker and the Flask subprocess write to the same DB file. SQLite handles this via file locking, but a long-running pipeline call can block dashboard sentiment writes — fine for v1, watch if you start running concurrent analyses.
- **No prompt caching.** The relation-classification prefix sits well below Opus 4.7's 4096-token cache minimum, so caching wouldn't fire. Markers are deliberately omitted to keep the code simple. If you batch-up larger contexts later, add `cache_control={"type": "ephemeral"}` to `messages.create()` and verify with `usage.cache_read_input_tokens`.
- **ToS-restricted channels.** `reviews` (Trustpilot) and any future Glassdoor/G2 work are off by default behind explicit env-var opt-ins. See `SCRAPING.md` for the per-channel legal posture before enabling.

## Branch policy

All work for the documentation/refactor task lives on `claude/add-claude-documentation-0y7t6` and pushes to the same branch on `origin`. Do not push to other branches without explicit permission.
