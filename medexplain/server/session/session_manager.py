from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List
import time


class SessionState(str, Enum):
    CREATED = "created"
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"
    ENDED = "ended"


@dataclass
class Session:
    session_id: str
    state: SessionState = SessionState.CREATED
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    last_activity_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    seq: int = 0  # event sequence number


class SessionManager:
    """
    In-memory session manager (no DB).
    Goals: do not drop session unexpectedly; manage state/timestamps/seq consistently.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}

    def create_session(self, session_id: str) -> Session:
        existing = self.get_session(session_id)
        if existing is not None:
            return existing

        session = Session(session_id=session_id)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def touch(self, session_id: str) -> None:
        s = self._sessions.get(session_id)
        if not s:
            return
        s.last_activity_ms = int(time.time() * 1000)

    def start_streaming(self, session_id: str) -> Optional[Session]:
        s = self._sessions.get(session_id)
        if not s:
            return None
        s.state = SessionState.STREAMING
        self.touch(session_id)
        return s

    def mark_reconnecting(self, session_id: str) -> Optional[Session]:
        s = self._sessions.get(session_id)
        if not s:
            return None
        s.state = SessionState.RECONNECTING
        self.touch(session_id)
        return s

    def end_session(self, session_id: str) -> Optional[Session]:
        s = self._sessions.get(session_id)
        if not s:
            return None
        s.state = SessionState.ENDED
        self.touch(session_id)
        return s

    def next_seq(self, session_id: str) -> int:
        """
        Increment and return sequence number for the session.
        """
        s = self._sessions.get(session_id)
        if not s:
            return 0
        s.seq += 1
        self.touch(session_id)
        return s.seq

    def expire_inactive_sessions(self, *, ttl_minutes: int = 20) -> List[str]:
        """
        last_activity_ms 기준 ttl_minutes 이상 비활성인 세션을 ENDED로 전환하고,
        종료된 session_id 목록을 반환한다.
        """
        now_ms = int(time.time() * 1000)
        ttl_ms = ttl_minutes * 60 * 1000

        expired: List[str] = []

        for session_id, s in list(self._sessions.items()):
            if s.state == SessionState.ENDED:
                continue

            if now_ms - s.last_activity_ms > ttl_ms:
                self.end_session(session_id)
                expired.append(session_id)

        return expired
