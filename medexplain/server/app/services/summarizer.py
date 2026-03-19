import json
import os
import re
from typing import List

from google import genai


def _normalize_text(text: str) -> str:
    text = text.strip()

    if not text:
        return ""

    # 줄바꿈/공백 정리
    text = re.sub(r"\s+", " ", text)

    # 너무 긴 입력 방지: 데모용으로 일단 적당히 제한
    # 필요하면 더 늘려도 됨
    if len(text) > 6000:
        text = text[:6000]

    return text


def summarize_text_rule_based(text: str) -> List[str]:
    text = _normalize_text(text)

    if not text:
        return []

    sentences = []
    for part in text.replace("!", ".").replace("?", ".").split("."):
        part = part.strip()
        if part:
            sentences.append(part)

    if not sentences:
        return [text]

    result = []
    for sentence in sentences[:3]:
        if sentence.endswith("."):
            result.append(sentence)
        else:
            result.append(sentence + ".")

    return result


def _build_prompt(text: str) -> str:
    return f"""
너는 환자 이해 보조 시스템의 요약기다.

아래는 병원 진료 설명을 STT로 전사한 한국어 텍스트다.
반드시 원문에 있는 사실만 바탕으로, 환자가 빠르게 이해할 수 있도록 핵심만 짧게 요약하라.

반드시 지킬 규칙:
1. 진단을 추론하지 말 것
2. 치료를 추천하지 말 것
3. 의사의 의도를 해석하지 말 것
4. 원문에 없는 내용을 추가하지 말 것
5. 불확실하거나 애매한 내용은 제외할 것
6. 최대 3개의 bullet만 만들 것
7. 각 bullet은 짧고 쉬운 한국어 문장으로 작성할 것
8. 출력은 JSON만 할 것
9. JSON 형식은 반드시 아래와 같아야 함

{{
  "summary": [
    "문장1",
    "문장2",
    "문장3"
  ]
}}

입력 텍스트:
\"\"\"{text}\"\"\"
""".strip()


def _parse_llm_summary(raw_text: str) -> List[str]:
    raw_text = raw_text.strip()

    if not raw_text:
        return []

    # 혹시 ```json ... ``` 형태로 올 수도 있어서 제거
    raw_text = re.sub(r"^```json\s*", "", raw_text)
    raw_text = re.sub(r"^```\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text)

    data = json.loads(raw_text)

    summary = data.get("summary", [])
    if not isinstance(summary, list):
        return []

    cleaned = []
    for item in summary:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if not s:
            continue
        cleaned.append(s)

    # 최대 3개만
    return cleaned[:3]


def summarize_text_llm(text: str) -> List[str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key)

    prompt = _build_prompt(text)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    raw_text = (response.text or "").strip()
    result = _parse_llm_summary(raw_text)

    if not result:
        raise RuntimeError("LLM returned empty or invalid summary")

    return result


def summarize_text(text: str) -> List[str]:
    text = _normalize_text(text)

    if not text:
        return []

    try:
        result = summarize_text_llm(text)
        if result:
            return result
    except Exception as e:
        print(f"[summary] llm failed, fallback to rule-based: {e}")

    return summarize_text_rule_based(text)