from fastapi import WebSocket, WebSocketDisconnect
import traceback

from session.fake_stt_stream import fake_stt_stream
from session.session_manager import SessionManager
from session.events import TranslationEvent, WarningEvent
from translate.translator import translate_text

# 전역 세션 매니저 (main.py가 import해서 cleanup loop를 돌림)
session_manager = SessionManager()


async def ws_stt_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[ws] accepted")

    # 현재 연결에서 다루는 session_id (끊김 처리 시 reconnecting으로 바꾸기 위함)
    current_session_id = None

    try:
        while True:
            # ----------------------------
            # client message 받기 (start / start:<session_id> / stop / stop:<session_id>)
            # ----------------------------
            try:
                msg = await websocket.receive_text()
            except WebSocketDisconnect:
                # 연결이 끊기면 session 유지(ENDED로 만들지 않음)
                if current_session_id is not None:
                    session_manager.mark_reconnecting(current_session_id)
                print("[ws] disconnect while waiting message")
                return

            print("[ws] recv:", msg)

            # ----------------------------
            # start / start:<session_id>
            # ----------------------------
            if msg.startswith("start"):
                parts = msg.split(":", 1)
                session_id = parts[1].strip() if len(parts) == 2 and parts[1].strip() else "test-session"
                current_session_id = session_id

                # 1) 세션 생성/조회
                if session_manager.get_session(session_id) is None:
                    session_manager.create_session(session_id)

                # 2) 상태 streaming으로 전환 (+ touch)
                session_manager.start_streaming(session_id)

                # 3) fake STT + (M2) translation pipeline
                #    M3 정책: 재접속이든 최초든 항상 처음부터 다시 보냄
                try:
                    for event in fake_stt_stream(session_id):
                        # STT 이벤트 전송
                        await websocket.send_text(event.model_dump_json())

                        # final이면 번역(en/zh) + warning(옵션)
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
                                    await websocket.send_text(tr_event.model_dump_json())

                                    # 실패/불확실이면 warning 추가 전송
                                    if not tr.get("ok", False):
                                        reason = tr.get("reason")
                                        code = reason if reason in (
                                            "translation_failed",
                                            "translation_uncertain",
                                        ) else "translation_failed"

                                        warn = WarningEvent(
                                            session_id=event.session_id,
                                            ts=event.ts,
                                            type="warning",
                                            payload={
                                                "code": code,
                                                "message": f"translation issue for {target_lang}",
                                                "target_lang": target_lang,
                                            },
                                        )
                                        await websocket.send_text(warn.model_dump_json())

                    # 스트림이 정상 끝나면 세션 ended 처리
                    session_manager.end_session(session_id)

                except WebSocketDisconnect:
                    # 네트워크 끊김: 세션 유지하고 reconnecting으로
                    session_manager.mark_reconnecting(session_id)
                    print("[ws] disconnect during streaming -> reconnecting")
                    return

                # start 처리 끝났으니 다음 메시지 받으러
                continue

            # ----------------------------
            # stop / stop:<session_id>
            # ----------------------------
            if msg.startswith("stop"):
                parts = msg.split(":", 1)
                session_id = parts[1].strip() if len(parts) == 2 and parts[1].strip() else (current_session_id or "test-session")
                current_session_id = session_id

                session_manager.end_session(session_id)

                # 간단 lifecycle 이벤트(현재 코드 스타일 유지)
                await websocket.send_text(
                    f'{{"type":"lifecycle","session_id":"{session_id}","payload":{{"state":"ended"}}}}'
                )
                continue

            # ----------------------------
            # 기타 메시지는 echo
            # ----------------------------
            await websocket.send_text(msg)

    except WebSocketDisconnect:
        # while loop 전체에서 끊김
        if current_session_id is not None:
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
