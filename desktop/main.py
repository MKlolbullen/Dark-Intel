"""Qt operator console: sidebar form + tabbed Results/Graph/Dashboard."""

from __future__ import annotations

import sys

from PySide6.QtCore import QUrl, Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import Config
from app.scrapers import REGISTRY

from .server import FlaskServer
from .worker import PipelineWorker


class MainWindow(QMainWindow):
    def __init__(self, server: FlaskServer):
        super().__init__()
        self.setWindowTitle("Dark-Intel")
        self.resize(1400, 900)
        self._server = server
        self._worker: PipelineWorker | None = None

        sidebar = self._build_sidebar()
        self._tabs = self._build_tabs()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(sidebar)
        splitter.addWidget(self._tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 1040])
        self.setCentralWidget(splitter)

        self.statusBar().showMessage(f"Ready · backend at {server.url}")

    # ---- UI assembly --------------------------------------------------

    def _build_sidebar(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel("<b>Business</b>"))
        self._business = QLineEdit()
        self._business.setPlaceholderText("e.g. Anthropic")
        layout.addWidget(self._business)

        layout.addWidget(QLabel("<b>Industry</b>"))
        self._industry = QLineEdit()
        self._industry.setPlaceholderText("e.g. AI, fintech, retail")
        layout.addWidget(self._industry)

        layout.addWidget(QLabel("<b>Question</b>"))
        self._question = QTextEdit()
        self._question.setPlaceholderText(
            "What should the analysis surface?\n"
            "e.g. main competitors, leadership changes, sentiment among engineers"
        )
        self._question.setFixedHeight(120)
        layout.addWidget(self._question)

        channel_box = QGroupBox("Sources")
        channel_layout = QVBoxLayout(channel_box)
        self._channels: dict[str, QCheckBox] = {}
        for name in REGISTRY:
            cb = QCheckBox(name)
            cb.setChecked(name in Config.DEFAULT_CHANNELS)
            self._channels[name] = cb
            channel_layout.addWidget(cb)
        layout.addWidget(channel_box)

        self._run = QPushButton("Run analysis")
        self._run.clicked.connect(self._on_run)
        layout.addWidget(self._run)

        layout.addStretch(1)
        return w

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        self._results = QTextBrowser()
        self._results.setOpenExternalLinks(True)
        self._results.setPlaceholderText("Run an analysis to see the answer here.")
        tabs.addTab(self._results, "Results")

        self._graph_view = QWebEngineView()
        tabs.addTab(self._graph_view, "Graph")

        self._dashboard_view = QWebEngineView()
        tabs.addTab(self._dashboard_view, "Dashboard")
        return tabs

    # ---- actions ------------------------------------------------------

    def _on_run(self) -> None:
        business = self._business.text().strip()
        industry = self._industry.text().strip()
        question = self._question.toPlainText().strip()
        if not (business and industry and question):
            QMessageBox.warning(self, "Missing input", "Business, industry, and question are all required.")
            return
        channels = [n for n, cb in self._channels.items() if cb.isChecked()]
        if not channels:
            QMessageBox.warning(self, "No sources", "Pick at least one source channel.")
            return

        self._set_running(True)
        self._worker = PipelineWorker(business, industry, question, channels)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_finished(self, analysis_id: int, answer: str, details: dict) -> None:
        self._set_running(False)
        self.statusBar().showMessage(f"Analysis #{analysis_id} complete.")
        html = _render_results(analysis_id, answer, details)
        self._results.setHtml(html)
        self._graph_view.setUrl(QUrl(f"{self._server.url}/graph?analysis_id={analysis_id}"))
        self._dashboard_view.setUrl(QUrl(f"{self._server.url}/dashboard?analysis_id={analysis_id}"))

    def _on_failed(self, message: str) -> None:
        self._set_running(False)
        self.statusBar().showMessage("Analysis failed.")
        QMessageBox.critical(self, "Pipeline error", message)

    def _set_running(self, running: bool) -> None:
        self._run.setEnabled(not running)
        self._run.setText("Running…" if running else "Run analysis")
        for w in (self._business, self._industry, self._question):
            w.setEnabled(not running)
        for cb in self._channels.values():
            cb.setEnabled(not running)


def _render_results(analysis_id: int, answer: str, details: dict) -> str:
    rows = "".join(
        f'<li><span style="color:#6b7280">{label}</span> '
        f'<a href="{src}">{src}</a></li>'
        for label, src in details.items()
    )
    return (
        '<div style="font-family: ui-sans-serif, system-ui;">'
        f"<h2>Analysis #{analysis_id}</h2>"
        '<h3 style="color:#6b7280; font-size:0.8rem; text-transform:uppercase">Answer</h3>'
        f'<p style="white-space:pre-wrap">{_escape(answer)}</p>'
        + ('<h3 style="color:#6b7280; font-size:0.8rem; text-transform:uppercase">Sources</h3>'
           f"<ol>{rows}</ol>" if rows else "")
        + "</div>"
    )


def _escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def main() -> None:
    app = QApplication(sys.argv)
    server = FlaskServer()
    try:
        server.start()
    except Exception as exc:
        QMessageBox.critical(None, "Backend startup failed", str(exc))
        sys.exit(1)
    win = MainWindow(server)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
