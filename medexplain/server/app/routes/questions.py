import json
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    GeneralInfoItem,
    QuestionAnalyzeRequest,
    QuestionAnalyzeResponse,
    QuestionDetailResponse,
    QuestionListItem,
    QuestionListResponse,
    QuestionSaveRequest,
)
from app.services.question_analyzer import analyze_questions

router = APIRouter()

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "questions.json"


def _load():
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.post("/questions/analyze", response_model=QuestionAnalyzeResponse)
def analyze(request: QuestionAnalyzeRequest):
    result = analyze_questions(request.text)
    return QuestionAnalyzeResponse(
        general_info=[GeneralInfoItem(**i) for i in result["general_info"]],
        ask_doctor=result["ask_doctor"],
        caution=result["caution"],
    )


@router.post("/questions")
def save_question(request: QuestionSaveRequest):
    if not request.raw_text.strip():
        raise HTTPException(status_code=400, detail="질문 내용이 없습니다.")

    questions = _load()
    new_item = {
        "question_id": str(uuid.uuid4()),
        "created_at": str(date.today()),
        "raw_text": request.raw_text.strip(),
        "general_info": [i.model_dump() for i in request.general_info],
        "ask_doctor": request.ask_doctor,
        "caution": request.caution,
        "record_id": request.record_id,
    }
    questions.append(new_item)
    _save(questions)
    return {"question_id": new_item["question_id"], "message": "saved"}


@router.get("/questions", response_model=QuestionListResponse)
def list_questions():
    questions = _load()
    items = [
        QuestionListItem(
            question_id=q["question_id"],
            created_at=q["created_at"],
            raw_text=q["raw_text"],
            ask_doctor_count=len(q.get("ask_doctor", [])),
            record_id=q.get("record_id"),
        )
        for q in questions
    ]
    return QuestionListResponse(questions=items)


@router.get("/questions/{question_id}", response_model=QuestionDetailResponse)
def get_question(question_id: str):
    questions = _load()
    for q in questions:
        if q["question_id"] == question_id:
            return QuestionDetailResponse(
                question_id=q["question_id"],
                created_at=q["created_at"],
                raw_text=q["raw_text"],
                general_info=[GeneralInfoItem(**i) for i in q.get("general_info", [])],
                ask_doctor=q.get("ask_doctor", []),
                caution=q.get("caution", []),
                record_id=q.get("record_id"),
            )
    raise HTTPException(status_code=404, detail="Question not found")
