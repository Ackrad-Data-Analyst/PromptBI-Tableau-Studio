from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .models import ChartSpec


AGGREGATIONS = {
    "sum": "sum", "mean": "mean", "median": "median", "count": "count"
}


def _aggregate(frame: pd.DataFrame, spec: ChartSpec) -> pd.DataFrame:
    if not spec.x or spec.kind in {"scatter", "histogram", "box", "map"}:
        return frame
    if spec.y:
        return frame.groupby([item for item in (spec.x, spec.color) if item], dropna=False, as_index=False).agg(
            **{spec.y: (spec.y, AGGREGATIONS.get(spec.aggregation, "sum"))}
        )
    grouped = frame.groupby([item for item in (spec.x, spec.color) if item], dropna=False).size()
    return grouped.rename("record_count").reset_index()


def create_figure(frame: pd.DataFrame, spec: ChartSpec) -> go.Figure:
    data = _aggregate(frame, spec)
    y = spec.y or ("record_count" if "record_count" in data else None)
    common = {"data_frame": data, "x": spec.x, "y": y, "color": spec.color, "title": spec.title}
    if spec.kind == "bar":
        fig = px.bar(**common)
    elif spec.kind == "line":
        fig = px.line(**common, markers=True)
    elif spec.kind == "area":
        fig = px.area(**common)
    elif spec.kind == "scatter":
        fig = px.scatter(**common, size=spec.size, hover_data=list(data.columns[:12]))
    elif spec.kind == "histogram":
        fig = px.histogram(data, x=spec.x, color=spec.color, title=spec.title, marginal="box")
    elif spec.kind == "box":
        fig = px.box(**common, points="outliers")
    elif spec.kind == "pie":
        fig = px.pie(data, names=spec.x, values=y, title=spec.title)
    elif spec.kind == "treemap":
        path = [item for item in (spec.color, spec.x) if item]
        fig = px.treemap(data, path=path, values=y, title=spec.title)
    elif spec.kind == "sunburst":
        path = [item for item in (spec.color, spec.x) if item]
        fig = px.sunburst(data, path=path, values=y, title=spec.title)
    elif spec.kind == "heatmap":
        corr = frame.select_dtypes(include="number").corr(numeric_only=True)
        fig = px.imshow(corr, text_auto=".2f", aspect="auto", title=spec.title or "Correlation heatmap")
    elif spec.kind == "map":
        lower = {column.lower(): column for column in frame.columns}
        lat = lower.get("latitude") or lower.get("lat")
        lon = lower.get("longitude") or lower.get("lon") or lower.get("lng")
        if not lat or not lon:
            raise ValueError("Map charts require latitude/longitude or lat/lon columns")
        fig = px.scatter_map(frame, lat=lat, lon=lon, color=spec.color, size=spec.size,
                             hover_name=spec.x, title=spec.title, zoom=3)
    else:
        raise ValueError(f"Unsupported chart type: {spec.kind}")
    fig.update_layout(template="plotly_white", margin=dict(l=30, r=30, t=65, b=35), height=480)
    return fig


def dashboard_html(figures: list[go.Figure], title: str, findings: list[str], warnings: list[str]) -> str:
    cards = "".join(
        f'<div class="note">{item}</div>' for item in findings
    ) or '<div class="note">No narrative finding was generated.</div>'
    cautions = "".join(f"<li>{item}</li>" for item in warnings)
    plots = "".join(
        f'<section class="chart">{figure.to_html(full_html=False, include_plotlyjs="cdn")}</section>'
        for figure in figures
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:Inter,Segoe UI,sans-serif;background:#f4f7fb;color:#142033;margin:0}}
main{{max-width:1440px;margin:auto;padding:28px}}h1{{letter-spacing:-.03em}}.grid{{display:grid;
grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:18px}}.chart,.note,.warnings{{background:white;
border:1px solid #dfe7f1;border-radius:14px;padding:14px;box-shadow:0 6px 24px #16324f12}}
.notes{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin:18px 0}}
.warnings{{margin-top:18px;border-left:5px solid #d98e04}}</style></head><body><main><h1>{title}</h1>
<div class="notes">{cards}</div><div class="grid">{plots}</div>
<div class="warnings"><strong>Review notes</strong><ul>{cautions}</ul></div></main></body></html>"""


def write_dashboard(path: str | Path, figures: list[go.Figure], title: str,
                    findings: list[str], warnings: list[str]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dashboard_html(figures, title, findings, warnings), encoding="utf-8")
    return target


def export_static(figures: list[go.Figure], directory: str | Path) -> list[Path]:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    outputs = []
    for index, figure in enumerate(figures, 1):
        target = root / f"chart_{index:02d}.png"
        figure.write_image(target, width=1600, height=900, scale=1.5)
        outputs.append(target)
    return outputs

