import csv
import json
import os
import threading
import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from config.settings import SETTINGS


@dataclass(slots=True)
class PerformanceStage:
    name: str
    seconds: float
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "seconds": round(self.seconds, 6),
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class PerformanceReport:
    report_id: str
    query: str
    started_at: str
    completed_at: str = ""
    total_seconds: float = 0.0
    stages: list[PerformanceStage] = field(
        default_factory=list
    )
    metrics: dict[str, Any] = field(
        default_factory=dict
    )
    peak_memory_mb: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "format": "lexia-performance-report",
            "version": "1.0",
            "report_id": self.report_id,
            "query": self.query,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_seconds": round(
                self.total_seconds,
                6,
            ),
            "peak_memory_mb": round(
                self.peak_memory_mb,
                3,
            ),
            "metrics": self.metrics,
            "stages": [
                stage.to_dict()
                for stage in self.stages
            ],
            "error": self.error,
        }


class PerformanceProfiler:
    """
    Profiler de observación.

    No cambia límites, consultas, ranking ni resultados. Solo mide el
    flujo actual y guarda informes JSON/CSV.
    """

    def __init__(
        self,
        reports_path: str | Path | None = None,
    ):
        runtime_path = getattr(
            SETTINGS,
            "runtime_path",
            Path("runtime"),
        )
        self.reports_path = Path(
            reports_path
            or (
                runtime_path
                / "performance_reports"
            )
        )
        self.reports_path.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._local = threading.local()
        self._last_report = None
        self._lock = threading.RLock()

    def start(
        self,
        query: str,
    ) -> PerformanceReport:
        now = datetime.now()
        report = PerformanceReport(
            report_id=now.strftime(
                "%Y%m%d_%H%M%S_%f"
            ),
            query=query.strip(),
            started_at=now.isoformat(
                timespec="milliseconds"
            ),
        )
        self._local.report = report
        self._local.started_perf = (
            time.perf_counter()
        )
        self._local.stage_stack = {}

        if not tracemalloc.is_tracing():
            tracemalloc.start()

        tracemalloc.reset_peak()
        return report

    @contextmanager
    def stage(
        self,
        name: str,
        **metadata,
    ):
        report = self.current()

        if report is None:
            yield
            return

        started = time.perf_counter()

        try:
            yield
        finally:
            elapsed = (
                time.perf_counter() - started
            )
            report.stages.append(
                PerformanceStage(
                    name=name,
                    seconds=elapsed,
                    metadata={
                        key: value
                        for key, value
                        in metadata.items()
                        if value is not None
                    },
                )
            )

    def metric(
        self,
        name: str,
        value: Any,
    ) -> None:
        report = self.current()

        if report is not None:
            report.metrics[name] = value

    def finish(
        self,
        error: Exception | str | None = None,
    ) -> PerformanceReport | None:
        report = self.current()

        if report is None:
            return None

        report.total_seconds = (
            time.perf_counter()
            - self._local.started_perf
        )
        report.completed_at = (
            datetime.now().isoformat(
                timespec="milliseconds"
            )
        )

        try:
            _, peak = tracemalloc.get_traced_memory()
            report.peak_memory_mb = (
                peak / 1024 / 1024
            )
        except RuntimeError:
            report.peak_memory_mb = 0.0

        if error:
            report.error = str(error)

        self._add_derived_metrics(report)
        self._save(report)

        with self._lock:
            self._last_report = report

        self._local.report = None
        return report

    def current(self):
        return getattr(
            self._local,
            "report",
            None,
        )

    def last_report(self):
        with self._lock:
            return self._last_report

    def last_report_dict(self) -> dict | None:
        report = self.last_report()
        return (
            report.to_dict()
            if report else None
        )

    def load_latest(self) -> dict | None:
        files = sorted(
            self.reports_path.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        if not files:
            return None

        try:
            return json.loads(
                files[0].read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            return None

    def _add_derived_metrics(
        self,
        report: PerformanceReport,
    ) -> None:
        stage_totals: dict[str, float] = {}

        for stage in report.stages:
            stage_totals[stage.name] = (
                stage_totals.get(
                    stage.name,
                    0.0,
                )
                + stage.seconds
            )

        report.metrics[
            "stage_totals_seconds"
        ] = {
            key: round(value, 6)
            for key, value
            in stage_totals.items()
        }

        duplicate_seconds = stage_totals.get(
            "base_builder_second_pass",
            0.0,
        )
        report.metrics[
            "possible_duplicate_work_seconds"
        ] = round(
            duplicate_seconds,
            6,
        )

        if report.total_seconds > 0:
            report.metrics[
                "possible_duplicate_work_percent"
            ] = round(
                duplicate_seconds
                / report.total_seconds
                * 100,
                2,
            )

        slowest = sorted(
            report.stages,
            key=lambda item: item.seconds,
            reverse=True,
        )[:5]

        report.metrics[
            "slowest_stages"
        ] = [
            {
                "name": item.name,
                "seconds": round(
                    item.seconds,
                    6,
                ),
            }
            for item in slowest
        ]

    def _save(
        self,
        report: PerformanceReport,
    ) -> None:
        base = (
            self.reports_path
            / report.report_id
        )
        json_path = base.with_suffix(".json")
        csv_path = base.with_suffix(".csv")

        json_path.write_text(
            json.dumps(
                report.to_dict(),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        with csv_path.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as stream:
            writer = csv.writer(stream)
            writer.writerow(
                [
                    "etapa",
                    "segundos",
                    "porcentaje_total",
                    "metadatos",
                ]
            )

            for stage in report.stages:
                percentage = (
                    stage.seconds
                    / report.total_seconds
                    * 100
                    if report.total_seconds
                    else 0
                )
                writer.writerow(
                    [
                        stage.name,
                        round(
                            stage.seconds,
                            6,
                        ),
                        round(
                            percentage,
                            2,
                        ),
                        json.dumps(
                            stage.metadata,
                            ensure_ascii=False,
                        ),
                    ]
                )

            writer.writerow([])
            writer.writerow(
                [
                    "TOTAL",
                    round(
                        report.total_seconds,
                        6,
                    ),
                    100,
                    "",
                ]
            )
