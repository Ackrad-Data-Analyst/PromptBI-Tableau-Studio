from __future__ import annotations

import io
import re
from pathlib import Path
from typing import BinaryIO

import pandas as pd


SUPPORTED = {".csv", ".xlsx", ".xls", ".parquet", ".json", ".jsonl"}


def clean_column_name(value: object) -> str:
    name = re.sub(r"\s+", "_", str(value).strip())
    name = re.sub(r"[^A-Za-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_") or "column"
    return name[:128]


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    used: dict[str, int] = {}
    names: list[str] = []
    for raw in result.columns:
        base = clean_column_name(raw)
        used[base] = used.get(base, 0) + 1
        names.append(base if used[base] == 1 else f"{base}_{used[base]}")
    result.columns = names
    for column in result.select_dtypes(include=["object", "string"]):
        sample = result[column].dropna().astype(str).head(100)
        if len(sample) and sample.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}").mean() >= 0.8:
            result[column] = pd.to_datetime(result[column], errors="coerce")
    return result


def load_data(source: str | Path | BinaryIO, filename: str | None = None) -> pd.DataFrame:
    if isinstance(source, (str, Path)):
        path = Path(source)
        suffix = path.suffix.lower()
        handle: str | Path | BinaryIO = path
    else:
        suffix = Path(filename or "").suffix.lower()
        handle = source
    if suffix not in SUPPORTED:
        raise ValueError(f"Unsupported file type {suffix!r}; expected {sorted(SUPPORTED)}")
    if suffix == ".csv":
        frame = pd.read_csv(handle)
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(handle)
    elif suffix == ".parquet":
        frame = pd.read_parquet(handle)
    else:
        try:
            frame = pd.read_json(handle, lines=suffix == ".jsonl")
        except ValueError:
            if hasattr(handle, "seek"):
                handle.seek(0)
            frame = pd.read_json(handle)
    if frame.empty:
        raise ValueError("The dataset has no rows")
    return normalize_frame(frame)


def frame_from_bytes(content: bytes, filename: str) -> pd.DataFrame:
    return load_data(io.BytesIO(content), filename)
