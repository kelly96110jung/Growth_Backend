from pydantic import BaseModel
from typing import List


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