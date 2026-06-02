from __future__ import annotations

import base64
import binascii
import math
import os
import sys
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from urllib.parse import urlparse

import requests

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
ERROR_TEXT = "抱歉，当前导游服务暂时不可用。"


def _log(message: str) -> None:
    print(f"[TTS] {message}", flush=True)


def _pcm16_wav(pcm: bytes) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        path = Path(tmp.name)
    try:
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm)
        return path.read_bytes()
    finally:
        path.unlink(missing_ok=True)


def _silence_wav(duration_seconds: float = 1.0) -> bytes:
    samples = max(1, int(SAMPLE_RATE * duration_seconds))
    return _pcm16_wav(b"\x00\x00" * samples)


def _mock_tts_wav(text: str) -> bytes:
    duration_seconds = min(max(1.0, len(text) * 0.09), 8.0)
    sample_count = int(SAMPLE_RATE * duration_seconds)
    amplitude = 4500
    pcm = bytearray()
    for i in range(sample_count):
        envelope = min(i / 800, (sample_count - i) / 800, 1.0)
        value = int(amplitude * max(envelope, 0.0) * math.sin(2 * math.pi * 440 * i / SAMPLE_RATE))
        pcm.extend(struct.pack("<h", value))
    return _pcm16_wav(bytes(pcm))


def _validate_wav_16k(wav_bytes: bytes) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        path = Path(tmp.name)
        tmp.write(wav_bytes)
    try:
        with wave.open(str(path), "rb") as wf:
            if wf.getnchannels() != CHANNELS:
                raise RuntimeError(f"invalid channels: {wf.getnchannels()}")
            if wf.getframerate() != SAMPLE_RATE:
                raise RuntimeError(f"invalid sample rate: {wf.getframerate()}")
            if wf.getsampwidth() != SAMPLE_WIDTH:
                raise RuntimeError(f"invalid sample width: {wf.getsampwidth()}")
            if wf.getcomptype() != "NONE":
                raise RuntimeError(f"invalid compression: {wf.getcomptype()}")
        return wav_bytes
    finally:
        path.unlink(missing_ok=True)


def _convert_with_ffmpeg(input_path: Path, output_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to convert DashScope TTS audio to 16k mono WAV")

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-ac",
        str(CHANNELS),
        "-ar",
        str(SAMPLE_RATE),
        "-sample_fmt",
        "s16",
        str(output_path),
    ]
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        startupinfo=startupinfo,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()}")


