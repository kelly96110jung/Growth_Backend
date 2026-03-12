from fastapi import APIRouter

from app.models.schemas import TextRequest, SummaryResponse
from app.services.summarizer import summarize_text

router = APIRouter()


@router.post("/summary", response_model=SummaryResponse)
def summarize(request: TextRequest):
    summary_result = summarize_text(request.text)
    return SummaryResponse(summary=summary_result)