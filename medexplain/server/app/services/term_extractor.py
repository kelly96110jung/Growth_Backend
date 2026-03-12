MEDICAL_TERMS = {
    "CRP": "염증 반응이 있을 때 높아질 수 있는 혈액 검사 수치입니다.",
    "내시경": "몸 안쪽 상태를 확인하는 검사입니다.",
    "염증": "몸에 자극이나 감염 등이 있을 때 나타나는 반응입니다.",
    "검사": "몸 상태를 확인하기 위해 시행하는 진료 과정입니다."
}


def extract_terms(text: str) -> list[dict]:
    found_terms = []

    for term, description in MEDICAL_TERMS.items():
        if term in text:
            found_terms.append({
                "term": term,
                "description": description
            })

    return found_terms