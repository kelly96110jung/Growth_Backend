from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional
import time
import uuid


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
    목표: 세션이 절대 터지지 않게, 상태/타임스탬프/seq를 안정적으로 관리.
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

