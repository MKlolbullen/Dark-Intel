"""QThread that runs an analysis and emits the resulting analysis_id."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class PipelineWorker(QThread):
    finished_ok = Signal(int, str, dict)  # analysis_id, answer, details
    failed = Signal(str)

    def __init__(
        self,
        business_name: str,
        industry: str,
        question: str,
        channels: list[str],
    ):
        super().__init__()
        self._args = (business_name, industry, question, channels)

    def run(self) -> None:
        # Import inside the thread so PySide6 doesn't need spaCy/anthropic at startup
        # if the user only wants to inspect previous analyses.
        from app.pipeline import run_pipeline

        try:
            analysis_id, answer, details = run_pipeline(*self._args)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.finished_ok.emit(analysis_id, answer, details)
