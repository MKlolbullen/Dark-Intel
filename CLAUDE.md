# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Install dependencies (the spaCy model is loaded at import time and is not in `requirements.txt`):

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Run the Flask dev server (creates `intel_graph.db` in the current working directory on first run):

```bash
export OPENAI_API_KEY=...   # required by app/pipeline/rag.py and edge_infer.py
python run.py               # serves on http://127.0.0.1:5000 with debug=True
```

There is no test suite, linter, or CI config in the repo.

## Architecture

Dark-Intel is a Flask app that answers free-form intelligence questions by fetching web sources, extracting an entity graph, and running a RAG QA chain over the documents. The graph is persisted to SQLite and visualized with D3.

Request flow (`POST /`):

1. `app/routes.py` calls `run_pipeline(question)` from `app/pipeline/__init__.py`.
2. `run_pipeline` is a sync wrapper around `run_pipeline_async`, which:
   - `source_selection.select_sources` picks a hard-coded URL list based on keywords in the question.
   - `async_loader.load_documents` fetches all URLs concurrently with `httpx.AsyncClient` and wraps them via LangChain's `WebBaseLoader`.
   - For each document, `process_doc` runs `entities.extract_entities` (spaCy NER over `ORG/PERSON/GPE/PRODUCT`, deduped with `rapidfuzz`), upserts a `PAGE` node and one node per entity, and fans out pairwise `edge_infer.infer_relation_async` LLM calls to label edges.
   - `rag.build_qa_chain` builds an in-memory FAISS index over the fetched docs and runs a `RetrievalQA` chain (`gpt-4o-mini`) to produce the user-facing answer with `[n]` citations.
3. The graph (`/graph`) is a separate D3 view that calls `/api/nodes` and `/api/edges`; those endpoints just dump every row from the `Node` / `Edge` SQLModel tables defined in `app/models.py`.

Persistence is intentionally minimal: `models.py` opens a single global `engine = create_engine("sqlite:///intel_graph.db")` and calls `SQLModel.metadata.create_all(engine)` at import time. `upsert_node`/`add_edge` are the only write paths and are called from the pipeline. The DB is path-relative to CWD, so running from a different directory silently creates a new DB.

The frontend is server-rendered Jinja2 with Tailwind via CDN (`app/templates/base.html`). The graph page (`templates/graph.html`) loads `static/js/d3graph.js`, which also POSTs the question form back to `/` and scrapes the first `<p>` from the returned HTML for the side panel summary — i.e. it depends on the structure of `results.html`.

## Repo quirks to be aware of

These look like bugs or stale state, not intentional design — confirm with the user before "fixing" them as part of an unrelated change:

- **Missing templates.** `routes.py` renders `index.html` and `results.html`, but only `base.html` and `graph.html` exist under `app/templates/`. The `/` route will 500 until those are added. The README's tree lists them, so they were expected to exist.
- **Duplicate `edge_infer.py`.** A copy exists at the repo root (`/edge_infer.py`) in addition to `app/pipeline/edge_infer.py`. Only the package version is imported; the root copy is dead code using the legacy sync `openai.ChatCompletion.create` API.
- **OpenAI SDK mismatch.** `requirements.txt` pins `openai==1.25.0`, but `app/pipeline/edge_infer.py` calls `openai.ChatCompletion.acreate(...)` — that API was removed in `openai>=1.0`. Any relation inference call will hit the `except` branch and fall back to `"mentions"`.
- **LangChain loader call.** `async_loader.load_documents` calls `WebBaseLoader.from_html(html, url=url)`, which is not a real constructor on `langchain_community.WebBaseLoader`. Document loading needs reworking before the pipeline can produce real output.
- **LangChain chain invocation.** `pipeline/__init__.py` uses `chain({"query": question})`; under `langchain==0.2.0` prefer `chain.invoke({"query": question})`.
- **Misplaced static asset.** `app/templates/static/css/style.css` is under `templates/` instead of `app/static/css/`. Nothing references it; templates load Tailwind from a CDN and the JS file is served from the correctly-located `app/static/js/d3graph.js`.
- **Config surface.** `app/config.py` only exposes `SECRET_KEY` (defaulting to `"dev"`). All other settings (URL lists in `source_selection.py`, models in `rag.py`/`edge_infer.py`, DB path in `models.py`) are hard-coded; treat them as the source of truth rather than searching for env vars.

## Branch policy

All work for this task must happen on `claude/add-claude-documentation-0y7t6` and be pushed to that same branch on `origin`. Do not push to other branches without explicit permission.
