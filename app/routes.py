from flask import Blueprint, render_template, request, jsonify
from .pipeline import run_pipeline
from .models import Node, Edge, engine
from sqlmodel import Session, select

main_bp = Blueprint("main", __name__)

@main_bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        question = request.form["question"].strip()
        answer, details = run_pipeline(question)
        return render_template("results.html",
                               question=question,
                               answer=answer,
                               details=details)
    return render_template("index.html")

@main_bp.route("/graph")
def graph():
    return render_template("graph.html")

@main_bp.route("/api/nodes")
def api_nodes():
    with Session(engine) as s:
        nodes = s.exec(select(Node)).all()
        return jsonify([n.dict() for n in nodes])

@main_bp.route("/api/edges")
def api_edges():
    with Session(engine) as s:
        edges = s.exec(select(Edge)).all()
        return jsonify([e.dict() for e in edges])
