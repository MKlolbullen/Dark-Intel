"""Pure-SQL aggregations that feed the dashboard charts."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from sqlmodel import Session, select

from ..models import Mention, Node, Source, engine


def _mentions_with_joins(session: Session, analysis_id: int):
    """Return (mention, source, node) tuples for the given analysis."""

    return session.exec(
        select(Mention, Source, Node)
        .join(Source, Mention.source_id == Source.id)
        .join(Node, Mention.node_id == Node.id)
        .where(Mention.analysis_id == analysis_id)
    ).all()


def source_mix(analysis_id: int) -> dict[str, int]:
    """Count of distinct source URLs per channel kind."""

    with Session(engine) as s:
        rows = s.exec(
            select(Source.kind, Source.id, Mention.id)
            .join(Mention, Mention.source_id == Source.id)
            .where(Mention.analysis_id == analysis_id)
        ).all()
    seen: set[int] = set()
    counts: Counter[str] = Counter()
    for kind, source_id, _ in rows:
        if source_id in seen:
            continue
        seen.add(source_id)
        counts[kind] += 1
    return dict(counts)


def top_entities(analysis_id: int, limit: int = 20) -> list[tuple[str, int]]:
    """Top N entities by mention count."""

    with Session(engine) as s:
        rows = _mentions_with_joins(s, analysis_id)
    counts: Counter[str] = Counter()
    for _, _, node in rows:
        if node.kind == "PAGE":
            continue
        counts[node.name] += 1
    return counts.most_common(limit)


def avg_sentiment_by_kind(analysis_id: int) -> dict[str, float]:
    """Average sentiment score per source kind. Skips unscored mentions."""

    with Session(engine) as s:
        rows = _mentions_with_joins(s, analysis_id)
    sums: defaultdict[str, float] = defaultdict(float)
    counts: defaultdict[str, int] = defaultdict(int)
    for mention, source, _ in rows:
        if mention.sentiment_score is None:
            continue
        sums[source.kind] += mention.sentiment_score
        counts[source.kind] += 1
    return {k: sums[k] / counts[k] for k in sums if counts[k]}


def sentiment_distribution(analysis_id: int, bins: int = 11) -> dict[str, list]:
    """Histogram of sentiment scores, bucketed -1..1."""

    with Session(engine) as s:
        scores = s.exec(
            select(Mention.sentiment_score)
            .where(Mention.analysis_id == analysis_id)
            .where(Mention.sentiment_score.is_not(None))
        ).all()
    if not scores:
        return {"bins": [], "counts": []}
    width = 2.0 / bins
    edges = [-1.0 + i * width for i in range(bins + 1)]
    counts = [0] * bins
    for s_ in scores:
        idx = min(bins - 1, max(0, int((s_ + 1.0) / width)))
        counts[idx] += 1
    labels = [f"{edges[i]:.2f}–{edges[i + 1]:.2f}" for i in range(bins)]
    return {"bins": labels, "counts": counts}


def mentions_over_time(analysis_id: int) -> dict[str, list]:
    """Mentions per day, using Source.fetched_at as the timestamp."""

    with Session(engine) as s:
        rows = s.exec(
            select(Source.fetched_at, Mention.id)
            .join(Mention, Mention.source_id == Source.id)
            .where(Mention.analysis_id == analysis_id)
        ).all()
    buckets: Counter[str] = Counter()
    for ts, _ in rows:
        if ts is None:
            continue
        day = ts.date().isoformat() if isinstance(ts, datetime) else str(ts)[:10]
        buckets[day] += 1
    days = sorted(buckets)
    return {"days": days, "counts": [buckets[d] for d in days]}


def all_charts(analysis_id: int) -> dict:
    return {
        "source_mix": source_mix(analysis_id),
        "top_entities": top_entities(analysis_id),
        "avg_sentiment_by_kind": avg_sentiment_by_kind(analysis_id),
        "sentiment_distribution": sentiment_distribution(analysis_id),
        "mentions_over_time": mentions_over_time(analysis_id),
    }
