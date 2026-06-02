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
from services.tts_service import synthesize_wav_16k


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "tmp" / "latest"


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
    parser = argparse.ArgumentParser(description="Run standalone TTS WAV generation test")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(PROJECT_ROOT)), help="output directory")
    args = parser.parse_args()

    output_dir = prepare_output_dir(args.out_dir)
    input_path = output_dir / "question.txt"
    output_path = output_dir / "reply.wav"
    input_path.write_text("你好，我是景区导游助手。", encoding="utf-8")
    wav_bytes = synthesize_wav_16k("你好，我是景区导游助手。")
    output_path.write_bytes(wav_bytes)

    with wave.open(str(output_path), "rb") as wf:
        channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        sample_width = wf.getsampwidth()

    assert channels == 1, channels
    assert sample_rate == 16000, sample_rate
    assert sample_width == 2, sample_width
    print(f"ok: {output_path} channels={channels} sample_rate={sample_rate} sample_width={sample_width}")


if __name__ == "__main__":
    main()
