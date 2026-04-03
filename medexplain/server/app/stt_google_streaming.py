from __future__ import annotations

import asyncio
import base64
import io
import os
import queue
import threading
import wave
from dataclasses import dataclass
from typing import Callable, Optional

from google.cloud import speech_v1 as speech

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\82107\Downloads\medexplain-stt-13e7cf056287.json"


@dataclass
class AudioFormat:
    encoding: str  # "LINEAR16"
    sample_rate_hz: int
    channels: int


def _looks_like_wav(raw: bytes) -> bool:
    return len(raw) >= 12 and raw[0:4] == b"RIFF" and raw[8:12] == b"WAVE"


def wav_bytes_to_pcm16(raw_wav: bytes) -> tuple[bytes, AudioFormat]:
    """
    WAV 컨테이너 bytes -> PCM16(raw) bytes + format
    """
    with wave.open(io.BytesIO(raw_wav), "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        pcm = wf.readframes(wf.getnframes())

    if sample_width != 2:
        raise ValueError(f"WAV must be 16-bit PCM. got sample_width={sample_width}")

    return pcm, AudioFormat(encoding="LINEAR16", sample_rate_hz=sample_rate, channels=channels)


def _medical_phrase_hints() -> list[str]:
    return [
        "CRP", "CBC", "CT", "MRI", "PET-CT", "PET CT",
        "biopsy", "endoscopy", "gastroscopy", "gastrectomy",
        "chemotherapy", "radiotherapy", "adenocarcinoma",
        "gastric adenocarcinoma", "carcinoma", "metastasis",
        "lymph node", "lymph nodes", "lymphatic invasion",
        "cancer", "stomach cancer",
        "위선암", "위암", "조직 검사", "내시경", "항암화학요법",
        "방사선 치료", "림프절",
    ]


def _build_recognition_config(sample_rate: int, channels: int) -> speech.RecognitionConfig:
    """
    공통 RecognitionConfig 생성
    - 한국어 기반 유지
    - 영어 의료용어 phrase hints 추가
    """
    speech_context = speech.SpeechContext(
        phrases=_medical_phrase_hints(),
        boost=25.0,
    )

    return speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=sample_rate,
        language_code="ko-KR",
        alternative_language_codes=["en-US"],
        enable_automatic_punctuation=True,
        audio_channel_count=channels,
        model="latest_long",
        use_enhanced=True,
        speech_contexts=[speech_context],
    )


class GoogleStreamingSttBridge:

    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        on_result: Callable[[str, bool], None],
        on_error: Callable[[str], None],
    ):
        self.loop = loop
        self.on_result = on_result
        self.on_error = on_error

        self._fmt: Optional[AudioFormat] = None
        self._q: "queue.Queue[Optional[bytes]]" = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def set_audio_format(self, *, encoding: str, sample_rate_hz: int, channels: int) -> None:
        if encoding != "LINEAR16":
            raise ValueError("Only LINEAR16 is supported in v0")
        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if channels not in (1, 2):
            raise ValueError("channels must be 1 or 2")
        self._fmt = AudioFormat(encoding=encoding, sample_rate_hz=sample_rate_hz, channels=channels)

    def start_streaming_thread(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_streaming, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._q.put(None)

    def enqueue_audio_bytes(self, raw: bytes) -> tuple[int, bool]:
        was_wav = False
        if _looks_like_wav(raw):
            was_wav = True
            pcm, _fmt_from_wav = wav_bytes_to_pcm16(raw)
            raw = pcm

        self._q.put(raw)
        return (len(raw), was_wav)

    def recognize_once(self, raw: bytes) -> None:
        """
        record-then-send 모드용: 한 번에 받은 오디오를 단발 recognize로 처리.
        (Streaming Audio Timeout 회피)
        """
        try:
            if not self._fmt:
                raise RuntimeError("Audio format is not set. Call set_audio_format() first.")

            if _looks_like_wav(raw):
                pcm, fmt_from_wav = wav_bytes_to_pcm16(raw)
                pcm_bytes = pcm
                sample_rate = fmt_from_wav.sample_rate_hz
                channels = fmt_from_wav.channels
            else:
                pcm_bytes = raw
                sample_rate = self._fmt.sample_rate_hz
                channels = self._fmt.channels

            config = _build_recognition_config(sample_rate, channels)
            audio = speech.RecognitionAudio(content=pcm_bytes)

            client = speech.SpeechClient()
            resp = client.recognize(config=config, audio=audio)

            if not resp.results:
                self._emit_result("", True)
                return

            texts: list[str] = []
            for r in resp.results:
                if r.alternatives:
                    texts.append(r.alternatives[0].transcript)

            final_text = " ".join(t.strip() for t in texts if t and t.strip())
            self._emit_result(final_text, True)

        except Exception as e:
            self._emit_error(f"{type(e).__name__}: {e}")

    def _emit_result(self, text: str, is_final: bool) -> None:
        self.loop.call_soon_threadsafe(self.on_result, text, is_final)

    def _emit_error(self, msg: str) -> None:
        self.loop.call_soon_threadsafe(self.on_error, msg)

    def _request_generator(self):
        first = self._q.get()
        if first is None:
            return

        if not self._fmt:
            raise RuntimeError("Audio format is not set. Call set_audio_format() after session.start.")

        config = _build_recognition_config(
            sample_rate=self._fmt.sample_rate_hz,
            channels=self._fmt.channels,
        )

        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
            single_utterance=False,
        )

        yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)
        yield speech.StreamingRecognizeRequest(audio_content=first)

        while not self._stop.is_set():
            chunk = self._q.get()
            if chunk is None:
                break
            yield speech.StreamingRecognizeRequest(audio_content=chunk)

    def _run_streaming(self) -> None:
        try:
            client = speech.SpeechClient()

            responses = client.streaming_recognize(requests=self._request_generator())

            for resp in responses:
                for result in resp.results:
                    if not result.alternatives:
                        continue
                    text = result.alternatives[0].transcript
                    self._emit_result(text, result.is_final)

        except Exception as e:
            self._emit_error(f"{type(e).__name__}: {e}")