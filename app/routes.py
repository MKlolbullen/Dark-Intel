from flask import Blueprint, jsonify, render_template, request
from sqlmodel import Session, select

from .config import Config
from .models import Analysis, Edge, Node, engine
from .pipeline import run_pipeline
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
        analysis_id, answer, details = run_pipeline(
            business_name, industry, question, channels
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


@main_bp.route("/api/analyses")
def api_analyses():
    with Session(engine) as s:
        rows = s.exec(select(Analysis).order_by(Analysis.created_at.desc())).all()
        return jsonify([r.dict() for r in rows])


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
