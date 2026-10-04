from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.common import logger
from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.ai import ChatMessage, ChatRequest
from app.services import agent_service, ai_service, chat_service
import json
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/ai", tags=["AI相关的API"])


@router.post("/chat")
def chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = agent_service.run_agent(db, current_user, data)
    # 非流式同样落库，保持两种接口的历史记录行为一致
    chat_service.append_round(
        db, current_user.id, chat_service.extract_user_question(data.messages), content
    )
    return Response.success(data=ChatMessage(role="assistant", content=content))


def _sse_line(payload: dict) -> str:
    """拼一条 SSE 帧：必须以 data: 开头，且以空行（\n\n）结束。"""
    # ensure_ascii=False：中文不要被转成 \uXXXX
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
def chat_stream(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    def event_gen():
        # 内层生成器：取出业务事件，包装成 SSE 文本再往外 yield
        collected = []  # 逐 token 攒回答全文，done 时整段落库
        for event in agent_service.stream_agent(db, current_user, data):
            if event.get("type") == "token":
                collected.append(event.get("content") or "")
            elif event.get("type") == "done":
                # 落库时机必须等流跑完：半截回答是残缺的不能存，error 的轮次也不存
                try:
                    chat_service.append_round(
                        db,
                        current_user.id,
                        chat_service.extract_user_question(data.messages),
                        "".join(collected),
                    )
                except Exception:
                    # 落库失败不影响已经发给用户的回答
                    logger.exception("对话记录落库失败")
            yield _sse_line(event)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",  # 告诉浏览器这是 SSE 流
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 有 Nginx 时避免缓冲整段再吐
        },
    )
