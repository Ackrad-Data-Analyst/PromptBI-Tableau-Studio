from __future__ import annotations

import io
import json
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

from promptbi.data import frame_from_bytes
from promptbi.llm import create_plan_with_llm
from promptbi.models import AnalysisPlan
from promptbi.pipeline import AnalysisResult, run_analysis
from promptbi.planner import deterministic_plan
from promptbi.tableau import create_hyper, create_tableau_public_bundle, publish_to_cloud_or_server


st.set_page_config(page_title="PromptBI Studio", page_icon="📊", layout="wide")
st.title("PromptBI Studio")
st.caption("Prompt → reviewable analysis plan → verified outputs → Tableau delivery")


def result_zip(result: AnalysisResult) -> bytes:
    with tempfile.TemporaryDirectory() as folder:
        root = result.write(Path(folder) / "PromptBI_Output")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in root.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(root.parent).as_posix())
        return buffer.getvalue()


with st.sidebar:
    st.header("1 · Data")
    uploaded = st.file_uploader("CSV, Excel, Parquet, JSON or JSONL", type=["csv", "xlsx", "xls", "parquet", "json", "jsonl"])
    st.header("2 · Planner")
    use_llm = st.toggle("Use optional LLM planner", False)
    if use_llm:
        llm_url = st.text_input("OpenAI-compatible endpoint", "https://api.openai.com/v1/chat/completions")
        llm_model = st.text_input("Model", "gpt-5-mini")
        llm_key = st.text_input("API key (memory only)", type="password")

if uploaded:
    try:
        fingerprint = (uploaded.name, uploaded.size)
        if st.session_state.get("fingerprint") != fingerprint:
            st.session_state.frame = frame_from_bytes(uploaded.getvalue(), uploaded.name)
            st.session_state.fingerprint = fingerprint
            st.session_state.pop("result", None)
        frame = st.session_state.frame
    except Exception as exc:
        st.error(f"Could not read the file: {exc}")
        st.stop()

    data_tab, plan_tab, results_tab, tableau_tab = st.tabs(["Data", "Prompt & plan", "Results", "Tableau delivery"])
    with data_tab:
        a, b, c = st.columns(3)
        a.metric("Rows", f"{len(frame):,}")
        b.metric("Columns", len(frame.columns))
        c.metric("Missing cells", f"{int(frame.isna().sum().sum()):,}")
        st.dataframe(frame.head(1000), use_container_width=True, height=500)

    with plan_tab:
        prompt = st.text_area("What should the analysis answer?", height=130,
                              placeholder="Compare total cost and output by region, identify drivers, forecast the next 12 months, and recommend priorities.")
        if st.button("Create analysis plan", type="primary", disabled=not prompt.strip()):
            try:
                plan = (create_plan_with_llm(prompt, frame, url=llm_url, model=llm_model, api_key=llm_key)
                        if use_llm else deterministic_plan(prompt, frame))
                st.session_state.plan_json = json.dumps(plan.to_dict(), indent=2)
            except Exception as exc:
                st.error(f"Planning failed: {exc}")
        plan_text = st.text_area("Review/edit plan JSON before execution", value=st.session_state.get("plan_json", ""), height=430)
        if st.button("Run approved plan", disabled=not plan_text.strip()):
            try:
                plan = AnalysisPlan.from_dict(json.loads(plan_text))
                plan.validate(list(frame.columns))
                st.session_state.result = run_analysis(frame, plan.goal, plan)
                st.success("Analysis completed. Open the Results tab.")
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")

    result = st.session_state.get("result")
    with results_tab:
        if not result:
            st.info("Create and run an analysis plan first.")
        else:
            for finding in result.outputs.findings:
                st.success(finding)
            for warning in result.outputs.warnings:
                st.warning(warning)
            for figure in result.figures:
                st.plotly_chart(figure, use_container_width=True)
            with st.expander("Analysis tables", expanded=False):
                for name, table in result.outputs.tables.items():
                    st.subheader(name.replace("_", " ").title())
                    st.dataframe(table, use_container_width=True)
            st.download_button("Download complete analysis ZIP", result_zip(result),
                               "PromptBI_Analysis.zip", "application/zip")

    with tableau_tab:
        if not result:
            st.info("Run an analysis before preparing Tableau delivery files.")
        else:
            st.subheader("Tableau extract and Tableau Public")
            st.warning("Tableau Public is public. Remove confidential, personal, licensed, and commercially sensitive fields first.")
            if st.button("Build Hyper + Public review package"):
                try:
                    with tempfile.TemporaryDirectory() as folder:
                        hyper = create_hyper(frame, Path(folder) / "data.hyper")
                        public = create_tableau_public_bundle(frame, result.plan.to_dict(), Path(folder) / "tableau_public_package.zip", hyper)
                        st.session_state.hyper_bytes = hyper.read_bytes()
                        st.session_state.public_bytes = public.read_bytes()
                    st.success("Tableau delivery files created.")
                except Exception as exc:
                    st.error(f"Tableau extract creation failed: {exc}")
            if st.session_state.get("hyper_bytes"):
                st.download_button("Download data.hyper", st.session_state.hyper_bytes, "data.hyper")
                st.download_button("Download Tableau Public package", st.session_state.public_bytes,
                                   "tableau_public_package.zip", "application/zip")

            st.divider()
            st.subheader("Publish to licensed Tableau Cloud or Server")
            server_url = st.text_input("Server URL", placeholder="https://your-pod.online.tableau.com")
            site_id = st.text_input("Site content URL (blank for Default)")
            project_name = st.text_input("Project name", "Default")
            token_name = st.text_input("Personal Access Token name")
            token_secret = st.text_input("Personal Access Token secret", type="password")
            datasource_name = st.text_input("Published data source name", "PromptBI Analysis Data")
            overwrite = st.checkbox("Overwrite same-named data source")
            if st.button("Publish Hyper data source", disabled=not st.session_state.get("hyper_bytes")):
                try:
                    with tempfile.TemporaryDirectory() as folder:
                        path = Path(folder) / "data.hyper"
                        path.write_bytes(st.session_state.hyper_bytes)
                        published = publish_to_cloud_or_server(path, name=datasource_name, overwrite=overwrite, config={
                            "server_url": server_url, "site_id": site_id, "project_name": project_name,
                            "token_name": token_name, "token_secret": token_secret,
                        })
                    st.success(f"Published {published['name']} to project {published['project']}.")
                except Exception as exc:
                    st.error(f"Publishing failed: {exc}")
else:
    st.info("Upload a dataset to begin. Nothing is transmitted unless you explicitly enable an LLM planner or publish to Tableau.")

