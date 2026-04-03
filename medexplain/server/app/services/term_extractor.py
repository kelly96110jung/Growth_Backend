from __future__ import annotations

import json
import os
import re
from typing import List


# Gemini 실패 시 fallback용 기본 사전
_FALLBACK_TERMS = {
    "CRP": "염증 반응이 있을 때 높아질 수 있는 혈액 검사 수치입니다.",
    "CBC": "혈액 세포 수를 측정하는 기본 혈액 검사입니다.",
    "CT": "여러 각도에서 X선을 촬영해 몸 내부를 단면으로 보는 검사입니다.",
    "MRI": "자기장을 이용해 몸 내부를 상세히 촬영하는 검사입니다.",
    "HbA1c": "최근 2~3개월간의 평균 혈당 수치를 반영하는 검사입니다.",
    "내시경": "몸 안쪽 상태를 카메라로 직접 확인하는 검사입니다.",
    "조직 검사": "몸의 일부 조직을 채취해 현미경으로 분석하는 검사입니다.",
    "림프절": "면역 세포가 모여 있는 작은 기관으로, 감염이나 암 전이 여부를 확인할 때 봅니다.",
    "항암화학요법": "약물로 암세포를 죽이거나 성장을 억제하는 치료입니다.",
    "방사선 치료": "방사선을 이용해 암세포를 파괴하는 치료입니다.",
    "위선암": "위의 점막 세포에서 발생하는 악성 종양입니다.",
    "adenocarcinoma": "샘 조직에서 발생하는 악성 종양으로 위암의 대부분을 차지합니다.",
    "gastric adenocarcinoma": "위에서 발생하는 선암으로, 위암의 가장 흔한 형태입니다.",
    "metastasis": "암세포가 원발 부위에서 다른 부위로 퍼지는 현상입니다.",
    "biopsy": "진단을 위해 조직 일부를 채취하는 시술입니다.",
    "염증": "몸에 자극이나 감염 등이 있을 때 나타나는 반응입니다.",
    "공복 혈당": "8시간 이상 금식 후 측정한 혈당 수치입니다.",
    "디스크": "척추 뼈 사이에서 충격을 흡수하는 구조물로, 탈출 시 신경을 눌러 통증을 유발합니다.",
}


def _build_prompt(text: str) -> str:
    return f"""
너는 의료 용어 추출 시스템이다.

아래 텍스트에서 환자가 이해하기 어려울 수 있는 의료 용어, 검사명, 약물명, 진단명을 추출하라.

규칙:
1. 실제로 텍스트에 등장한 단어만 추출할 것
2. 각 용어에 대해 환자가 이해할 수 있는 짧은 설명(1-2문장)을 제공할 것
3. 너무 일반적인 단어(예: 치료, 병원, 의사)는 제외할 것
4. 최대 6개까지만 추출할 것
5. 출력은 JSON만 할 것

출력 형식:
{{
  "terms": [
    {{"term": "...", "description": "..."}}
  ]
}}

텍스트:
\"\"\"{text}\"\"\"
""".strip()


def _parse_response(raw: str) -> list[dict]:
    raw = raw.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    data = json.loads(raw)
    result = []
    for item in data.get("terms", []):
        term = str(item.get("term", "")).strip()
        description = str(item.get("description", "")).strip()
        if term and description:
            result.append({"term": term, "description": description})
    return result[:6]


def _fallback(text: str) -> list[dict]:
    found = []
    for term, description in _FALLBACK_TERMS.items():
        if term in text:
            found.append({"term": term, "description": description})
    return found


def extract_terms(text: str) -> list[dict]:
    if not text or not text.strip():
        return []

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
            result = _parse_response(raw)
            if result:
                return result
        except Exception as e:
            print(f"[terms] llm failed, fallback: {e}")

    return _fallback(text)
