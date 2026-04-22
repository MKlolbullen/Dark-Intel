"""Score Mention.snippet sentiment with Claude Haiku, in parallel.

Run lazily on first dashboard load for a given analysis. Subsequent loads
skip already-scored mentions, so the cost is paid once per analysis.
A hard cap (`MAX_PER_RUN`) bounds the API spend per dashboard view.
"""

from __future__ import annotations

import asyncio
import json
import re

import anthropic
from sqlmodel import Session, select

from ..config import Config
from ..models import Analysis, Mention, engine

MAX_PER_RUN = 200
CONCURRENCY = 8

_client = anthropic.AsyncAnthropic(api_key=Config.ANTHROPIC_API_KEY)


def _system_prompt(business_name: str) -> str:
    return (
        f"You score sentiment toward {business_name} in short text snippets. "
        "Return a single JSON object with one key 'score' whose value is a "
        "number from -1.0 (very negative) to 1.0 (very positive). Use 0.0 "
        "for neutral or unclear. No prose, no commentary."
    )


_SCORE_RE = re.compile(r'"score"\s*:\s*(-?\d+(?:\.\d+)?)')


def _parse_score(raw: str) -> float | None:
    raw = raw.strip()
    try:
        score = float(json.loads(raw).get("score"))
    except Exception:
        m = _SCORE_RE.search(raw)
        if not m:
            return None
        score = float(m.group(1))
    return max(-1.0, min(1.0, score))


async def _score_one(sem: asyncio.Semaphore, business_name: str, snippet: str) -> float | None:
    async with sem:
        try:
            response = await _client.messages.create(
                model=Config.CLAUDE_MODEL_RELATION,
                max_tokens=32,
                system=_system_prompt(business_name),
                messages=[{"role": "user", "content": snippet}],
            )
        except Exception:
            return None
        text = next((b.text for b in response.content if b.type == "text"), "")
        return _parse_score(text)


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
