from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
import importlib.util
from pathlib import Path

import pandas as pd

from promptbi.analysis import profile, run_modules
from promptbi.data import normalize_frame
from promptbi.models import AnalysisPlan
from promptbi.planner import deterministic_plan, plan_from_llm_response
from promptbi.tableau import create_tableau_public_bundle


def sample() -> pd.DataFrame:
    return normalize_frame(pd.DataFrame({
        "Date": pd.date_range("2025-01-01", periods=30, freq="MS"),
        "Region": ["A", "B", "C"] * 10,
        "Revenue": [100 + index * 4 for index in range(30)],
        "Cost": [70 + index * 2 for index in range(30)],
        "Risk Score": [index % 7 for index in range(30)],
    }))


class PromptBITests(unittest.TestCase):
    def test_columns_are_safe_and_unique(self):
        result = normalize_frame(pd.DataFrame([[1, 2, 3]], columns=["Risk Score", "Risk Score", "$"]))
        self.assertEqual(list(result.columns), ["Risk_Score", "Risk_Score_2", "column"])

    def test_profile_reports_missingness(self):
        frame = sample()
        frame.loc[0, "Cost"] = None
        table = profile(frame).set_index("column")
        self.assertGreater(table.loc["Cost", "missing_pct"], 0)

    def test_prompt_builds_four_analysis_types(self):
        plan = deterministic_plan(
            "Show Revenue by Region over Date, explain drivers, forecast 12 months and recommend the best option",
            sample(),
        )
        self.assertEqual(set(plan.analyses), {"descriptive", "diagnostic", "predictive", "prescriptive"})
        self.assertEqual(plan.forecast_periods, 12)
        self.assertEqual(plan.target, "Revenue")

    def test_llm_plan_rejects_unknown_columns(self):
        content = json.dumps({"goal": "x", "analyses": ["descriptive"], "measures": ["Invented"]})
        with self.assertRaises(ValueError):
            plan_from_llm_response(content, sample())

    def test_analysis_produces_tables_and_findings(self):
        plan = deterministic_plan("Revenue by Region and explain correlation and recommend best", sample())
        output = run_modules(sample(), plan)
        self.assertIn("data_profile", output.tables)
        self.assertIn("correlation_matrix", output.tables)
        self.assertTrue(output.findings)

    @unittest.skipUnless(importlib.util.find_spec("sklearn"), "scikit-learn not installed in validation runtime")
    def test_predictive_metrics_use_holdout(self):
        plan = AnalysisPlan("forecast", ["predictive"], ["Region"], ["Revenue", "Cost"],
                            "Date", "Revenue", 3, [])
        output = run_modules(sample(), plan)
        self.assertIn("holdout_mae", output.metrics)
        self.assertIn("trend_forecast", output.tables)

    def test_public_bundle_contains_warning_and_data(self):
        with tempfile.TemporaryDirectory() as folder:
            target = create_tableau_public_bundle(sample(), {"goal": "test"}, Path(folder) / "public.zip")
            with zipfile.ZipFile(target) as archive:
                self.assertIn("data.csv", archive.namelist())
                self.assertIn("publicly accessible", archive.read("README_PUBLICATION.txt").decode())


if __name__ == "__main__":
    unittest.main()
