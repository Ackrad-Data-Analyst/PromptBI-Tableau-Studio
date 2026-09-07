from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

from .models import AnalysisPlan, ChartSpec


def _mentions(prompt: str, columns: list[str]) -> list[str]:
    text = prompt.lower().replace("_", " ")
    return [column for column in columns if column.lower().replace("_", " ") in text]


def deterministic_plan(prompt: str, frame: pd.DataFrame) -> AnalysisPlan:
    text = prompt.lower()
    columns = list(frame.columns)
    numeric = list(frame.select_dtypes(include="number").columns)
    dates = list(frame.select_dtypes(include=["datetime", "datetimetz"]).columns)
    categorical = [column for column in columns if column not in numeric and column not in dates]
    mentioned = _mentions(prompt, columns)
    measures = [column for column in mentioned if column in numeric] or numeric[:3]
    dimensions = [column for column in mentioned if column in categorical]
    if not dimensions:
        dimensions = [column for column in categorical if frame[column].nunique(dropna=True) <= 30][:2]
    date_field = next((column for column in mentioned if column in dates), dates[0] if dates else None)
    analyses = ["descriptive"]
    if any(word in text for word in ("why", "driver", "correlation", "diagnostic", "cause")):
        analyses.append("diagnostic")
    if any(word in text for word in ("forecast", "predict", "projection", "trend")):
        analyses.append("predictive")
    if any(word in text for word in ("recommend", "optimize", "prescriptive", "scenario", "best")):
        analyses.append("prescriptive")
    target = measures[0] if measures else None
    charts: list[ChartSpec] = []
    if date_field and target:
        charts.append(ChartSpec("line", date_field, target, dimensions[0] if dimensions else None,
                               title=f"{target} over time"))
    if dimensions and target:
        charts.append(ChartSpec("bar", dimensions[0], target, dimensions[1] if len(dimensions) > 1 else None,
                               title=f"{target} by {dimensions[0]}"))
    if len(measures) >= 2:
        charts.append(ChartSpec("scatter", measures[0], measures[1], dimensions[0] if dimensions else None,
                               title=f"{measures[1]} versus {measures[0]}"))
    if target:
        charts.append(ChartSpec("histogram", target, title=f"Distribution of {target}"))
    if not charts and dimensions:
        charts.append(ChartSpec("bar", dimensions[0], title=f"Records by {dimensions[0]}", aggregation="count"))
    periods_match = re.search(r"(\d+)\s*(?:period|month|week|quarter|year)s?", text)
    periods = min(120, max(1, int(periods_match.group(1)))) if periods_match else 6
    plan = AnalysisPlan(prompt.strip(), list(dict.fromkeys(analyses)), dimensions, measures,
                        date_field, target, periods, charts[:6])
    plan.validate(columns)
    return plan


def plan_from_llm_response(content: str, frame: pd.DataFrame) -> AnalysisPlan:
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        raise ValueError("The planning model did not return a JSON object")
    plan = AnalysisPlan.from_dict(json.loads(match.group(0)))
    plan.validate(list(frame.columns))
    return plan


def planning_prompt(user_prompt: str, frame: pd.DataFrame) -> str:
    schema: list[dict[str, Any]] = []
    for column in frame.columns:
        schema.append({
            "name": column,
            "dtype": str(frame[column].dtype),
            "non_null": int(frame[column].notna().sum()),
            "unique": int(frame[column].nunique(dropna=True)),
        })
    return f"""You are an analytics planner. Return JSON only. Never invent columns.
Schema: {json.dumps(schema)}
Request: {user_prompt}
Return: {{"goal": string, "analyses": [descriptive|diagnostic|predictive|prescriptive],
"dimensions": [column], "measures": [numeric column], "date_field": column|null,
"target": numeric column|null, "forecast_periods": integer 1..120,
"charts": [{{"kind": bar|line|scatter|histogram|box|heatmap|treemap|sunburst|map|area|pie,
"x": column|null, "y": column|null, "color": column|null, "size": column|null,
"title": string, "aggregation": sum|mean|median|count}}], "assumptions": [string]}}"""

