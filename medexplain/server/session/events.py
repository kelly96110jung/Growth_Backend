from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal, Dict, Any


class BaseEvent(BaseModel):
    """
    모든 이벤트가 공통으로 갖는 최소 필드.
    서버는 어떤 상황에서도 이 구조를 깨면 안 된다.
    """
    session_id: str
    ts: int = Field(..., description="epoch milliseconds")
    type: Literal["stt", "translation", "warning", "lifecycle"]
    payload: Dict[str, Any]


class LifecycleEvent(BaseEvent):
    """
    세션 상태 변경 이벤트
    created / streaming / reconnecting / ended
    """
    type: Literal["lifecycle"] = "lifecycle"
    payload: Dict[str, Any]


class WarningEvent(BaseEvent):
    """
    실패 / 불확실 상황 전달용 이벤트
    """
    type: Literal["warning"] = "warning"
    payload: Dict[str, Any]


class SttEvent(BaseEvent):
    """
    STT 결과 이벤트 (interim / final)
    """
    type: Literal["stt"] = "stt"
    payload: Dict[str, Any]


class TranslationEvent(BaseEvent):
    """
    번역 결과 이벤트 (ko -> en / zh)
    """
    type: Literal["translation"] = "translation"
    payload: Dict[str, Any]
