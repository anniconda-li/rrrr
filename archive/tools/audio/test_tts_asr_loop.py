from __future__ import annotations

import argparse
import difflib
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
        compression = f"{wf.getcomptype()} ({wf.getcompname()})"
        duration = frames / sample_rate if sample_rate else 0.0

    return {
        "channels": channels,
        "sample_width": sample_width,
        "sample_rate": sample_rate,
        "frames": frames,
        "duration": duration,
        "compression": compression,
    }


def print_diff(expected: str, actual: str) -> None:
    if expected == actual:
        return
    print("diff:")
    for line in difflib.ndiff([expected], [actual]):
        print(line)


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
    parser = argparse.ArgumentParser(description="Run local TTS -> WAV -> ASR loop test")
    parser.add_argument("--text", required=True, help="input text to synthesize and recognize")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(PROJECT_ROOT)), help="output directory")
    args = parser.parse_args()

    text = args.text
    output_dir = prepare_output_dir(args.out_dir)

    input_path = output_dir / "question.txt"
    wav_path = output_dir / "question.wav"
    recognized_path = output_dir / "asr_text.txt"

    input_path.write_text(text, encoding="utf-8")
    wav_bytes = synthesize_wav_16k(text)
    wav_path.write_bytes(wav_bytes)

    wav_info = inspect_wav(wav_path)
    print("WAV:")
    print(f"  channels: {wav_info['channels']}")
    print(f"  sample_width: {wav_info['sample_width']}")
    print(f"  sample_rate: {wav_info['sample_rate']}")
    print(f"  frames: {wav_info['frames']}")
    print(f"  duration: {wav_info['duration']:.3f}s")
    print(f"  compression: {wav_info['compression']}")

    recognized = transcribe_wav(wav_path)
    recognized_path.write_text(recognized, encoding="utf-8")

    is_exact_match = text == recognized
    print(f"original: {text}")
    print(f"recognized: {recognized}")
    print(f"exact_match: {is_exact_match}")
    print_diff(text, recognized)
    print(f"artifacts: {output_dir}")


if __name__ == "__main__":
    main()
