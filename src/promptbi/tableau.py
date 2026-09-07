from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd


def _hyper_type(dtype: Any):
    from tableauhyperapi import SqlType
    if pd.api.types.is_bool_dtype(dtype):
        return SqlType.bool()
    if pd.api.types.is_integer_dtype(dtype):
        return SqlType.big_int()
    if pd.api.types.is_float_dtype(dtype):
        return SqlType.double()
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return SqlType.timestamp()
    return SqlType.text()


def create_hyper(frame: pd.DataFrame, target: str | Path, table_name: str = "Extract") -> Path:
    try:
        from tableauhyperapi import (
            Connection, CreateMode, HyperProcess, Inserter, Nullability, TableDefinition,
            TableName, Telemetry,
        )
    except ImportError as exc:
        raise RuntimeError("Install Tableau support: pip install -e .[tableau]") from exc
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        TableDefinition.Column(column, _hyper_type(frame[column].dtype), Nullability.NULLABLE)
        for column in frame.columns
    ]
    definition = TableDefinition(TableName("Extract", table_name), columns)
    converted = frame.astype(object).where(pd.notna(frame), None)
    for column in frame.select_dtypes(include=["datetime", "datetimetz"]):
        converted[column] = converted[column].map(lambda value: value.to_pydatetime() if value is not None else None)
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as process:
        with Connection(process.endpoint, str(path), CreateMode.CREATE_AND_REPLACE) as connection:
            connection.catalog.create_schema("Extract")
            connection.catalog.create_table(definition)
            with Inserter(connection, definition) as inserter:
                inserter.add_rows(converted.itertuples(index=False, name=None))
                inserter.execute()
    return path


def _credentials(config: dict[str, str] | None = None) -> dict[str, str]:
    config = config or {}
    mapping = {
        "server_url": "TABLEAU_SERVER_URL", "site_id": "TABLEAU_SITE_ID",
        "token_name": "TABLEAU_PAT_NAME", "token_secret": "TABLEAU_PAT_SECRET",
        "project_name": "TABLEAU_PROJECT_NAME",
    }
    values = {key: config.get(key) or os.getenv(env, "") for key, env in mapping.items()}
    missing = [key for key in ("server_url", "token_name", "token_secret", "project_name") if not values[key]]
    if missing:
        raise ValueError(f"Missing Tableau settings: {missing}")
    return values


def publish_to_cloud_or_server(file_path: str | Path, *, name: str,
                               kind: str = "datasource", overwrite: bool = False,
                               config: dict[str, str] | None = None) -> dict[str, str]:
    try:
        import tableauserverclient as TSC
    except ImportError as exc:
        raise RuntimeError("Install Tableau support: pip install -e .[tableau]") from exc
    values = _credentials(config)
    auth = TSC.PersonalAccessTokenAuth(values["token_name"], values["token_secret"], values["site_id"])
    server = TSC.Server(values["server_url"], use_server_version=True)
    mode = TSC.Server.PublishMode.Overwrite if overwrite else TSC.Server.PublishMode.CreateNew
    with server.auth.sign_in(auth):
        projects, _ = server.projects.get()
        project = next((item for item in projects if item.name == values["project_name"]), None)
        if project is None:
            raise ValueError(f"Tableau project not found: {values['project_name']}")
        if kind == "workbook":
            item = server.workbooks.publish(TSC.WorkbookItem(project.id, name=name), str(file_path), mode)
        elif kind == "datasource":
            item = server.datasources.publish(TSC.DatasourceItem(project.id, name=name), str(file_path), mode)
        else:
            raise ValueError("kind must be 'datasource' or 'workbook'")
        return {"id": item.id, "name": item.name, "project": project.name, "server": values["server_url"]}


def create_tableau_public_bundle(frame: pd.DataFrame, plan: dict[str, Any], target: str | Path,
                                 hyper_path: str | Path | None = None) -> Path:
    """Create a review-first bundle; Tableau Public has no supported REST publishing workflow."""
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    readme = """TABLEAU PUBLIC DELIVERY PACKAGE

1. Review every field for confidential, personal, licensed, or commercially sensitive data.
2. Open Tableau Public Edition and connect to data.csv (or data.hyper when included).
3. Build/review the workbook, then use Server > Tableau Public > Save to Tableau Public.
4. Everything published to Tableau Public is publicly accessible and may be downloadable.

PromptBI intentionally does not send data to an undocumented Tableau Public endpoint.
"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README_PUBLICATION.txt", readme)
        archive.writestr("analysis_plan.json", json.dumps(plan, indent=2, default=str))
        archive.writestr("data.csv", frame.to_csv(index=False))
        if hyper_path:
            source = Path(hyper_path)
            archive.write(source, "data.hyper")
    return path

