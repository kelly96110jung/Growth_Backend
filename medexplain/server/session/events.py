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
    (M2에서 translation 실패/불확실 시 사용)
    payload 예시:
      {
        "code": "translation_failed" | "translation_uncertain",
        "message": "...",
        "target_lang": "en" | "zh" | None
      }
    """
    type: Literal["warning"] = "warning"
    payload: Dict[str, Any]


class SttEvent(BaseEvent):
    """
    STT 결과 이벤트 (interim / final)
    payload 예시:
      {
        "text": "...",
        "is_final": true/false
      }
    """
    type: Literal["stt"] = "stt"
    payload: Dict[str, Any]


class TranslationEvent(BaseEvent):
    """
    번역 결과 이벤트 (ko -> en / zh)
    ✅ M2 완료 기준을 위해 "항상 JSON으로" 번역 결과를 보내기 위한 이벤트

    payload 예시(성공):
      {
        "source_lang": "ko",
        "target_lang": "en",
        "stt_text": "원문",
        "translated_text": "번역문",
        "ok": true
      }

    payload 예시(실패/불확실):
      {
        "source_lang": "ko",
        "target_lang": "zh",
        "stt_text": "원문",
        "translated_text": "원문",   # 원문 유지
        "ok": false,
        "reason": "translation_failed" | "translation_uncertain"
      }
    """
    type: Literal["translation"] = "translation"
    payload: Dict[str, Any]
