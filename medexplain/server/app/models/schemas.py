from pydantic import BaseModel
from typing import List, Optional


class TextRequest(BaseModel):
    text: str


class TermItem(BaseModel):
    term: str
    description: str


class SummaryResponse(BaseModel):
    summary: List[str]


class ExplainResponse(BaseModel):
    terms: List[TermItem]


class RecordCreateRequest(BaseModel):
    date: str
    department: str
    clean_text: str
    summary: List[str]
    terms: List[TermItem]


class RecordListItem(BaseModel):
    record_id: str
    date: str
    department: str
    summary_preview: str


class RecordListResponse(BaseModel):
    records: List[RecordListItem]


class RecordDetailResponse(BaseModel):
    record_id: str
    date: str
    department: str
    clean_text: str
    summary: List[str]
    terms: List[TermItem]


# ── 사전 질문 정리 ──────────────────────────────────────

class QuestionAnalyzeRequest(BaseModel):
    text: str


class GeneralInfoItem(BaseModel):
    question: str
    answer: str


class QuestionAnalyzeResponse(BaseModel):
    general_info: List[GeneralInfoItem]
    ask_doctor: List[str]
    caution: List[str]


class QuestionSaveRequest(BaseModel):
    raw_text: str
    general_info: List[GeneralInfoItem]
    ask_doctor: List[str]
    caution: List[str]
    record_id: Optional[str] = None  # 진료 기록과 연결 (B안)


class QuestionListItem(BaseModel):
    question_id: str
    created_at: str
    raw_text: str
    ask_doctor_count: int
    record_id: Optional[str]


class QuestionListResponse(BaseModel):
    questions: List[QuestionListItem]


class QuestionDetailResponse(BaseModel):
    question_id: str
    created_at: str
    raw_text: str
    general_info: List[GeneralInfoItem]
    ask_doctor: List[str]
    caution: List[str]
    record_id: Optional[str]