"""Generate local Kokoro voice samples for Friday voice comparison."""

from __future__ import annotations

import os
import time
from pathlib import Path
import argparse


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "tts" / "kokoro_hf_cache"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import soundfile as sf
import torch
from kokoro import KPipeline


TEXT = "Hello the user. I'm Friday, here and ready to help. What would you like to do today?"
VOICES = ("af_bella", "af_sarah", "af_nova")
OUTPUT_DIR = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Kokoro comparison voice samples.")
    parser.add_argument("--voices", nargs="+", choices=VOICES, default=VOICES)
    args = parser.parse_args()

    print("Loading Kokoro-82M on CPU from local cache.")
    started = time.perf_counter()
    pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M", device="cpu")
    print(f"Model ready in {time.perf_counter() - started:.1f}s.")

    import numpy as np

    for voice in args.voices:
        audio_chunks = []
        generation_started = time.perf_counter()
        for _, _, audio in pipeline(TEXT, voice=voice, speed=1.0):
            if isinstance(audio, torch.Tensor):
                audio = audio.detach().cpu().numpy()
            audio_chunks.append(audio)

        if not audio_chunks:
            raise RuntimeError(f"Kokoro returned no audio chunks for {voice}.")

        audio = np.concatenate(audio_chunks)
        output = OUTPUT_DIR / f"kokoro_{voice}.wav"
        sf.write(str(output), audio, 24_000)
        print(f"{voice}: generated in {time.perf_counter() - generation_started:.1f}s; saved {output}")


if __name__ == "__main__":
    main()
