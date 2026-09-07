# Architecture

```text
file/live adapter -> normalized DataFrame -> schema-aware planner -> reviewed AnalysisPlan
                   -> analysis modules -> Plotly figures + tables + findings
                   -> HTML/static exports
                   -> Hyper extract -> Tableau Cloud/Server REST publish
                   -> reviewed public package -> Tableau Public manual publish
```

Core modules:

- `data.py`: validated file loading and safe column names.
- `planner.py`: offline planning, JSON parsing, and schema enforcement.
- `llm.py`: optional OpenAI-compatible planner request; no silent transmission.
- `analysis.py`: descriptive, diagnostic, predictive, and prescriptive modules.
- `visuals.py`: Plotly figure factory and responsive dashboard HTML.
- `tableau.py`: official Hyper creation, Cloud/Server PAT publishing, Public package.
- `pipeline.py`: orchestration and reproducible output writer.
- `app.py`: Streamlit review and delivery interface.

The application separates planning from execution so a model cannot directly run arbitrary Python
or SQL. Plans can reference only existing dataset columns and enumerated analysis/chart types.

