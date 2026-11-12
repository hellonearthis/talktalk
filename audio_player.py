"""Interruptible streaming audio player using sounddevice."""

from __future__ import annotations

import queue
import threading

import numpy as np
import sounddevice as sd

from text_chunker import chunk_text_for_tts
from tts_engines import TTSEngine


_SENTINEL = None


class StreamingTTSPlayer:
    """Manages background synthesis and instant-abort audio playback."""

    def __init__(self, engine: TTSEngine) -> None:
        self._engine = engine
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._active_stream: sd.OutputStream | None = None
        self._producer_thread: threading.Thread | None = None
        self._player_thread: threading.Thread | None = None

    @property
    def is_playing(self) -> bool:
        """Return True if synthesis or audio playback is currently active."""
        with self._lock:
            producer_alive = self._producer_thread is not None and self._producer_thread.is_alive()
            player_alive = self._player_thread is not None and self._player_thread.is_alive()
            return producer_alive or player_alive

    def speak(self, text: str) -> None:
        """Stop any current playback and start reading the given text."""
        chunks = chunk_text_for_tts(text)
        if not chunks:
            print("[TTS] Clipboard is empty or contains no readable text.")
            return

        self.stop()

        with self._lock:
            cancel_event = threading.Event()
            self._cancel_event = cancel_event
            audio_queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=4)

            self._producer_thread = threading.Thread(
                target=self._produce_audio,
                args=(chunks, audio_queue, cancel_event),
                daemon=True,
            )
            self._player_thread = threading.Thread(
                target=self._play_audio,
                args=(audio_queue, cancel_event),
                daemon=True,
            )
            self._producer_thread.start()
            self._player_thread.start()

    def stop(self) -> None:
        """Immediately halt synthesis and abort active audio output."""
        with self._lock:
            self._cancel_event.set()
            stream = self._active_stream
            if stream is not None:
                try:
                    stream.abort(ignore_errors=True)
                except Exception:
                    pass
            producer = self._producer_thread
            player = self._player_thread
            self._producer_thread = None
            self._player_thread = None

        if producer is not None and producer.is_alive():
            producer.join(timeout=1.0)
        if player is not None and player.is_alive():
            player.join(timeout=1.0)

    def _produce_audio(
        self,
        chunks: list[str],
        audio_queue: queue.Queue[np.ndarray | None],
        cancel_event: threading.Event,
    ) -> None:
        try:
            for wav_chunk in self._engine.stream_chunks(chunks, cancel_event):
                if cancel_event.is_set():
                    break
                while not cancel_event.is_set():
                    try:
                        audio_queue.put(wav_chunk, timeout=0.05)
                        break
                    except queue.Full:
                        continue
        except Exception as exc:
            if not cancel_event.is_set():
                print(f"[TTS] Synthesis error: {type(exc).__name__}: {exc}")
        finally:
            while True:
                try:
                    audio_queue.put(_SENTINEL, timeout=0.05)
                    break
                except queue.Full:
                    if cancel_event.is_set():
                        # Drain one item so sentinel can fit
                        try:
                            audio_queue.get_nowait()
                        except queue.Empty:
                            pass

    def _play_audio(
        self,
        audio_queue: queue.Queue[np.ndarray | None],
        cancel_event: threading.Event,
    ) -> None:
        stream: sd.OutputStream | None = None
        try:
            while not cancel_event.is_set():
                try:
                    item = audio_queue.get(timeout=0.05)
                except queue.Empty:
                    continue

                if item is _SENTINEL:
                    break

                if stream is None:
                    stream = sd.OutputStream(
                        samplerate=self._engine.sample_rate,
                        channels=1,
                        dtype="float32",
                    )
                    stream.start()
                    with self._lock:
                        self._active_stream = stream

                if item.ndim == 1:
                    item = item.reshape(-1, 1)

                # Write in ~50ms slices so cancellation is responsive
                slice_len = max(1, int(self._engine.sample_rate * 0.05))
                for offset in range(0, len(item), slice_len):
                    if cancel_event.is_set():
                        break
                    stream.write(item[offset : offset + slice_len])
        except Exception as exc:
            if not cancel_event.is_set():
                print(f"[TTS] Playback error: {type(exc).__name__}: {exc}")
        finally:
            if stream is not None:
                try:
                    if cancel_event.is_set():
                        stream.abort(ignore_errors=True)
                    else:
                        stream.stop(ignore_errors=True)
                    stream.close(ignore_errors=True)
                except Exception:
                    pass
                with self._lock:
                    if self._active_stream is stream:
                        self._active_stream = None

