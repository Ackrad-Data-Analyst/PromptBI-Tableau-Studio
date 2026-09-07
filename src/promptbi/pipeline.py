from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from .analysis import AnalysisOutputs, run_modules
from .models import AnalysisPlan
from .planner import deterministic_plan
from .visuals import create_figure, write_dashboard


@dataclass(slots=True)
class AnalysisResult:
    plan: AnalysisPlan
    outputs: AnalysisOutputs
    figures: list[go.Figure]

    def write(self, directory: str | Path) -> Path:
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        (root / "analysis_plan.json").write_text(json.dumps(self.plan.to_dict(), indent=2), encoding="utf-8")
        (root / "findings.json").write_text(json.dumps({
            "findings": self.outputs.findings,
            "warnings": self.outputs.warnings,
            "metrics": self.outputs.metrics,
        }, indent=2, default=str), encoding="utf-8")
        table_root = root / "tables"
        table_root.mkdir(exist_ok=True)
        for name, table in self.outputs.tables.items():
            table.to_csv(table_root / f"{name}.csv", index=False)
        write_dashboard(root / "dashboard.html", self.figures, self.plan.goal,
                        self.outputs.findings, self.outputs.warnings)
        return root


def run_analysis(frame: pd.DataFrame, prompt: str, plan: AnalysisPlan | None = None) -> AnalysisResult:
    selected = plan or deterministic_plan(prompt, frame)
    selected.validate(list(frame.columns))
    outputs = run_modules(frame, selected)
    figures: list[go.Figure] = []
    for spec in selected.charts:
        try:
            figures.append(create_figure(frame, spec))
        except (ValueError, TypeError) as exc:
            outputs.warnings.append(f"Chart {spec.title or spec.kind!r} skipped: {exc}")
    return AnalysisResult(selected, outputs, figures)

