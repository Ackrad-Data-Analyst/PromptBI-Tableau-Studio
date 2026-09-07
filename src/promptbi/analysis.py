from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .models import AnalysisPlan


@dataclass(slots=True)
class AnalysisOutputs:
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


def _safe_number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if np.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def profile(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in frame.columns:
        series = frame[column]
        rows.append({
            "column": column,
            "dtype": str(series.dtype),
            "rows": len(series),
            "non_null": int(series.notna().sum()),
            "missing_pct": round(float(series.isna().mean() * 100), 3),
            "unique": int(series.nunique(dropna=True)),
            "min": _safe_number(series.min()) if pd.api.types.is_numeric_dtype(series) else None,
            "max": _safe_number(series.max()) if pd.api.types.is_numeric_dtype(series) else None,
            "mean": _safe_number(series.mean()) if pd.api.types.is_numeric_dtype(series) else None,
        })
    return pd.DataFrame(rows)


def _descriptive(frame: pd.DataFrame, plan: AnalysisPlan, output: AnalysisOutputs) -> None:
    output.tables["data_profile"] = profile(frame)
    if plan.measures:
        output.tables["numeric_summary"] = frame[plan.measures].describe().T.reset_index(names="measure")
    if plan.dimensions and plan.measures:
        dimension = plan.dimensions[0]
        grouped = frame.groupby(dimension, dropna=False)[plan.measures].agg(["count", "sum", "mean", "median"])
        grouped.columns = [f"{measure}_{stat}" for measure, stat in grouped.columns]
        output.tables["group_summary"] = grouped.reset_index().sort_values(
            f"{plan.measures[0]}_sum", ascending=False
        )
        leader = output.tables["group_summary"].iloc[0]
        output.findings.append(
            f"Highest total {plan.measures[0]}: {dimension}={leader[dimension]!r}."
        )
    high_missing = output.tables["data_profile"].query("missing_pct >= 20")
    if len(high_missing):
        output.warnings.append(
            "Columns with at least 20% missing values: " + ", ".join(high_missing["column"].astype(str))
        )


def _diagnostic(frame: pd.DataFrame, plan: AnalysisPlan, output: AnalysisOutputs) -> None:
    numeric = frame.select_dtypes(include="number")
    if numeric.shape[1] >= 2:
        corr = numeric.corr(numeric_only=True)
        output.tables["correlation_matrix"] = corr.reset_index(names="measure")
        pairs = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool)).stack().abs().sort_values(ascending=False)
        if len(pairs):
            first = pairs.index[0]
            signed = corr.loc[first[0], first[1]]
            output.findings.append(
                f"Strongest observed numeric association: {first[0]} and {first[1]} (r={signed:.3f})."
            )
    target = plan.target
    if target and target in numeric:
        q1, q3 = numeric[target].quantile([0.25, 0.75])
        iqr = q3 - q1
        mask = (numeric[target] < q1 - 1.5 * iqr) | (numeric[target] > q3 + 1.5 * iqr)
        output.tables["target_outliers"] = frame.loc[mask].copy()
        output.findings.append(f"IQR screening flagged {int(mask.sum())} possible {target} outliers.")
    output.warnings.append("Associations are diagnostic signals, not proof of causation.")


def _predictive(frame: pd.DataFrame, plan: AnalysisPlan, output: AnalysisOutputs) -> None:
    target = plan.target
    numeric = list(frame.select_dtypes(include="number").columns)
    if not target or target not in numeric:
        output.warnings.append("Predictive analysis skipped: choose a numeric target.")
        return
    features = [column for column in numeric if column != target]
    clean = frame[[target] + features].dropna()
    if features and len(clean) >= 20:
        try:
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.metrics import mean_absolute_error, r2_score
            from sklearn.model_selection import train_test_split

            x_train, x_test, y_train, y_test = train_test_split(
                clean[features], clean[target], test_size=0.25, random_state=42
            )
            model = RandomForestRegressor(n_estimators=150, random_state=42, n_jobs=-1)
            model.fit(x_train, y_train)
            predicted = model.predict(x_test)
            output.metrics.update({
                "predictive_rows": len(clean),
                "holdout_mae": float(mean_absolute_error(y_test, predicted)),
                "holdout_r2": float(r2_score(y_test, predicted)),
            })
            output.tables["feature_importance"] = pd.DataFrame({
                "feature": features, "importance": model.feature_importances_
            }).sort_values("importance", ascending=False)
            output.findings.append(
                f"Holdout model for {target}: MAE={output.metrics['holdout_mae']:.3g}, "
                f"R²={output.metrics['holdout_r2']:.3f}."
            )
        except ImportError:
            output.warnings.append("scikit-learn is not installed; predictive model skipped.")
    if plan.date_field:
        timeline = frame[[plan.date_field, target]].dropna().copy()
        timeline = timeline.groupby(plan.date_field, as_index=False)[target].sum().sort_values(plan.date_field)
        if len(timeline) >= 3:
            x = np.arange(len(timeline), dtype=float)
            slope, intercept = np.polyfit(x, timeline[target].astype(float), 1)
            future_x = np.arange(len(timeline), len(timeline) + plan.forecast_periods)
            inferred = pd.infer_freq(pd.DatetimeIndex(timeline[plan.date_field]))
            if inferred:
                future_dates = pd.date_range(timeline[plan.date_field].iloc[-1], periods=plan.forecast_periods + 1,
                                             freq=inferred)[1:]
            else:
                future_dates = future_x
                output.warnings.append("Date frequency could not be inferred; forecast periods use an ordinal index.")
            output.tables["trend_forecast"] = pd.DataFrame({
                plan.date_field: future_dates,
                f"forecast_{target}": intercept + slope * future_x,
            })
            output.warnings.append("Trend forecast is a baseline extrapolation, not a validated operational forecast.")


def _prescriptive(frame: pd.DataFrame, plan: AnalysisPlan, output: AnalysisOutputs) -> None:
    target = plan.target
    if not target or target not in frame.select_dtypes(include="number"):
        output.warnings.append("Prescriptive analysis skipped: choose a numeric objective measure.")
        return
    if plan.dimensions:
        dimension = plan.dimensions[0]
        ranking = frame.groupby(dimension, dropna=False)[target].agg(["sum", "mean", "median", "count"]).reset_index()
        ranking["rank_by_mean"] = ranking["mean"].rank(ascending=False, method="dense").astype(int)
        output.tables["prescriptive_ranking"] = ranking.sort_values(["rank_by_mean", "count"], ascending=[True, False])
        best = output.tables["prescriptive_ranking"].iloc[0]
        output.findings.append(
            f"Screening candidate: {dimension}={best[dimension]!r} has the highest observed mean {target}."
        )
    else:
        q75 = frame[target].quantile(0.75)
        output.tables["high_value_candidates"] = frame.loc[frame[target] >= q75].copy()
        output.findings.append(f"Selected records at or above the 75th percentile of {target} for review.")
    output.warnings.append(
        "Recommendations rank observed data only; add real costs, constraints, uncertainty, and decision authority before action."
    )


def run_modules(frame: pd.DataFrame, plan: AnalysisPlan) -> AnalysisOutputs:
    output = AnalysisOutputs(metrics={"rows": len(frame), "columns": len(frame.columns)})
    if "descriptive" in plan.analyses:
        _descriptive(frame, plan, output)
    if "diagnostic" in plan.analyses:
        _diagnostic(frame, plan, output)
    if "predictive" in plan.analyses:
        _predictive(frame, plan, output)
    if "prescriptive" in plan.analyses:
        _prescriptive(frame, plan, output)
    return output

