from typing import Literal, Dict, Any


def translate_text(
    text: str,
    target_lang: Literal["en", "zh"],
) -> Dict[str, Any]:
    """
    가짜 번역 함수 (M2용 더미)
    - 실제 번역 API 붙이기 전 단계
    - 실패/불확실 상황도 흉내냄
    """

    # 방어: 빈 텍스트
    if not text.strip():
        return {
            "ok": False,
            "translated_text": text,
            "reason": "empty_text",
        }

    # 예시: 특정 키워드가 있으면 '불확실' 처리
    if "??" in text:
        return {
            "ok": False,
            "translated_text": text,
            "reason": "translation_uncertain",
        }

    # 정상 번역인 척
    fake_prefix = "[EN]" if target_lang == "en" else "[ZH]"
    return {
        "ok": True,
        "translated_text": f"{fake_prefix} {text}",
        "reason": None,
    }
