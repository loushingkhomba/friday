"""Persistent, offline Kokoro speech worker for Friday."""

import contextlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
SAMPLE_RATE = 24000
SENTENCE_GAP_SECONDS = 0.18
os.environ["HF_HOME"] = str(ROOT / "models" / "tts" / "kokoro_hf_cache")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


def send(payload):
    # ASCII escaping prevents lone surrogates in errors from breaking the JSON pipe.
    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def trim_sentence_edges(audio, np):
    """Remove long quiet padding while preserving short natural word tails."""
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    active = np.flatnonzero(np.abs(audio) > 0.002)
    if active.size == 0:
        return audio
    padding = int(0.05 * SAMPLE_RATE)
    start = max(0, int(active[0]) - padding)
    end = min(len(audio), int(active[-1]) + padding + 1)
    return audio[start:end]


def main():
    try:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline

        started = time.perf_counter()
        with contextlib.redirect_stdout(sys.stderr):
            pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M", device="cpu")
        send({"ready": True, "load_seconds": round(time.perf_counter() - started, 3)})
    except Exception as exc:
        send({"ready": False, "error": f"{type(exc).__name__}: {exc}"})
        return 1

    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request.get("shutdown"):
                break
            started = time.perf_counter()
            chunks = []
            with contextlib.redirect_stdout(sys.stderr):
                for _, _, audio in pipeline(request["text"], voice=request.get("voice", "af_bella"), speed=1.0):
                    if audio is not None:
                        trimmed = trim_sentence_edges(audio, np)
                        if trimmed.size:
                            chunks.append(trimmed)
            if not chunks:
                raise RuntimeError("Kokoro returned no audio")
            gap = np.zeros(int(SENTENCE_GAP_SECONDS * SAMPLE_RATE), dtype=np.float32)
            audio_parts = []
            for index, chunk in enumerate(chunks):
                if index:
                    audio_parts.append(gap)
                audio_parts.append(chunk)
            sf.write(request["output"], np.concatenate(audio_parts), SAMPLE_RATE, subtype="PCM_16")
            send({"ok": True, "seconds": round(time.perf_counter() - started, 3)})
        except Exception as exc:
            send({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
