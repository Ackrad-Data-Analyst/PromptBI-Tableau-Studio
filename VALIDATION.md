# Validation record

Date: 2026-09-05

- Six core tests passed for schema normalization, profiling, offline prompt planning, LLM-plan
  column enforcement, descriptive/diagnostic/prescriptive execution, and Tableau Public packaging.
- One predictive-model test was skipped because scikit-learn was unavailable in the packaging
  runtime. It is declared as an installation dependency and the code fails safely if unavailable.
- All Python files passed bytecode compilation.
- The final package contains no credentials, `.env`, generated data outputs, Hyper extracts, or
  workbook files.

Live acceptance tests still required by the user:

1. Install the declared dependencies in a clean Python 3.11+ virtual environment.
2. Run the Streamlit interface and the full test suite.
3. Create a Hyper file and open it in the intended Tableau version.
4. Publish to a non-production Tableau project using a limited PAT.
5. Confirm site permissions, refresh behavior, field types, dashboard performance, and row counts.

No test publishes data or contacts a Tableau site.

