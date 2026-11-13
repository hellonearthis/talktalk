"""TTS engine adapters for Kokoro ONNX and BabelVox (Qwen3-TTS OpenVINO)."""

from __future__ import annotations

import os
import threading
import urllib.request
from collections.abc import Iterator
from typing import Protocol

import numpy as np


KOKORO_MODEL_DIR = os.path.join(".", "models", "kokoro")
KOKORO_MODEL_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/kokoro-v1.0.onnx"
)
KOKORO_VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/voices-v1.0.bin"
)


class TTSEngine(Protocol):
    """Protocol implemented by all TTS backends."""

    sample_rate: int

    def stream_chunks(
        self,
        text_chunks: list[str],
        cancel_event: threading.Event,
    ) -> Iterator[np.ndarray]:
        """Yield float32 mono waveform chunks until done or canceled."""
        ...


def _ensure_kokoro_files(model_dir: str = KOKORO_MODEL_DIR) -> tuple[str, str]:
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "kokoro-v1.0.onnx")
    voices_path = os.path.join(model_dir, "voices-v1.0.bin")
    for url, path in ((KOKORO_MODEL_URL, model_path), (KOKORO_VOICES_URL, voices_path)):
        if not os.path.isfile(path):
            print(f"Downloading {os.path.basename(path)}...")
            partial_path = f"{path}.part"
            urllib.request.urlretrieve(url, partial_path)
            os.replace(partial_path, path)
    return model_path, voices_path


class KokoroTTSEngine:
    """Fast CPU Kokoro ONNX backend."""

    def __init__(
        self,
        voice: str = "af_heart",
        speed: float = 1.3,
        lang: str = "en-us",
        model_dir: str = KOKORO_MODEL_DIR,
    ) -> None:
        from kokoro_onnx import Kokoro

        model_path, voices_path = _ensure_kokoro_files(model_dir)
        self._kokoro = Kokoro(model_path, voices_path)
        self._voice = voice
        self.speed = speed  # public so a UI (tray menu) can change it between chunks
        self._lang = lang
        self.sample_rate = 24000
        # Warm up ONNX runtime so first hotkey press is fast
        self._kokoro.create("Ready.", voice=self._voice, speed=self.speed, lang=self._lang)

    def stream_chunks(
        self,
        text_chunks: list[str],
        cancel_event: threading.Event,
    ) -> Iterator[np.ndarray]:
        for segment in text_chunks:
            if cancel_event.is_set():
                return
            samples, sr = self._kokoro.create(
                segment,
                voice=self._voice,
                speed=self.speed,
                lang=self._lang,
            )
            self.sample_rate = sr
            if cancel_event.is_set():
                return
            yield np.asarray(samples, dtype=np.float32)


class BabelVoxTTSEngine:
    """Qwen3-TTS 0.6B OpenVINO backend via BabelVox."""

    def __init__(
        self,
        device: str = "CPU",
        language: str = "English",
        chunk_frames: int = 6,
        ref_audio: str | None = None,
        ref_text: str | None = None,
    ) -> None:
        from babelvox import BabelVox

        kwargs: dict[str, object] = {
            "device": device,
            "precision": "int8",
            "use_cp_kv_cache": True,
        }
        if device == "NPU":
            kwargs["talker_buckets"] = [64, 128, 256]
            kwargs["cache_dir"] = "./ov_cache"

        self._engine = BabelVox(**kwargs)
        self._language = language
        self._chunk_frames = chunk_frames
        self._ref_audio = ref_audio
        self._ref_text = ref_text
        self.sample_rate = 24000
        # Warm up
        self._engine.generate("Ready.", language=self._language)

    def stream_chunks(
        self,
        text_chunks: list[str],
        cancel_event: threading.Event,
    ) -> Iterator[np.ndarray]:
        for segment in text_chunks:
            if cancel_event.is_set():
                return
            for chunk, sr in self._engine.generate_stream(
                segment,
                language=self._language,
                ref_audio=self._ref_audio,
                ref_text=self._ref_text,
                chunk_frames=self._chunk_frames,
                cancel_event=cancel_event,
            ):
                self.sample_rate = sr
                if cancel_event.is_set():
                    return
                yield np.asarray(chunk, dtype=np.float32)


def create_tts_engine(
    engine_name: str,
    *,
    voice: str = "af_heart",
    speed: float = 1.3,
    lang: str = "en-us",
    device: str = "CPU",
    language: str = "English",
    ref_audio: str | None = None,
    ref_text: str | None = None,
) -> TTSEngine:
    """Instantiate the requested TTS engine."""
    normalized = engine_name.lower().strip()
    if normalized == "kokoro":
        return KokoroTTSEngine(voice=voice, speed=speed, lang=lang)
    if normalized == "babelvox":
        return BabelVoxTTSEngine(
            device=device,
            language=language,
            ref_audio=ref_audio,
            ref_text=ref_text,
        )
    raise ValueError(f"Unsupported TTS engine: {engine_name!r} (expected 'kokoro' or 'babelvox')")

