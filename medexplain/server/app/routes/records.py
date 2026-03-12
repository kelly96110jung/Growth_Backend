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


@router.post("/records")
def create_record(request: RecordCreateRequest):
    records = load_records()

    new_record = {
        "record_id": str(uuid.uuid4()),
        "date": request.date,
        "department": request.department,
        "clean_text": request.clean_text,
        "summary": request.summary,
        "terms": [term.model_dump() for term in request.terms],
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
                summary=record["summary"],
                terms=record["terms"],
            )

    raise HTTPException(status_code=404, detail="Record not found")