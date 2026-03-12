from fastapi import APIRouter

from app.models.schemas import TextRequest, ExplainResponse, TermItem
from app.services.term_extractor import extract_terms

router = APIRouter()


@router.post("/explain", response_model=ExplainResponse)
def explain_terms(request: TextRequest):
    terms_result = extract_terms(request.text)
    term_items = [TermItem(**term) for term in terms_result]
    return ExplainResponse(terms=term_items)