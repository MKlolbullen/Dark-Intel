import json as _json

from flask import Blueprint, abort, jsonify, render_template, request
from sqlmodel import Session, select

from .analysis import aggregations, sentiment
from .config import Config
from .models import Analysis, Edge, Node, engine, list_chat_turns
from .pipeline import run_pipeline
from .pipeline.qa import answer_followup
from .scrapers import REGISTRY

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET", "POST"])
def index():
    available = list(REGISTRY.keys())
    if request.method == "POST":
        business_name = request.form.get("business_name", "").strip()
        industry = request.form.get("industry", "").strip()
        question = request.form.get("question", "").strip()
        channels = request.form.getlist("channels") or list(Config.DEFAULT_CHANNELS)
        competitors_input = request.form.get("competitors", "").strip()
        analysis_id, answer, details = run_pipeline(
            business_name, industry, question, channels, competitors_input
        )
        return render_template(
            "results.html",
            analysis_id=analysis_id,
            business_name=business_name,
            industry=industry,
            question=question,
            answer=answer,
            details=details,
        )
    return render_template(
        "index.html",
        available_channels=available,
        default_channels=list(Config.DEFAULT_CHANNELS),
    )


@main_bp.route("/graph")
def graph():
    return render_template(
        "graph.html",
        analysis_id=request.args.get("analysis_id", type=int),
    )


@main_bp.route("/dashboard")
def dashboard():
    analysis_id = request.args.get("analysis_id", type=int)
    if analysis_id is None:
        abort(400, "analysis_id is required")
    with Session(engine) as s:
        analysis = s.get(Analysis, analysis_id)
    if analysis is None:
        abort(404)
    competitors = []
    if analysis.competitors:
        try:
            competitors = _json.loads(analysis.competitors)
        except Exception:
            competitors = []
    comparison = None
    if analysis.comparison_json:
        try:
            comparison = _json.loads(analysis.comparison_json)
        except Exception:
            comparison = None
    return render_template(
        "dashboard.html",
        analysis=analysis,
        competitors=competitors,
        comparison=comparison,
    )


@main_bp.route("/api/analyses")
def api_analyses():
    with Session(engine) as s:
        rows = s.exec(select(Analysis).order_by(Analysis.created_at.desc())).all()
        return jsonify([r.dict() for r in rows])


@main_bp.route("/api/analysis/<int:analysis_id>/charts")
def api_analysis_charts(analysis_id: int):
    """Return chart data for the dashboard. Lazily backfills sentiment scores."""

    with Session(engine) as s:
        if s.get(Analysis, analysis_id) is None:
            abort(404)
    sentiment.score_unscored_sync(analysis_id)
    return jsonify(aggregations.all_charts(analysis_id))


@main_bp.route("/chat")
def chat():
    analysis_id = request.args.get("analysis_id", type=int)
    if analysis_id is None:
        abort(400, "analysis_id is required")
    with Session(engine) as s:
        analysis = s.get(Analysis, analysis_id)
    if analysis is None:
        abort(404)
    turns = list_chat_turns(analysis_id)
    # Surface cited source URLs as already-parsed lists for the template
    turn_views = []
    for t in turns:
        try:
            sources = _json.loads(t.sources_json) if t.sources_json else []
        except Exception:
            sources = []
        turn_views.append({"question": t.question, "answer": t.answer, "sources": sources})
    return render_template("chat.html", analysis=analysis, turns=turn_views)


@main_bp.route("/api/analysis/<int:analysis_id>/chat", methods=["POST"])
def api_analysis_chat(analysis_id: int):
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400
    with Session(engine) as s:
        if s.get(Analysis, analysis_id) is None:
            abort(404)
    try:
        answer, sources = answer_followup(analysis_id, question)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"answer": answer, "sources": sources})


@main_bp.route("/api/nodes")
def api_nodes():
    """Return nodes. With ?analysis_id=N, scope to nodes touched by that analysis's edges."""

    analysis_id = request.args.get("analysis_id", type=int)
    with Session(engine) as s:
        if analysis_id is None:
            return jsonify([n.dict() for n in s.exec(select(Node)).all()])

        edges = s.exec(select(Edge).where(Edge.analysis_id == analysis_id)).all()
        node_ids = {e.source_id for e in edges} | {e.target_id for e in edges}
        if not node_ids:
            return jsonify([])
        nodes = s.exec(select(Node).where(Node.id.in_(node_ids))).all()
        return jsonify([n.dict() for n in nodes])


@main_bp.route("/api/edges")
def api_edges():
    analysis_id = request.args.get("analysis_id", type=int)
    with Session(engine) as s:
        stmt = select(Edge)
        if analysis_id is not None:
            stmt = stmt.where(Edge.analysis_id == analysis_id)
        return jsonify([e.dict() for e in s.exec(stmt).all()])
