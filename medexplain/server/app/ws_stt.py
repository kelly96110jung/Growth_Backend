from __future__ import annotations

import base64
import json
import traceback
from typing import Any, Dict, Optional, Tuple

from fastapi import WebSocket, WebSocketDisconnect

from session.fake_stt_stream import fake_stt_stream
from session.session_manager import SessionManager
from session.events import TranslationEvent, WarningEvent
from translate.translator import translate_text


# 전역 SessionManager (main.py에서 import되어도 1개만 쓰는 형태)
session_manager = SessionManager()


def _safe_json_loads(s: str) -> Optional[dict]:
    s = (s or "").strip()
    if not s.startswith("{"):
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def _parse_start_text(msg: str) -> Tuple[str, str]:
    """
    "start" or "start:<session_id>" 형태 지원
    returns: (cmd, session_id)
    """
    parts = msg.split(":", 1)
    cmd = parts[0].strip()
    sid = parts[1].strip() if len(parts) == 2 and parts[1].strip() else "test-session"
    return cmd, sid


def _parse_stop_text(msg: str, fallback_session_id: str) -> Tuple[str, str]:
    """
    "stop" or "stop:<session_id>" 형태 지원
    returns: (cmd, session_id)
    """
    parts = msg.split(":", 1)
    cmd = parts[0].strip()
    sid = parts[1].strip() if len(parts) == 2 and parts[1].strip() else (fallback_session_id or "test-session")
    return cmd, sid


async def _send_text(websocket: WebSocket, payload: str) -> None:
    await websocket.send_text(payload)


async def _send_lifecycle(websocket: WebSocket, session_id: str, state: str) -> None:
    # 기존 코드처럼 간단 lifecycle JSON 문자열로 전송(테스트/호환용)
    await _send_text(
        websocket,
        json.dumps(
            {
                "type": "lifecycle",
                "session_id": session_id,
                "payload": {"state": state},
            },
            ensure_ascii=False,
        ),
    )


async def _send_warning(
    websocket: WebSocket,
    session_id: str,
    code: str,
    message: str,
    ts: Optional[int] = None,
    extra: Optional[dict] = None,
) -> None:
    payload = {"code": code, "message": message}
    if extra:
        payload.update(extra)

    # ts가 없으면 SessionManager 쪽 시간/seq를 쓰는 이벤트와 섞일 수 있어서,
    # 여기서는 None이면 0으로 둠 (클라이언트에서 optional 처리 권장)
    warn = WarningEvent(
        session_id=session_id,
        ts=ts or 0,
        type="warning",
        payload=payload,
    )
    await _send_text(websocket, warn.model_dump_json())


def _ensure_session(session_id: str) -> None:
    if session_manager.get_session(session_id) is None:
        session_manager.create_session(session_id)


async def _run_fake_stream_and_translation(websocket: WebSocket, session_id: str) -> None:
    """
    지금까지 해오던 fake_stt_stream -> (final이면) 번역 이벤트 + 실패시 warning
    """
    try:
        for event in fake_stt_stream(session_id):
            # STT 이벤트 먼저 전송
            await _send_text(websocket, event.model_dump_json())

            # final STT면 번역도 같이 전송
            if getattr(event, "type", None) == "stt":
                payload = event.payload or {}
                is_final = bool(payload.get("is_final", False))
                stt_text = payload.get("text", "")

                if is_final:
                    for target_lang in ("en", "zh"):
                        tr = translate_text(stt_text, target_lang)
                        # tr: {"ok": bool, "translated_text": str, "reason": str|None}
                        tr_event = TranslationEvent(
                            session_id=event.session_id,
                            ts=event.ts,
                            type="translation",
                            payload={
                                "source_lang": "ko",
                                "target_lang": target_lang,
                                "stt_text": stt_text,
                                "translated_text": tr.get("translated_text", stt_text),
                                "ok": bool(tr.get("ok", False)),
                                "reason": tr.get("reason"),
                            },
                        )
                        await _send_text(websocket, tr_event.model_dump_json())

                        if not bool(tr.get("ok", False)):
                            reason = tr.get("reason") or "translation_failed"
                            code = reason if reason in ("translation_failed", "translation_uncertain") else "translation_failed"
                            await _send_warning(
                                websocket,
                                session_id=event.session_id,
                                code=code,
                                message=f"translation issue for {target_lang}",
                                ts=event.ts,
                                extra={"target_lang": target_lang},
                            )

        # 스트림 끝나면 종료 처리
        session_manager.end_session(session_id)

    except WebSocketDisconnect:
        # 스트리밍 도중 끊김 -> reconnecting
        session_manager.mark_reconnecting(session_id)
        print("[ws] disconnect during streaming -> reconnecting")
        return


