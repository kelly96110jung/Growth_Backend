from __future__ import annotations

import asyncio
import base64
import io
import queue
import threading
import wave
from dataclasses import dataclass
from typing import Callable, Optional

from google.cloud import speech_v1 as speech


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


class GoogleStreamingSttBridge:
    """
    ✅ record-then-send(한 방에 WAV 전송)도 동작하도록 "단발 recognize" 지원
    ✅ streaming 모드(쪼개서 보내기)도 그대로 지원
    """

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
        """
        raw가 WAV면 PCM으로 풀어서 넣고,
        raw가 PCM이면 그대로 넣음.
        return: (decoded_len, was_wav)
        """
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
                # WAV에서 읽은 sample_rate/ch가 session.start와 다르면, WAV 값을 우선 적용해도 됨
                sample_rate = fmt_from_wav.sample_rate_hz
                channels = fmt_from_wav.channels
            else:
                pcm_bytes = raw
                sample_rate = self._fmt.sample_rate_hz
                channels = self._fmt.channels

            # v0: stereo는 인식이 흔들릴 수 있어 mono 권장
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=sample_rate,
                language_code="ko-KR",
                enable_automatic_punctuation=True,
                audio_channel_count=channels,
                model="latest_long",
                use_enhanced=True,
            )
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
        """
        Google streaming_recognize 요구사항:
        - 첫 request에 streaming_config 포함
        - 이후 audio_content들을 "가까운 실시간"으로 흘려보내야 안정적
        """
        first = self._q.get()
        if first is None:
            return

        if not self._fmt:
            raise RuntimeError("Audio format is not set. Call set_audio_format() after session.start.")

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self._fmt.sample_rate_hz,
            language_code="ko-KR",
            enable_automatic_punctuation=True,
            audio_channel_count=self._fmt.channels,
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

            # ✅ 반드시 keyword로 requests= 를 써야 이상한 helper 경로로 안 샘
            responses = client.streaming_recognize(requests=self._request_generator())

            for resp in responses:
                for result in resp.results:
                    if not result.alternatives:
                        continue
                    text = result.alternatives[0].transcript
                    self._emit_result(text, result.is_final)

        except Exception as e:
            self._emit_error(f"{type(e).__name__}: {e}")