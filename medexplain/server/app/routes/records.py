import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    RecordCreateRequest,
    RecordDetailResponse,
    RecordListItem,
    RecordListResponse,
)

router = APIRouter()

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "records.json"


def load_records():
    if not DATA_FILE.exists():
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_records(records):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def _is_blank_text(text: str) -> bool:
    return not text or not text.strip()


def _normalize_summary(summary):
    if summary is None:
        return ["요약이 생성되지 않았습니다."]

    if isinstance(summary, list):
        cleaned = [str(item).strip() for item in summary if str(item).strip()]
        return cleaned if cleaned else ["요약이 생성되지 않았습니다."]

    text = str(summary).strip()
    return [text] if text else ["요약이 생성되지 않았습니다."]


def _normalize_terms_for_save(terms):
    if not terms:
        return []

    normalized = []
    for term in terms:
        if hasattr(term, "model_dump"):
            item = term.model_dump()
        else:
            item = dict(term)

        term_text = str(item.get("term", "")).strip()
        easy_text = str(item.get("description", "") or item.get("easy", "")).strip()

        if not term_text:
            continue

        normalized.append(
            {
                "term": term_text,
                # 기존 저장 구조 유지
                "easy": easy_text,
                # 상세 조회 response_model 호환용
                "description": easy_text,
            }
        )

    return normalized


def _normalize_terms_for_detail(terms):
    if not terms:
        return []

    normalized = []
    for item in terms:
        term_text = str(item.get("term", "")).strip()
        description = str(
            item.get("description")
            or item.get("easy")
            or ""
        ).strip()

        if not term_text:
            continue

        normalized.append(
            {
                "term": term_text,
                "description": description,
            }
        )

    return normalized


@router.post("/records")
def create_record(request: RecordCreateRequest):
    if _is_blank_text(request.clean_text):
        raise HTTPException(
            status_code=400,
            detail="저장할 수 있는 음성 인식 결과가 없습니다."
        )

    records = load_records()

    new_record = {
        "record_id": str(uuid.uuid4()),
        "date": request.date,
        "department": request.department,
        "clean_text": request.clean_text.strip(),
        "summary": _normalize_summary(request.summary),
        "terms": _normalize_terms_for_save(request.terms),
    }

    records.append(new_record)
    save_records(records)

    return {
        "record_id": new_record["record_id"],
        "message": "saved"
    }


@router.get("/records", response_model=RecordListResponse)
def get_records():
    records = load_records()

    result = []
    for record in records:
        summary_list = record.get("summary", [])
        summary_preview = summary_list[0] if summary_list else ""

        result.append(
            RecordListItem(
                record_id=record["record_id"],
                date=record["date"],
                department=record["department"],
                summary_preview=summary_preview,
            )
        )

    return RecordListResponse(records=result)


@router.get("/records/{record_id}", response_model=RecordDetailResponse)
def get_record_detail(record_id: str):
    records = load_records()

    for record in records:
        if record["record_id"] == record_id:
            return RecordDetailResponse(
                record_id=record["record_id"],
                date=record["date"],
                department=record["department"],
                clean_text=record["clean_text"],
                summary=record.get("summary", []),
                terms=_normalize_terms_for_detail(record.get("terms", [])),
            )

    raise HTTPException(status_code=404, detail="Record not found")