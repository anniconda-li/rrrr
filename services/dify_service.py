from __future__ import annotations

import os
from typing import Any

import requests


DEFAULT_DIFY_MAX_CHARS = 60
DEFAULT_DIFY_STYLE = "请用简洁口语回答，控制在60个中文字符以内，适合语音播报。"


class DifyService:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def run_workflow(
        self,
        question: str,
        image_context: str = "",
        device: str = "walkie-01",
        spot_id: str = "",
        user: str | None = None,
        timeout: int = 60,
    ) -> str:
        if not self.base_url:
            raise ValueError("DIFY_BASE_URL is not configured")
        if not self.api_key:
            raise ValueError("DIFY_API_KEY is not configured; set it or run with --mock-dify/--answer")

        url = f"{self.base_url}/workflows/run"
        input_field = os.getenv("DIFY_INPUT_FIELD", "question").strip() or "question"
        max_chars = _get_dify_max_chars()
        style = os.getenv("DIFY_STYLE", DEFAULT_DIFY_STYLE).strip() or DEFAULT_DIFY_STYLE
        inputs = {input_field: question}
        if image_context:
            inputs["image_context"] = image_context
        if device:
            inputs["device"] = device
        if spot_id:
            inputs["spot_id"] = spot_id
        inputs["style"] = style
        inputs["max_chars"] = max_chars
        payload = {
            "inputs": inputs,
            "response_mode": "blocking",
            "user": user or os.getenv("DIFY_USER", device),
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        print(f"[DifyService] workflow start user={payload['user']} inputs={list(inputs.keys())}", flush=True)
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            raise RuntimeError(f"Dify workflow request failed: {exc}") from exc

        if not 200 <= response.status_code < 300:
            raise RuntimeError(
                f"Dify workflow HTTP {response.status_code}: {response.text}"
            )

        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Dify workflow returned invalid JSON: {response.text}") from exc

        answer = _extract_answer(data)
        if not isinstance(answer, str) or not answer.strip():
            print(f"[DifyService] missing answer in response: {_safe_dump_response(data)}", flush=True)
            raise RuntimeError("Dify workflow response missing answer text")

        answer_chars = len(answer)
        print(f"[DIFY] answer chars={answer_chars}", flush=True)
        if answer_chars > max_chars * 2:
            print("[DIFY] warning: answer is long for device playback", flush=True)
        print(f"[DifyService] workflow answer received chars={answer_chars}", flush=True)
        return answer.strip()


def _extract_answer(data: dict[str, Any]) -> str:
    root_answer = data.get("answer")
    if isinstance(root_answer, str) and root_answer.strip():
        return root_answer.strip()
    root_text = data.get("text")
    if isinstance(root_text, str) and root_text.strip():
        return root_text.strip()

    data_obj = data.get("data")
    if isinstance(data_obj, dict):
        outputs = data_obj.get("outputs")
        if isinstance(outputs, dict):
            output_answer = outputs.get("answer")
            if isinstance(output_answer, str) and output_answer.strip():
                return output_answer.strip()
            output_text = outputs.get("text")
            if isinstance(output_text, str) and output_text.strip():
                return output_text.strip()

        data_answer = data_obj.get("answer")
        if isinstance(data_answer, str) and data_answer.strip():
            return data_answer.strip()
        data_text = data_obj.get("text")
        if isinstance(data_text, str) and data_text.strip():
            return data_text.strip()

    return ""


def _safe_dump_response(data: Any) -> Any:
    if isinstance(data, dict):
        return data
    try:
        return dict(data)
    except Exception:
        return type(data).__name__


def _get_dify_max_chars() -> int:
    raw_value = os.getenv("DIFY_MAX_CHARS", str(DEFAULT_DIFY_MAX_CHARS)).strip()
    try:
        value = int(raw_value)
    except ValueError:
        print(f"[DIFY] invalid DIFY_MAX_CHARS={raw_value!r}; using {DEFAULT_DIFY_MAX_CHARS}", flush=True)
        return DEFAULT_DIFY_MAX_CHARS
    if value <= 0:
        print(f"[DIFY] invalid DIFY_MAX_CHARS={raw_value!r}; using {DEFAULT_DIFY_MAX_CHARS}", flush=True)
        return DEFAULT_DIFY_MAX_CHARS
    return value
