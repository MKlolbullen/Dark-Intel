from flask import Blueprint, jsonify, render_template, request
from sqlmodel import Session, select

from .config import Config
from .models import Edge, Node, engine
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
        answer, details = run_pipeline(business_name, industry, question, channels)
        return render_template(
            "results.html",
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
    return render_template("graph.html")


@main_bp.route("/api/nodes")
def api_nodes():
    with Session(engine) as s:
        return jsonify([n.dict() for n in s.exec(select(Node)).all()])


@main_bp.route("/api/edges")
def api_edges():
    with Session(engine) as s:
        return jsonify([e.dict() for e in s.exec(select(Edge)).all()])
