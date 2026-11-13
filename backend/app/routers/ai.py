from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import AIChatRequest
from ..services.ai_chat_service import answer_village_question

router = APIRouter(prefix='/api/ai', tags=['ai'])
_WINDOW_SECONDS = 60
_MAX_REQUESTS = 20
_buckets: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def _allow_request(key: str) -> bool:
    now = monotonic()
    with _lock:
        bucket = _buckets[key]
        while bucket and now - bucket[0] >= _WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= _MAX_REQUESTS:
            return False
        bucket.append(now)
        return True


@router.post('/chat')
async def chat(payload: AIChatRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else 'unknown'
    if not _allow_request(client_ip):
        raise HTTPException(status_code=429, detail='提问过于频繁，请稍后再试。')
    result = await answer_village_question(
        db=db,
        message=payload.message,
        history=[item.model_dump() for item in payload.history],
        village_ref=payload.village_ref,
        deep_thinking=payload.deep_thinking,
    )
    return result
