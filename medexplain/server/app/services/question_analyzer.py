from __future__ import annotations

import json
import os
import re
from typing import List


def _build_prompt(text: str) -> str:
    return f"""
너는 환자 진료 준비 보조 시스템이다.

아래는 환자가 진료 전에 적은 궁금한 점들이다.
각 질문을 분류하고 정리하라.

분류 기준:
- general_info: 의학적 기본 지식으로 간단히 설명 가능한 것 (예: "CRP가 뭔가요?")
- ask_doctor: 반드시 담당 의사에게 직접 물어봐야 하는 것 (예: "제 CRP가 왜 높나요?")
- caution: 즉시 주의가 필요하거나 응급 가능성이 있는 것 (예: "갑자기 가슴이 너무 아파요")

반드시 지킬 규칙:
1. 진단하지 말 것
2. 치료를 추천하지 말 것
3. general_info의 answer는 1-2문장 이내로 짧고 쉽게
4. ask_doctor는 의사에게 물어볼 질문 형태로 정리
5. 불확실하면 ask_doctor로 분류
6. 출력은 JSON만 할 것

출력 형식:
{{
  "general_info": [
    {{"question": "...", "answer": "..."}}
  ],
  "ask_doctor": ["...", "..."],
  "caution": ["..."]
}}

환자 질문:
\"\"\"{text}\"\"\"
""".strip()


def _parse_response(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    data = json.loads(raw)

    general_info = []
    for item in data.get("general_info", []):
        if isinstance(item, dict):
            q = str(item.get("question", "")).strip()
            a = str(item.get("answer", "")).strip()
            if q and a:
                general_info.append({"question": q, "answer": a})

    ask_doctor = [str(i).strip() for i in data.get("ask_doctor", []) if str(i).strip()]
    caution = [str(i).strip() for i in data.get("caution", []) if str(i).strip()]

    return {"general_info": general_info, "ask_doctor": ask_doctor, "caution": caution}


def _fallback(text: str) -> dict:
    """LLM 실패 시 전체를 ask_doctor로 분류"""
    lines = []
    for part in re.split(r"[?\n]", text):
        part = part.strip()
        if part:
            lines.append(part + "?" if not part.endswith("?") else part)
    return {
        "general_info": [],
        "ask_doctor": lines if lines else [text.strip()],
        "caution": [],
    }


def analyze_questions(text: str) -> dict:
    text = text.strip()
    if not text:
        return {"general_info": [], "ask_doctor": [], "caution": []}

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = _build_prompt(text)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            raw = (response.text or "").strip()
            return _parse_response(raw)
        except Exception as e:
            print(f"[questions] llm failed, fallback: {e}")

    return _fallback(text)