def _validate_session_start_payload(obj: dict) -> Tuple[bool, str]:
    """
    사진의 session.start 형태 검증 (필수값/권장값)
    """
    audio = obj.get("audio") or {}
    enc = audio.get("encoding")
    sr = audio.get("sampleRateHz")
    ch = audio.get("channels")

    if enc != "LINEAR16":
        return False, "audio.encoding must be LINEAR16"
    if sr is None:
        return False, "audio.sampleRateHz is required"
    if ch is None:
        return False, "audio.channels is required"
    if not isinstance(sr, int) or sr <= 0:
        return False, "audio.sampleRateHz must be positive int"
    if ch not in (1, 2):
        return False, "audio.channels must be 1 or 2"
    return True, ""


def _decode_audio_b64(audio_b64: str) -> Tuple[bool, bytes, str]:
    """
    audio 메시지의 base64는 WAV가 아니라 PCM bytes여야 한다는 전제.
    여기서는 "받아서 디코드"만 하고, WAV 헤더 여부는 간단 체크로 경고만 준비.
    """
    try:
        raw = base64.b64decode(audio_b64, validate=True)
    except Exception:
        return False, b"", "audioB64 base64 decode failed"

    # WAV 헤더 흔적("RIFF", "WAVE") 있으면 거의 WAV 컨테이너로 보임 -> 경고용
    if len(raw) >= 12 and raw[0:4] == b"RIFF" and raw[8:12] == b"WAVE":
        return True, raw, "looks like WAV container (RIFF/WAVE). send PCM bytes, not WAV bytes"
    return True, raw, ""


