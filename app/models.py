from datetime import datetime, timezone

from sqlalchemy import inspect, text
from sqlmodel import Field, Session, SQLModel, create_engine, select

from .config import Config

engine = create_engine(Config.DB_URL)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Node(SQLModel, table=True):
    """An entity in the global knowledge graph. Unique by name across all analyses."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    kind: str
    x: int | None = None
    y: int | None = None


class Edge(SQLModel, table=True):
    """A relation between two entities, scoped to the analysis that discovered it."""

    id: int | None = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="node.id")
    target_id: int = Field(foreign_key="node.id")
    relation: str
    analysis_id: int | None = Field(default=None, foreign_key="analysis.id", index=True)


class Analysis(SQLModel, table=True):
    """One pipeline run."""

    id: int | None = Field(default=None, primary_key=True)
    business_name: str = Field(index=True)
    industry: str
    question: str
    model: str
    summary: str | None = None
    competitors: str | None = None  # JSON: [{"name": "...", "domain": "..."}, ...]
    comparison_json: str | None = None  # JSON: structured head-to-head table
    created_at: datetime = Field(default_factory=_utcnow, index=True)


class Source(SQLModel, table=True):
    """A document fetched by a scraper. Deduped globally by URL."""

    id: int | None = Field(default=None, primary_key=True)
    url: str = Field(index=True, unique=True)
    kind: str  # news / reddit / hn / linkedin / x / reviews / competitor
    scraper: str
    title: str | None = None
    competitor: str | None = Field(default=None, index=True)  # set on competitor pages
    fetched_at: datetime = Field(default_factory=_utcnow)


class Mention(SQLModel, table=True):
    """An entity surfaced from a source during an analysis. Feeds dashboard charts."""

    id: int | None = Field(default=None, primary_key=True)
    analysis_id: int = Field(foreign_key="analysis.id", index=True)
    source_id: int = Field(foreign_key="source.id", index=True)
    node_id: int = Field(foreign_key="node.id", index=True)
    snippet: str | None = None
    sentiment_score: float | None = None  # populated lazily on dashboard load


def _migrate() -> None:
    """Add columns we introduced after the initial schema.

    SQLModel.metadata.create_all is idempotent for tables but never alters
    existing ones. SQLite supports ADD COLUMN, so this runs on every import
    for both fresh and existing databases.
    """

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    additions: list[tuple[str, str, str]] = [
        ("edge", "analysis_id", "INTEGER"),
        ("analysis", "competitors", "TEXT"),
        ("analysis", "comparison_json", "TEXT"),
        ("source", "competitor", "VARCHAR"),
    ]
    for table_name, col_name, sql_type in additions:
        if table_name not in existing_tables:
            continue
        cols = {c["name"] for c in inspector.get_columns(table_name)}
        if col_name in cols:
            continue
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {sql_type}"))
            conn.commit()


SQLModel.metadata.create_all(engine)
_migrate()


# ---- write helpers ---------------------------------------------------------


def upsert_node(name: str, kind: str = "GENERIC") -> int:
    with Session(engine) as s:
        node = s.exec(select(Node).where(Node.name == name)).first()
        if not node:
            node = Node(name=name, kind=kind)
            s.add(node)
            s.commit()
            s.refresh(node)
        return node.id


def add_edge(
    src_name: str,
    tgt_name: str,
    relation: str = "mentions",
    analysis_id: int | None = None,
) -> None:
    src_id = upsert_node(src_name)
    tgt_id = upsert_node(tgt_name)
    with Session(engine) as s:
        s.add(
            Edge(
                source_id=src_id,
                target_id=tgt_id,
                relation=relation,
                analysis_id=analysis_id,
            )
        )
        s.commit()


def create_analysis(
    business_name: str,
    industry: str,
    question: str,
    model: str,
    competitors_json: str | None = None,
) -> int:
    with Session(engine) as s:
        row = Analysis(
            business_name=business_name,
            industry=industry,
            question=question,
            model=model,
            competitors=competitors_json,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return row.id


def update_analysis_summary(analysis_id: int, summary: str) -> None:
    with Session(engine) as s:
        row = s.get(Analysis, analysis_id)
        if row is None:
            return
        row.summary = summary
        s.add(row)
        s.commit()


def update_analysis_comparison(analysis_id: int, comparison_json: str) -> None:
    with Session(engine) as s:
        row = s.get(Analysis, analysis_id)
        if row is None:
            return
        row.comparison_json = comparison_json
        s.add(row)
        s.commit()


def upsert_source(
    url: str,
    kind: str,
    scraper: str,
    title: str | None = None,
    competitor: str | None = None,
) -> int:
    """Insert a Source row if missing. competitor is only set on insert."""

    with Session(engine) as s:
        row = s.exec(select(Source).where(Source.url == url)).first()
        if not row:
            row = Source(
                url=url,
                kind=kind,
                scraper=scraper,
                title=title,
                competitor=competitor,
            )
            s.add(row)
            s.commit()
            s.refresh(row)
        return row.id


def add_mention(
    analysis_id: int,
    source_id: int,
    node_id: int,
    snippet: str | None = None,
) -> None:
    with Session(engine) as s:
        s.add(
            Mention(
                analysis_id=analysis_id,
                source_id=source_id,
                node_id=node_id,
                snippet=snippet,
            )
        )
        s.commit()
