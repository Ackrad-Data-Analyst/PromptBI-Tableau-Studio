from __future__ import annotations

import json
import os
import urllib.request

import pandas as pd

from .models import AnalysisPlan
from .planner import plan_from_llm_response, planning_prompt


def create_plan_with_llm(prompt: str, frame: pd.DataFrame, *, url: str | None = None,
                         model: str | None = None, api_key: str | None = None) -> AnalysisPlan:
    endpoint = url or os.getenv("PROMPTBI_LLM_URL", "https://api.openai.com/v1/chat/completions")
    selected_model = model or os.getenv("PROMPTBI_LLM_MODEL", "gpt-5-mini")
    secret = api_key or os.getenv("PROMPTBI_LLM_API_KEY")
    if not secret:
        raise ValueError("Set PROMPTBI_LLM_API_KEY or use the deterministic planner")
    body = json.dumps({
        "model": selected_model,
        "messages": [{"role": "user", "content": planning_prompt(prompt, frame)}],
        "temperature": 0,
    }).encode("utf-8")
    request = urllib.request.Request(endpoint, body, {
        "Authorization": f"Bearer {secret}", "Content-Type": "application/json"
    })
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = json.load(response)
    content = payload["choices"][0]["message"]["content"]
    return plan_from_llm_response(content, frame)

