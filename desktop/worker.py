"""QThread that runs an analysis and reports progress + result."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class PipelineWorker(QThread):
    progress = Signal(str)  # stage name: resolving_competitors | scraping | processing | answering | comparing | done
    finished_ok = Signal(int, str, dict, dict)  # analysis_id, answer, details, source_counts
    failed = Signal(str)

    def __init__(
        self,
        business_name: str,
        industry: str,
        question: str,
        channels: list[str],
        competitors_input: str = "",
        business_website: str = "",
    ):
        super().__init__()
        self._args = (
            business_name,
            industry,
            question,
            channels,
            competitors_input,
            business_website,
        )

    def run(self) -> None:
        from app.pipeline import run_pipeline

        try:
            analysis_id, answer, details, source_counts = run_pipeline(
                *self._args,
                progress=self.progress.emit,
            )
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.finished_ok.emit(analysis_id, answer, details, source_counts)