async def ws_stt_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    print("[ws] accepted")

    current_session_id: Optional[str] = None

    try:
        while True:
            # 1) 메시지 수신
            try:
                msg = await websocket.receive_text()
            except WebSocketDisconnect:
                # 대기중 끊김
                if current_session_id:
                    session_manager.mark_reconnecting(current_session_id)
                print("[ws] disconnect while waiting message")
                return

            print("[ws] recv:", msg)

            # 2) JSON 메시지인지 먼저 시도
            obj = _safe_json_loads(msg)

            # ------------------------------------------------------------------
            # A) JSON 프로토콜 (사진에 나온 session.start / audio / session.end)
            # ------------------------------------------------------------------
            if isinstance(obj, dict) and "type" in obj:
                mtype = obj.get("type")

                # session.start
                if mtype == "session.start":
                    session_id = obj.get("sessionId") or obj.get("session_id") or "test-session"
                    current_session_id = session_id

                    ok, reason = _validate_session_start_payload(obj)
                    _ensure_session(session_id)
                    session_manager.start_streaming(session_id)

                    await _send_lifecycle(websocket, session_id, "streaming")

                    if not ok:
                        await _send_warning(
                            websocket,
                            session_id=session_id,
                            code="bad_session_start",
                            message=reason,
                            extra={"expected": {"encoding": "LINEAR16", "sampleRateHz": "int", "channels": "1|2"}},
                        )
                    else:
                        # sampleRateHz/channels 관련 “팀 충돌 포인트”를 서버가 명시적으로 안내
                        audio = obj.get("audio") or {}
                        sr = audio.get("sampleRateHz")
                        ch = audio.get("channels")
                        if ch == 2:
                            await _send_warning(
                                websocket,
                                session_id=session_id,
                                code="stereo_risk",
                                message="channels=2 increases bandwidth/instability risk; prefer mono(1) for M1 stability",
                                extra={"channels": ch, "sampleRateHz": sr},
                            )

                    # 지금 단계에서는 session.start만으로 fake stream을 자동 재생하진 않음
                    # (팀에서 audio를 보내는 흐름과 충돌 줄이기)
                    continue

                # audio (PCM base64 chunk)
                if mtype == "audio":
                    session_id = obj.get("sessionId") or obj.get("session_id") or (current_session_id or "test-session")
                    current_session_id = session_id
                    _ensure_session(session_id)

                    audio_b64 = obj.get("audioB64") or obj.get("audio_b64") or ""
                    seq = obj.get("seq")
                    declared_bytes = obj.get("bytes")

                    if not audio_b64:
                        await _send_warning(
                            websocket,
                            session_id=session_id,
                            code="missing_audio",
                            message="audio.audioB64 is required",
                            extra={"seq": seq},
                        )
                        continue

                    ok, raw, wav_hint = _decode_audio_b64(audio_b64)
                    if not ok:
                        await _send_warning(
                            websocket,
                            session_id=session_id,
                            code="bad_audio_base64",
                            message="audioB64 decode failed",
                            extra={"seq": seq},
                        )
                        continue

                    if isinstance(declared_bytes, int) and declared_bytes != len(raw):
                        await _send_warning(
                            websocket,
                            session_id=session_id,
                            code="bytes_mismatch",
                            message="declared bytes != decoded bytes length",
                            extra={"declared": declared_bytes, "decoded": len(raw), "seq": seq},
                        )

                    if wav_hint:
                        await _send_warning(
                            websocket,
                            session_id=session_id,
                            code="wav_detected",
                            message=wav_hint,
                            extra={"seq": seq},
                        )

                    # 여기서 raw PCM을 Google Streaming STT로 흘려보내는 건 다음 단계(파이프 연결)에서 처리.
                    # 지금은 “서버가 PCM 청크를 받을 수 있다” + “형식 검증/경고”까지만 확정.
                    # 클라이언트가 연결 유지를 확인할 수 있도록 간단 ack 전송
                    await _send_text(
                        websocket,
                        json.dumps(
                            {
                                "type": "audio.ack",
                                "session_id": session_id,
                                "payload": {"seq": seq, "bytes": len(raw)},
                            },
                            ensure_ascii=False,
                        ),
                    )
                    continue

                # session.end
                if mtype == "session.end":
                    session_id = obj.get("sessionId") or obj.get("session_id") or (current_session_id or "test-session")
                    current_session_id = session_id
                    _ensure_session(session_id)

                    session_manager.end_session(session_id)
                    await _send_lifecycle(websocket, session_id, "ended")
                    continue

                # unknown JSON type
                session_id = obj.get("sessionId") or obj.get("session_id") or (current_session_id or "test-session")
                await _send_warning(
                    websocket,
                    session_id=session_id,
                    code="unknown_message_type",
                    message=f"unknown type: {mtype}",
                )
                continue

            # ------------------------------------------------------------------
            # B) 기존 텍스트 프로토콜 (start/stop/echo)
            # ------------------------------------------------------------------
            # start / start:<session_id>
            if msg.startswith("start"):
                _, session_id = _parse_start_text(msg)
                current_session_id = session_id

                _ensure_session(session_id)
                session_manager.start_streaming(session_id)

                # 시작 알림
                await _send_lifecycle(websocket, session_id, "streaming")

                # 기존처럼 start 치면 fake STT + 번역까지 한번에 쏴주는 동작 유지
                await _run_fake_stream_and_translation(websocket, session_id)
                continue

            # stop / stop:<session_id>
            if msg.startswith("stop"):
                _, session_id = _parse_stop_text(msg, current_session_id or "test-session")
                current_session_id = session_id

                session_manager.end_session(session_id)
                await _send_lifecycle(websocket, session_id, "ended")
                continue

            # 기본 echo
            await _send_text(websocket, msg)

    except WebSocketDisconnect:
        if current_session_id:
            session_manager.mark_reconnecting(current_session_id)
        print("[ws] disconnect")
        return

    except Exception as e:
        print("[ws] exception:", repr(e))
        traceback.print_exc()
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
