from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
from typing import List
import re
import json
import asyncio
import logging

from app.ws_stt import ws_stt_endpoint

# ----------------------------
# logging
# ----------------------------
logger = logging.getLogger(__name__)

# ----------------------------
# Session cleanup (20 min TTL)
# ----------------------------
# ws_stt.py 안에서 session_manager를 이미 만들어 쓰고 있을 가능성이 높아서,
# "같은 인스턴스"를 잡아오려고 시도함.
try:
    from ws_stt import session_manager as stt_session_manager  # type: ignore
except Exception:
    stt_session_manager = None  # ws_stt.py에 없으면 None


async def session_cleanup_loop(
    session_manager,
    *,
    interval_seconds: int = 60,
    ttl_minutes: int = 20,
):
    """
    Periodically expire inactive sessions.
    session_manager는 expire_inactive_sessions(ttl_minutes=...)를 지원해야 함.
    """
    while True:
        try:
            if session_manager is not None:
                expired = session_manager.expire_inactive_sessions(ttl_minutes=ttl_minutes)
                if expired:
                    logger.info(f"Expired sessions: {expired}")
        except Exception as e:
            logger.exception("Session cleanup loop error", exc_info=e)

        await asyncio.sleep(interval_seconds)


# ----------------------------
# FastAPI app
# ----------------------------
app = FastAPI()


@app.on_event("startup")
async def on_startup():
    # 서버가 켜질 때 타임아웃 정리 루프 시작
    asyncio.create_task(
        session_cleanup_loop(
            stt_session_manager,
            interval_seconds=60,  # 1분마다 체크
            ttl_minutes=20,       # 20분 비활성 세션 종료
        )
    )


# ----------------------------
# WebSocket STT endpoint
# ----------------------------
@app.websocket("/ws/stt")
async def ws_stt(websocket: WebSocket):
    await ws_stt_endpoint(websocket)


# ============================
# below: (schema.md 대응) 기존 summarize 관련 코드 유지
# ============================

class SummarizeRequest(BaseModel):
    raw_text: str


class EasyTerm(BaseModel):
    term: str
    easy: str


class NextAction(BaseModel):
    title: str
    detail: str


class SummarizeResponse(BaseModel):
    summary_3sent: str
    easy_terms: List[EasyTerm]
    next_actions: List[NextAction]
    warnings: List[str]


# ============================
# utils
# ============================

def force_3_sentences(text: str) -> str:
    text = (text or "").strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    parts = [p for p in parts if p]

    if len(parts) >= 3:
        return " ".join(parts[:3])

    while len(parts) < 3:
        parts.append("추가 안내를 의료진의 설명을 따르세요.")
    return " ".join(parts)


def extract_json_block(text: str) -> str:
    """
    LLM 출력이 막 섞여도 {...}만 뽑기
    """
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("JSON 블록을 찾지 못함")
    return m.group(0)


def sanitize_to_schema(obj: dict) -> dict:
    """
    어떤 obj가 와도 schema 형태로 안전하게 맞춤
    """
    summary = force_3_sentences(str(obj.get("summary_3sent", "")).strip())

    easy_terms = obj.get("easy_terms", [])
    if not isinstance(easy_terms, list):
        easy_terms = []
    easy_terms2 = []
    for it in easy_terms[:5]:
        if isinstance(it, dict):
            term = str(it.get("term", "")).strip()
            easy = str(it.get("easy", "")).strip()
            if term and easy:
                easy_terms2.append({"term": term, "easy": easy})

    next_actions = obj.get("next_actions", [])
    if not isinstance(next_actions, list):
        next_actions = []
    next_actions2 = []
    for it in next_actions[:3]:
        if isinstance(it, dict):
            title = str(it.get("title", "")).strip()
            detail = str(it.get("detail", "")).strip()
            if title and detail:
                next_actions2.append({"title": title, "detail": detail})

    warnings = obj.get("warnings", [])
    if isinstance(warnings, list):
        warnings2 = [str(x).strip() for x in warnings if str(x).strip()]
    else:
        warnings2 = []

    # 맨 앞 경고: 진단 아님
    if not any("진단" in w for w in warnings2):
        warnings2.insert(
            0,
            "이 결과는 진단이 아니라 이해를 돕기 위한 요약입니다. 증상이 심해지면 의료진과 상담하세요.",
        )

    return {
        "summary_3sent": summary,
        "easy_terms": easy_terms2,
        "next_actions": next_actions2,
        "warnings": warnings2,
    }


def fallback(reason: str) -> dict:
    """
    어떤 상황에도 JSON 구조를 깨지 않고 반환
    """
    return {
        "summary_3sent": force_3_sentences(
            "요약 생성에 실패했습니다. 의료진의 설명을 다시 확인하세요. 증상이 심해지면 병원을 방문하세요."
        ),
        "easy_terms": [],
        "next_actions": [
            {"title": "의료진 안내 확인", "detail": "진단/처방/주의사항을 다시 확인하세요."},
            {"title": "증상 기록", "detail": "언제부터 어떤 증상이 있는지 메모해 다음 진료 때 공유하세요."},
        ],
        "warnings": [
            "이 결과는 진단이 아니라 이해를 돕기 위한 요약입니다. 증상이 심해지면 의료진과 상담하세요.",
            f"LLM 출력 파싱 실패로 기본 응답 반환: {reason}",
        ],
    }


# TODO: 여기서 실제 LLM 호출로 바꾸면 됨 (지금은 임시)
def call_llm(raw_text: str) -> str:
    """
    반환은 문자열 하나.
    나중에 Gemini/OpenAI 붙이면 이 함수를 바꾸면 됨.
    """
    return f"""
아래는 결과입니다.
{json.dumps({
    "summary_3sent": f"{raw_text}에 대한 쉬운 요약입니다. 핵심만 정리했습니다. 다음 행동을 제안합니다.",
    "easy_terms": [{"term": "검사", "easy": "몸 상태를 확인하기 위해 하는 절차"}],
    "next_actions": [{"title": "의료진 안내 확인", "detail": "설명 중 이해 안 될 부분은 의료진에게 질문하세요."}],
    "warnings": []
}, ensure_ascii=False)}
감사합니다.
""".strip()


def safe_summarize(raw_text: str) -> dict:
    last_err = None

    # 최대 3번 재시도
    for _ in range(3):
        try:
            out = call_llm(raw_text)
            j = extract_json_block(out)
            obj = json.loads(j)
            return sanitize_to_schema(obj)
        except Exception as e:
            last_err = str(e)

    return fallback(last_err or "unknown")


# ============================
# endpoints
# ============================

@app.get("/health")
def health():
    return {"ok": True}


@app.post("/summarize", response_model=SummarizeResponse)
def summarize(req: SummarizeRequest):
    return safe_summarize(req.raw_text)
