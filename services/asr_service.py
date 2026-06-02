from __future__ import annotations

import os
from http import HTTPStatus
from pathlib import Path
from typing import Any


MOCK_TEXT = "大雁塔有什么故事？"


def _log(message: str) -> None:
    print(f"[ASR] {message}", flush=True)


def _safe_dump_result(result: Any) -> Any:
    if isinstance(result, dict):
        return dict(result)
    try:
        result_dict = getattr(result, "__dict__", None)
        if isinstance(result_dict, dict):
            return dict(result_dict)
    except Exception:
        pass
    return type(result).__name__


def _result_to_dict(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result

    data: dict[str, Any] = {}
    for name in ("status_code", "code", "message", "output", "usage", "request_id"):
        try:
            if hasattr(result, name):
                data[name] = getattr(result, name)
        except Exception:
            pass
    return data


def _extract_sentence(result: Any) -> str:
    get_sentence = getattr(result, "get_sentence", None)
    if callable(get_sentence):
        try:
            sentence = get_sentence()
            if isinstance(sentence, str) and sentence.strip():
                return sentence.strip()
        except Exception:
            pass

    result_dict = _result_to_dict(result)
    if isinstance(result_dict.get("text"), str) and result_dict["text"].strip():
        return result_dict["text"].strip()

    output = result_dict.get("output")
    if isinstance(output, dict):
        sentence = output.get("sentence")
        if isinstance(sentence, dict):
            sentence_text = sentence.get("text")
            if isinstance(sentence_text, str) and sentence_text.strip():
                return sentence_text.strip()
        if isinstance(sentence, list):
            parts = [
                item.get("text", "").strip()
                for item in sentence
                if isinstance(item, dict) and isinstance(item.get("text"), str) and item.get("text", "").strip()
            ]
            if parts:
                return "".join(parts)
        if isinstance(sentence, str) and sentence.strip():
            return sentence.strip()
        output_text = output.get("text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        sentences = output.get("sentences")
        if isinstance(sentences, list):
            parts = [
                item.get("text", "")
                for item in sentences
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            ]
            text = "".join(parts).strip()
            if text:
                return text

    raise RuntimeError(f"DashScope ASR response has no recognizable text: {_safe_dump_result(result)}")


def _transcribe_with_dashscope(wav_path: Path) -> str:
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is not configured")
    if not wav_path.exists():
        raise FileNotFoundError(wav_path)

    import dashscope
    from dashscope.audio.asr import Recognition

    dashscope.api_key = api_key
    dashscope.base_websocket_api_url = os.getenv(
        "DASHSCOPE_WEBSOCKET_URL",
        "wss://dashscope.aliyuncs.com/api-ws/v1/inference",
    )

    recognition = Recognition(
        model=os.getenv("ASR_MODEL", "paraformer-realtime-v2"),
        format="wav",
        sample_rate=16000,
        language_hints=["zh", "en"],
        callback=None,
    )
    result = recognition.call(str(wav_path))
    status_code = getattr(result, "status_code", None)
    if status_code != HTTPStatus.OK:
        message = getattr(result, "message", "")
        raise RuntimeError(f"DashScope ASR failed status={status_code} message={message}")

    text = _extract_sentence(result)
    _log(f"recognized chars={len(text)}")
    return text


def transcribe_wav(wav_path: str | Path) -> str:
    provider = os.getenv("ASR_PROVIDER", "mock").strip().lower() or "mock"

    if provider == "mock":
        _log("using mock ASR; returning fixed text")
        return MOCK_TEXT
    if provider == "dashscope":
        return _transcribe_with_dashscope(Path(wav_path))

    raise ValueError(f"unsupported ASR_PROVIDER: {provider}")
