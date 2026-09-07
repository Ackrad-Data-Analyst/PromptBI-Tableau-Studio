from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ALLOWED_ANALYSES = {"descriptive", "diagnostic", "predictive", "prescriptive"}
ALLOWED_CHARTS = {
    "bar", "line", "scatter", "histogram", "box", "heatmap", "treemap",
    "sunburst", "map", "area", "pie",
}


@dataclass(slots=True)
class ChartSpec:
    kind: str
    x: str | None = None
    y: str | None = None
    color: str | None = None
    size: str | None = None
    title: str = ""
    aggregation: str = "sum"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ChartSpec":
        allowed = {key: value.get(key) for key in cls.__dataclass_fields__ if key in value}
        spec = cls(**allowed)
        if spec.kind not in ALLOWED_CHARTS:
            raise ValueError(f"Unsupported chart kind: {spec.kind}")
        return spec


@dataclass(slots=True)
class AnalysisPlan:
    goal: str
    analyses: list[str] = field(default_factory=lambda: ["descriptive"])
    dimensions: list[str] = field(default_factory=list)
    measures: list[str] = field(default_factory=list)
    date_field: str | None = None
    target: str | None = None
    forecast_periods: int = 6
    charts: list[ChartSpec] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def validate(self, columns: list[str]) -> None:
        unknown_analyses = set(self.analyses) - ALLOWED_ANALYSES
        if unknown_analyses:
            raise ValueError(f"Unsupported analysis types: {sorted(unknown_analyses)}")
        referenced = self.dimensions + self.measures
        referenced += [item for item in (self.date_field, self.target) if item]
        referenced += [item for c in self.charts for item in (c.x, c.y, c.color, c.size) if item]
        missing = sorted(set(referenced) - set(columns))
        if missing:
            raise ValueError(f"Plan references missing columns: {missing}")
        if not 1 <= self.forecast_periods <= 120:
            raise ValueError("forecast_periods must be between 1 and 120")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AnalysisPlan":
        payload = dict(value)
        payload["charts"] = [ChartSpec.from_dict(item) for item in payload.get("charts", [])]
        return cls(**{key: payload[key] for key in cls.__dataclass_fields__ if key in payload})