def ensure_wav_16k_mono(audio_bytes: bytes, input_suffix: str = ".wav") -> bytes:
    if not audio_bytes:
        raise RuntimeError("empty audio bytes cannot be converted")

    try:
        return _validate_wav_16k(audio_bytes)
    except Exception as exc:
        _log(f"TTS audio needs conversion: {exc}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        suffix = input_suffix if input_suffix.startswith(".") else f".{input_suffix}"
        input_path = Path(tmp_dir) / f"tts_input{suffix}"
        output_path = Path(tmp_dir) / "tts_16k.wav"
        input_path.write_bytes(audio_bytes)
        _convert_with_ffmpeg(input_path, output_path)
        return _validate_wav_16k(output_path.read_bytes())


def _response_to_dict(response) -> dict:
    if isinstance(response, dict):
        return response
    to_dict = getattr(response, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    data: dict[str, object] = {}
    for name in ("status_code", "code", "message", "output", "usage", "request_id"):
        if hasattr(response, name):
            data[name] = getattr(response, name)
    return data


def _find_audio_url(value) -> str | None:
    if isinstance(value, dict):
        audio = value.get("audio")
        if isinstance(audio, dict):
            url = audio.get("url")
            if isinstance(url, str) and url:
                return url
        url = value.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            return url
        for child in value.values():
            found = _find_audio_url(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_audio_url(child)
            if found:
                return found
    return None


def _find_audio_bytes(value) -> tuple[bytes, str] | None:
    if isinstance(value, (bytes, bytearray)) and value:
        return bytes(value), ".wav"
    if isinstance(value, str) and value:
        if value.startswith("data:"):
            header, _, payload = value.partition(",")
            if ";base64" in header and payload:
                suffix = ".mp3" if "mpeg" in header or "mp3" in header else ".wav"
                return base64.b64decode(payload), suffix
        try:
            decoded = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            decoded = b""
        if decoded:
            return decoded, ".wav"
    if isinstance(value, dict):
        for key in ("data", "audio", "content", "bytes", "base64", "audio_data"):
            if key in value:
                found = _find_audio_bytes(value[key])
                if found:
                    return found
        for child in value.values():
            found = _find_audio_bytes(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_audio_bytes(child)
            if found:
                return found
    return None


def _suffix_from_url(url: str, content_type: str = "") -> str:
    path_suffix = Path(urlparse(url).path).suffix.lower()
    if path_suffix in {".wav", ".mp3", ".m4a", ".aac", ".pcm", ".ogg", ".flac"}:
        return path_suffix
    content_type = content_type.lower()
    if "mpeg" in content_type or "mp3" in content_type:
        return ".mp3"
    if "wav" in content_type or "wave" in content_type:
        return ".wav"
    return ".audio"


def _download_audio(url: str) -> tuple[bytes, str]:
    response = requests.get(url, timeout=120)
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"DashScope TTS audio download failed HTTP {response.status_code}: {response.text[:500]}")
    audio = response.content
    if not audio:
        raise RuntimeError("DashScope TTS audio URL returned empty body")
    return audio, _suffix_from_url(url, response.headers.get("content-type", ""))


def _synthesize_with_dashscope(text: str) -> bytes:
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is not configured")

    import dashscope

    dashscope.api_key = api_key

    model = os.getenv("TTS_MODEL", os.getenv("DASHSCOPE_TTS_MODEL", "qwen3-tts-flash")).strip()
    voice = os.getenv("TTS_VOICE", os.getenv("DASHSCOPE_TTS_VOICE", "Cherry")).strip()
    _log("provider=dashscope")
    _log(f"model={model}")
    _log(f"voice={voice}")

    response = dashscope.MultiModalConversation.call(
        model=model,
        text=text,
        voice=voice,
    )
    response_data = _response_to_dict(response)
    status_code = response_data.get("status_code", getattr(response, "status_code", None))
    if status_code not in (None, 200):
        message = response_data.get("message", getattr(response, "message", ""))
        code = response_data.get("code", getattr(response, "code", ""))
        raise RuntimeError(f"DashScope TTS failed status={status_code} code={code} message={message}")

    audio_url = _find_audio_url(response_data)
    if audio_url:
        audio_bytes, suffix = _download_audio(audio_url)
    else:
        found = _find_audio_bytes(response_data)
        if not found:
            raise RuntimeError(f"DashScope TTS response has no audio url or bytes: {response_data}")
        audio_bytes, suffix = found

    _log(f"received audio bytes={len(audio_bytes)}")
    wav_bytes = ensure_wav_16k_mono(audio_bytes, suffix)
    _log(f"final wav bytes={len(wav_bytes)}")
    return wav_bytes


def synthesize_wav_16k(text: str) -> bytes:
    provider = os.getenv("TTS_PROVIDER", "mock").strip().lower() or "mock"
    safe_text = text.strip() or ERROR_TEXT

    if provider == "mock":
        _log("using mock TTS; generated tone cannot be semantically recognized by ASR")
        return _mock_tts_wav(safe_text)
    if provider == "dashscope":
        return _synthesize_with_dashscope(safe_text)

    raise ValueError(f"unsupported TTS_PROVIDER: {provider}")


def synthesize_fallback_wav_16k(text: str = ERROR_TEXT) -> bytes:
    try:
        return _mock_tts_wav(text)
    except Exception as exc:
        _log(f"fallback mock TTS failed: {exc}; returning 1s silence")
        return _silence_wav(1.0)
