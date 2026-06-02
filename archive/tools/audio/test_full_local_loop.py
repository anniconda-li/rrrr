from __future__ import annotations

import argparse
import shutil
import sys
import wave
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import core.config  # noqa: F401 - loads project .env
from services.asr_service import transcribe_wav
from services.tts_service import synthesize_wav_16k


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "tmp" / "latest"


def inspect_wav(path: Path) -> dict[str, object]:
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.getnframes()
        compression = wf.getcomptype()
        compression_name = wf.getcompname()
        duration = frames / sample_rate if sample_rate else 0.0

    return {
        "channels": channels,
        "sample_width": sample_width,
        "sample_rate": sample_rate,
        "frames": frames,
        "duration": duration,
        "compression": compression,
        "compression_name": compression_name,
    }


def validate_esp_wav(path: Path) -> dict[str, object]:
    info = inspect_wav(path)
    if info["channels"] != 1:
        raise RuntimeError(f"reply WAV channels must be 1, got {info['channels']}")
    if info["sample_width"] != 2:
        raise RuntimeError(f"reply WAV sample_width must be 2, got {info['sample_width']}")
    if info["sample_rate"] != 16000:
        raise RuntimeError(f"reply WAV sample_rate must be 16000, got {info['sample_rate']}")
    if info["compression"] != "NONE":
        raise RuntimeError(f"reply WAV compression must be NONE, got {info['compression']}")
    return info


def simulate_chunk_reassembly(wav_bytes: bytes, chunk_size: int) -> None:
    if chunk_size <= 0:
        raise RuntimeError(f"chunk_size must be positive, got {chunk_size}")

    chunks = [
        wav_bytes[offset : offset + chunk_size]
        for offset in range(0, len(wav_bytes), chunk_size)
    ]
    print(f"total_size: {len(wav_bytes)}")
    print(f"chunk_size: {chunk_size}")
    print(f"chunk_count: {len(chunks)}")

    reassembled = b"".join(chunks)
    if reassembled != wav_bytes:
        raise RuntimeError("chunk reassembly mismatch")
    print("[OK] chunk reassembly matched")


def prepare_output_dir(path_text: str) -> Path:
    output_dir = Path(path_text)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    for child in output_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local WAV -> ASR -> mock answer -> TTS -> chunk loop")
    parser.add_argument("--wav", required=True, help="input WAV file path")
    parser.add_argument("--chunk-size", type=int, default=4096, help="simulated ESP chunk size")
    parser.add_argument("--answer", default="", help="manual reply text; defaults to a mock answer from ASR text")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(PROJECT_ROOT)), help="output directory")
    args = parser.parse_args()

    wav_path = Path(args.wav)
    if not wav_path.exists():
        raise FileNotFoundError(wav_path)

    output_dir = prepare_output_dir(args.out_dir)
    asr_text_path = output_dir / "asr_text.txt"
    answer_text_path = output_dir / "answer.txt"
    reply_wav_path = output_dir / "reply.wav"

    asr_text = transcribe_wav(wav_path)
    asr_text_path.write_text(asr_text, encoding="utf-8")
    print(f"[ASR] text: {asr_text}")

    answer_text = args.answer.strip() if args.answer else f"你好，我是你的 AI 导游。你刚刚说的是：{asr_text}"
    answer_text_path.write_text(answer_text, encoding="utf-8")
    print(f"[ANSWER] text: {answer_text}")

    reply_wav_bytes = synthesize_wav_16k(answer_text)
    reply_wav_path.write_bytes(reply_wav_bytes)
    wav_info = validate_esp_wav(reply_wav_path)
    print(f"[TTS] wav: {reply_wav_path}")
    print(
        "[TTS] format: "
        f"channels={wav_info['channels']} "
        f"sample_width={wav_info['sample_width']} "
        f"sample_rate={wav_info['sample_rate']} "
        f"frames={wav_info['frames']} "
        f"duration={wav_info['duration']:.3f}s "
        f"compression={wav_info['compression']} ({wav_info['compression_name']})"
    )

    simulate_chunk_reassembly(reply_wav_bytes, args.chunk_size)
    print("[OK] full local loop passed")


if __name__ == "__main__":
    main()
