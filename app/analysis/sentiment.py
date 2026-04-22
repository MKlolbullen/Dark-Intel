"""Score Mention.snippet sentiment with the active LLM provider, in parallel.

Run lazily on first dashboard load for a given analysis. Subsequent loads
skip already-scored mentions, so the cost is paid once per analysis.
A hard cap (`MAX_PER_RUN`) bounds the API spend per dashboard view.
"""

from __future__ import annotations

import asyncio

from sqlmodel import Session, select

from ..llm import get_relation_client
from ..models import Analysis, Mention, engine

MAX_PER_RUN = 200
CONCURRENCY = 8

_SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "number"}},
    "required": ["score"],
    "additionalProperties": False,
}


def _system_prompt(business_name: str) -> str:
    return (
        f"You score sentiment toward {business_name} in short text snippets. "
        "Return a single JSON object with one key 'score' whose value is a "
        "number from -1.0 (very negative) to 1.0 (very positive). Use 0.0 "
        "for neutral or unclear. No prose, no commentary."
    )


async def _score_one(sem: asyncio.Semaphore, business_name: str, snippet: str) -> float | None:
    async with sem:
        data = await get_relation_client().acomplete_json(
            system=_system_prompt(business_name),
            user=snippet,
            schema=_SCHEMA,
            max_tokens=32,
        )
    if not data:
        return None
    try:
        score = float(data.get("score"))
    except Exception:
        return None
    return max(-1.0, min(1.0, score))


async def score_unscored(analysis_id: int) -> int:
    """Score every unscored Mention for this analysis. Returns the count scored."""

    with Session(engine) as s:
        analysis = s.get(Analysis, analysis_id)
        if analysis is None:
            return 0
        rows = s.exec(
            select(Mention)
            .where(Mention.analysis_id == analysis_id)
            .where(Mention.sentiment_score.is_(None))
        ).all()
        rows = [r for r in rows if r.snippet]
        rows = rows[:MAX_PER_RUN]
        if not rows:
            return 0
        business_name = analysis.business_name

    sem = asyncio.Semaphore(CONCURRENCY)
    scores = await asyncio.gather(*[_score_one(sem, business_name, r.snippet) for r in rows])

    written = 0
    with Session(engine) as s:
        for row, score in zip(rows, scores):
            if score is None:
                continue
            mention = s.get(Mention, row.id)
            if mention is None:
                continue
            mention.sentiment_score = score
            s.add(mention)
            written += 1
        s.commit()
    return written


def score_unscored_sync(analysis_id: int) -> int:
    return asyncio.run(score_unscored(analysis_id))
