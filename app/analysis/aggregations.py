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


def coverage_per_competitor(analysis_id: int) -> dict[str, dict[str, int]]:
    """For each competitor, count distinct sources scraped and mentions extracted."""

    with Session(engine) as s:
        rows = s.exec(
            select(Source.competitor, Source.id, Mention.id)
            .join(Mention, Mention.source_id == Source.id)
            .where(Mention.analysis_id == analysis_id)
            .where(Source.competitor.is_not(None))
        ).all()
    sources_per: defaultdict[str, set] = defaultdict(set)
    mentions_per: Counter[str] = Counter()
    for competitor, source_id, _ in rows:
        sources_per[competitor].add(source_id)
        mentions_per[competitor] += 1
    return {
        c: {"sources": len(sources_per[c]), "mentions": mentions_per[c]}
        for c in sorted(sources_per)
    }


def avg_sentiment_per_competitor(analysis_id: int) -> dict[str, float]:
    """Average sentiment of mentions extracted from each competitor's own pages.

    Useful as a rough proxy for how favorably each competitor describes
    the broader landscape (including the target business).
    """

    with Session(engine) as s:
        rows = s.exec(
            select(Source.competitor, Mention.sentiment_score)
            .join(Mention, Mention.source_id == Source.id)
            .where(Mention.analysis_id == analysis_id)
            .where(Source.competitor.is_not(None))
            .where(Mention.sentiment_score.is_not(None))
        ).all()
    sums: defaultdict[str, float] = defaultdict(float)
    counts: defaultdict[str, int] = defaultdict(int)
    for competitor, score in rows:
        sums[competitor] += score
        counts[competitor] += 1
    return {c: sums[c] / counts[c] for c in sums if counts[c]}


def top_entities_per_competitor(
    analysis_id: int, limit_per_competitor: int = 10
) -> dict[str, list]:
    """Heatmap data: rows=entities, cols=competitors, cell=mention count.

    Returns `{competitors: [...], entities: [...], matrix: [[count, ...], ...]}`
    where matrix[i][j] is the mention count of entities[i] on competitors[j]'s pages.
    """

    with Session(engine) as s:
        rows = s.exec(
            select(Source.competitor, Node.name)
            .join(Mention, Mention.source_id == Source.id)
            .join(Node, Mention.node_id == Node.id)
            .where(Mention.analysis_id == analysis_id)
            .where(Source.competitor.is_not(None))
        ).all()

    by_competitor: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for competitor, entity in rows:
        if entity and entity.startswith(("http://", "https://")):
            continue  # skip PAGE nodes
        by_competitor[competitor][entity] += 1

    if not by_competitor:
        return {"competitors": [], "entities": [], "matrix": []}

    competitors = sorted(by_competitor)
    top_entities_set: set[str] = set()
    for comp in competitors:
        for ent, _ in by_competitor[comp].most_common(limit_per_competitor):
            top_entities_set.add(ent)

    totals = Counter()
    for ent in top_entities_set:
        for comp in competitors:
            totals[ent] += by_competitor[comp].get(ent, 0)
    entities = [ent for ent, _ in totals.most_common()]
    matrix = [
        [by_competitor[comp].get(ent, 0) for comp in competitors]
        for ent in entities
    ]
    return {"competitors": competitors, "entities": entities, "matrix": matrix}


def all_charts(analysis_id: int) -> dict:
    return {
        "source_mix": source_mix(analysis_id),
        "top_entities": top_entities(analysis_id),
        "avg_sentiment_by_kind": avg_sentiment_by_kind(analysis_id),
        "sentiment_distribution": sentiment_distribution(analysis_id),
        "mentions_over_time": mentions_over_time(analysis_id),
        "coverage_per_competitor": coverage_per_competitor(analysis_id),
        "avg_sentiment_per_competitor": avg_sentiment_per_competitor(analysis_id),
        "top_entities_per_competitor": top_entities_per_competitor(analysis_id),
    }
