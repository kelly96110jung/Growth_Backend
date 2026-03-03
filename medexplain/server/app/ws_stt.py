from __future__ import annotations

import asyncio
import base64
import json
import traceback
from typing import Any, Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

from app.stt_google_streaming import GoogleStreamingSttBridge


# ✅ 지금 Flutter가 "녹음 끝나고 WAV 한 번에 전송"이면 True 유지
# 나중에 "쪼개서 실시간 전송"으로 바꾸면 False로 바꾸면 됨
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


def _make_stt_event(session_id: str, text: str, is_final: bool) -> str:
    payload = {
        "type": "stt",
        "session_id": session_id,
        "ts": 0,
        "payload": {"text": text, "is_final": bool(is_final)},
    }
    return json.dumps(payload, ensure_ascii=False)


def _make_warning_event(session_id: str, message: str) -> str:
    payload = {"type": "warning", "session_id": session_id, "ts": 0, "payload": {"message": message}}
    return json.dumps(payload, ensure_ascii=False)


def _make_error_event(session_id: str, message: str) -> str:
    payload = {"type": "error", "session_id": session_id, "ts": 0, "payload": {"message": message}}
    return json.dumps(payload, ensure_ascii=False)


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
        except Exception as e:
            print("[ws] push_stt failed:", e)

    def on_result(text: str, is_final: bool) -> None:
        print(f"[gcp] result final={is_final} text={text!r}")
        asyncio.create_task(push_stt(text, is_final))

    def on_error(message: str) -> None:
        print(f"[gcp] ERROR {message}")

        async def _push_err():
            try:
                await _send_text(websocket, _make_error_event(current_session_id, message))
            except Exception as e:
                print("[ws] push_error failed:", e)

        asyncio.create_task(_push_err())

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

                bridge = GoogleStreamingSttBridge(loop=loop, on_result=on_result, on_error=on_error)

                try:
                    bridge.set_audio_format(encoding=encoding, sample_rate_hz=sample_rate, channels=channels)
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
                        _make_warning_event(current_session_id, "channels!=1 (stereo). v0는 mono(1) 권장"),
                    )
                continue

            if mtype == "audio":
                if not bridge:
                    await _send_text(websocket, _make_warning_event(current_session_id, "got audio before session.start"))
                    continue

                b64 = msg.get("audioB64") or msg.get("audio_b64")
                if not b64:
                    await _send_text(
                        websocket,
                        _make_warning_event(current_session_id, f"audio missing audioB64 keys={list(msg.keys())}"),
                    )
                    continue

                try:
                    audio_bytes = _b64_to_bytes(b64)
                    bytes_field = msg.get("bytes")

                    # 로그: 서버가 실제로 받았는지 확인용
                    decoded_len = len(audio_bytes)
                    if bytes_field:
                        print(
                            f"[ws] audio recv sid={current_session_id} bytes_field={bytes_field} decoded={decoded_len}"
                        )
                    else:
                        print(f"[ws] audio recv sid={current_session_id} decoded={decoded_len}")

                    if RECORD_THEN_SEND:
                        # ✅ 한 방에 받은 WAV/PCM을 단발 recognize로 처리
                        print("[ws] recognize_once (record-then-send mode)")
                        await asyncio.to_thread(bridge.recognize_once, audio_bytes)
                        print("[ws] recognize_once done")
                        continue

                    # ✅ streaming 모드 (나중에 Flutter가 chunk로 보내면 사용)
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
                await _send_text(websocket, json.dumps({"type": "session.ended", "session_id": current_session_id}))
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