import time
from typing import Generator
from datetime import datetime

from session.events import SttEvent


def fake_stt_stream(session_id: str) -> Generator[SttEvent, None, None]:
    """
    Google STT 대신 쓰는 가짜 스트리밍.
    interim -> final 흐름을 흉내낸다.
    """
    seq = 0

    # interim 1
    yield SttEvent(
        session_id=session_id,
        ts=int(time.time() * 1000),
        type="stt",
        payload={
            "is_final": False,
            "text": "안녕하세요 지금 상담을",
            "seq": seq,
        },
    )
    seq += 1
    time.sleep(1)

    # interim 2
    yield SttEvent(
        session_id=session_id,
        ts=int(time.time() * 1000),
        type="stt",
        payload={
            "is_final": False,
            "text": "안녕하세요 지금 상담을 시작하고",
            "seq": seq,
        },
    )
    seq += 1
    time.sleep(1)

    # final
    yield SttEvent(
        session_id=session_id,
        ts=int(time.time() * 1000),
        type="stt",
        payload={
            "is_final": True,
            "text": "안녕하세요 지금 상담을 시작하겠습니다??",
            "seq": seq,
        },
    )
