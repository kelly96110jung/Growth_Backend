from fastapi import WebSocket, WebSocketDisconnect
import traceback

from session.fake_stt_stream import fake_stt_stream
from session.session_manager import SessionManager

# ✅ 전역으로 "인스턴스"를 1개만 유지 (세션 관리의 핵심)
session_manager = SessionManager()


async def ws_stt_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[ws] accepted")

    try:
        while True:
            msg = await websocket.receive_text()
            print("[ws] recv:", msg)

            # -----------------------------
            # start / start:<session_id>
            # -----------------------------
            if msg.startswith("start"):
                # 예: "start" 또는 "start:test-session"
                parts = msg.split(":", 1)
                session_id = parts[1].strip() if len(parts) == 2 and parts[1].strip() else "test-session"

                # 1) 세션 없으면 생성
                if session_manager.get_session(session_id) is None:
                    session_manager.create_session(session_id)

                # 2) 상태를 streaming 으로 변경
                session_manager.start_streaming(session_id)

                # 3) fake STT 이벤트를 WebSocket으로 전송 (동기 generator라서 for 사용)
                for event in fake_stt_stream(session_id):
                    await websocket.send_text(event.model_dump_json())

                # 4) fake 스트림 끝나면 세션 종료
                session_manager.end_session(session_id)

                # start 처리 끝났으니 다음 메시지 받으러 감
                continue

            # -----------------------------
            # stop / stop:<session_id>
            # -----------------------------
            if msg.startswith("stop"):
                parts = msg.split(":", 1)
                session_id = parts[1].strip() if len(parts) == 2 and parts[1].strip() else "test-session"
                session_manager.end_session(session_id)
                await websocket.send_text(f'{{"type":"lifecycle","session_id":"{session_id}","payload":{{"state":"ended"}}}}')
                continue

            # -----------------------------
            # 그 외는 에코
            # -----------------------------
            await websocket.send_text(msg)

    except WebSocketDisconnect:
        print("[ws] disconnect")

    except Exception as e:
        print("[ws] exception:", repr(e))
        traceback.print_exc()
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
