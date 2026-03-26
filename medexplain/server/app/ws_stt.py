from __future__ import annotations

import asyncio
import base64
import json
import traceback
from typing import Any, Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

from app.stt_google_streaming import GoogleStreamingSttBridge

RECORD_THEN_SEND = True


async def _send_text(ws: WebSocket, text: str) -> None:
    await ws.send_text(text)


def _safe_json_loads(s: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(s)
    except Exception:
        return None


def _b64_to_bytes(b64: str) -> bytes:
    b64 = b64.strip().replace("\n", "").replace("\r", "")
    return base64.b64decode(b64)


def _translate_text_mock(text: str, target_lang: str) -> str:
    text = (text or "").strip()

    if not text:
        return text

    if target_lang == "en":
        return f"[EN] {text}"
    if target_lang == "zh":
        return f"[ZH] {text}"

    return text


def _make_stt_event(session_id: str, text: str, is_final: bool) -> str:
    payload = {
        "type": "stt",
        "session_id": session_id,
        "ts": 0,
        "text": text,
        "isFinal": bool(is_final),
    }
    return json.dumps(payload, ensure_ascii=False)


def _make_translation_event(
    session_id: str,
    source_lang: str,
    target_lang: str,
    stt_text: str,
    translated_text: str,
    ok: bool,
    reason: Optional[str] = None,
) -> str:
    payload = {
        "type": "translate",
        "session_id": session_id,
        "ts": 0,
        "target": target_lang,
        "text": translated_text,
        "needsConfirm": not ok,
        "sourceLang": source_lang,
        "sttText": stt_text,
    }

    if reason is not None:
        payload["reason"] = reason

    return json.dumps(payload, ensure_ascii=False)


def _make_warning_event(session_id: str, message: str) -> str:
    payload = {
        "type": "warning",
        "session_id": session_id,
        "ts": 0,
        "payload": {"message": message},
    }
    return json.dumps(payload, ensure_ascii=False)


def _make_error_event(session_id: str, message: str) -> str:
    payload = {
        "type": "error",
        "session_id": session_id,
        "ts": 0,
        "payload": {"message": message},
    }
    return json.dumps(payload, ensure_ascii=False)


def _is_empty_stt_text(text: Optional[str]) -> bool:
    return not text or not text.strip()


async def ws_stt_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    print("[ws] accepted /ws/stt")

    loop = asyncio.get_running_loop()
    current_session_id: str = "test-session"

    bridge: Optional[GoogleStreamingSttBridge] = None
    started_streaming = False

    async def push_stt(text: str, is_final: bool) -> None:
        try:
            msg = _make_stt_event(current_session_id, text, is_final)
            await _send_text(websocket, msg)
            print(f"[ws] pushed stt final={is_final} text={text!r}")
        except Exception as e:
            print("[ws] push_stt failed:", e)

    async def push_translation(stt_text: str, target_lang: str) -> None:
        try:
            translated_text = _translate_text_mock(stt_text, target_lang)

            msg = _make_translation_event(
                session_id=current_session_id,
                source_lang="ko",
                target_lang=target_lang,
                stt_text=stt_text,
                translated_text=translated_text,
                ok=True,
            )
            await _send_text(websocket, msg)
            print(f"[ws] pushed translation target={target_lang} text={translated_text!r}")

        except Exception as e:
            print("[ws] push_translation failed:", e)

            try:
                fail_msg = _make_translation_event(
                    session_id=current_session_id,
                    source_lang="ko",
                    target_lang=target_lang,
                    stt_text=stt_text,
                    translated_text=stt_text,
                    ok=False,
                    reason="translation_failed",
                )
                await _send_text(websocket, fail_msg)
            except Exception as inner_e:
                print("[ws] push_translation fallback failed:", inner_e)

    async def push_warning(message: str) -> None:
        try:
            msg = _make_warning_event(current_session_id, message)
            await _send_text(websocket, msg)
            print(f"[ws] pushed warning message={message!r}")
        except Exception as e:
            print("[ws] push_warning failed:", e)

    def submit_coro(coro, label: str) -> None:
        try:
            asyncio.run_coroutine_threadsafe(coro, loop)
        except Exception as e:
            print(f"[ws] submit {label} failed:", e)

    def on_result(text: str, is_final: bool) -> None:
        print(f"[gcp] result final={is_final} text={text!r}")

        # 결과 전송은 submit만 하고 기다리지 않음
        submit_coro(push_stt(text, is_final), "push_stt")

        # final인데 텍스트가 비어 있으면 warning 전송
        if is_final and _is_empty_stt_text(text):
            submit_coro(
                push_warning("음성이 인식되지 않았습니다. 다시 녹음해주세요."),
                "push_warning",
            )
            return

        # final이고 텍스트가 있으면 번역 진행
        if is_final:
            submit_coro(push_translation(text, "en"), "push_translation_en")
            submit_coro(push_translation(text, "zh"), "push_translation_zh")

    def on_error(message: str) -> None:
        print(f"[gcp] ERROR {message}")

        async def _push_err() -> None:
            try:
                await _send_text(websocket, _make_error_event(current_session_id, message))
            except Exception as e:
                print("[ws] push_error failed:", e)

        submit_coro(_push_err(), "push_error")

    try:
        while True:
            raw = await websocket.receive_text()
            msg = _safe_json_loads(raw)
            if not msg:
                print("[ws] non-json msg, ignoring")
                continue

            mtype = msg.get("type")
            if not mtype:
                print("[ws] missing type, ignoring:", msg.keys())
                continue

            if mtype == "session.start":
                current_session_id = msg.get("sessionId") or msg.get("session_id") or "test-session"
                audio = msg.get("audio") or {}

                encoding = audio.get("encoding", "LINEAR16")
                sample_rate = int(audio.get("sampleRateHz", 16000))
                channels = int(audio.get("channels", 1))

                print(f"[ws] session.start sid={current_session_id} fmt={encoding}/{sample_rate}/{channels}")

                bridge = GoogleStreamingSttBridge(
                    loop=loop,
                    on_result=on_result,
                    on_error=on_error,
                )

                try:
                    bridge.set_audio_format(
                        encoding=encoding,
                        sample_rate_hz=sample_rate,
                        channels=channels,
                    )
                except Exception as e:
                    err = f"Audio format invalid: {type(e).__name__}: {e}"
                    print("[ws] " + err)
                    await _send_text(websocket, _make_error_event(current_session_id, err))
                    bridge = None
                    started_streaming = False
                    continue

                started_streaming = False
                print("[ws] bridge prepared")

                if channels != 1:
                    await _send_text(
                        websocket,
                        _make_warning_event(
                            current_session_id,
                            "channels!=1 (stereo). v0는 mono(1) 권장",
                        ),
                    )
                continue

            if mtype == "audio":
                if not bridge:
                    await _send_text(
                        websocket,
                        _make_warning_event(current_session_id, "got audio before session.start"),
                    )
                    continue

                b64 = msg.get("audioB64") or msg.get("audio_b64")
                if not b64:
                    await _send_text(
                        websocket,
                        _make_warning_event(
                            current_session_id,
                            f"audio missing audioB64 keys={list(msg.keys())}",
                        ),
                    )
                    continue

                try:
                    audio_bytes = _b64_to_bytes(b64)
                    bytes_field = msg.get("bytes")

                    decoded_len = len(audio_bytes)
                    if bytes_field:
                        print(
                            f"[ws] audio recv sid={current_session_id} "
                            f"bytes_field={bytes_field} decoded={decoded_len}"
                        )
                    else:
                        print(f"[ws] audio recv sid={current_session_id} decoded={decoded_len}")

                    if RECORD_THEN_SEND:
                        print("[ws] recognize_once (record-then-send mode)")
                        await asyncio.to_thread(bridge.recognize_once, audio_bytes)
                        print("[ws] recognize_once done")
                        continue

                    if not started_streaming:
                        bridge.start_streaming_thread()
                        started_streaming = True
                        print("[ws] streaming thread started")

                    dec_len, was_wav = bridge.enqueue_audio_bytes(audio_bytes)
                    print(f"[ws] audio enqueue sid={current_session_id} decoded={dec_len} was_wav={was_wav}")

                except Exception as e:
                    err = f"audio decode/enqueue failed: {type(e).__name__}: {e}"
                    print("[ws] " + err)
                    await _send_text(websocket, _make_error_event(current_session_id, err))
                continue

            if mtype == "session.end":
                print(f"[ws] session.end sid={current_session_id}")
                if bridge:
                    bridge.stop()
                await _send_text(
                    websocket,
                    json.dumps(
                        {
                            "type": "session.ended",
                            "session_id": current_session_id,
                        },
                        ensure_ascii=False,
                    ),
                )
                continue

            print("[ws] unknown type:", mtype)

    except WebSocketDisconnect:
        print("[ws] disconnect")
    except Exception as e:
        print("[ws] fatal error:", type(e).__name__, e)
        traceback.print_exc()
    finally:
        try:
            if bridge:
                bridge.stop()
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass