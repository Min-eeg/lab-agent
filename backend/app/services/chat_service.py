"""AI 对话记录持久化：问答落 MySQL，换设备登录也能看到历史。

设计取舍：
- 每个用户始终只有「最近一个活跃会话」，和前端单会话的交互保持一致；
  表结构保留 sessions / messages 两层，未来做历史会话侧栏不用再改表。
- 落库时机在流式回答「结束之后」（done 事件）：流到一半的内容是残缺的，不能存；
  出错（error 事件）的轮次也不入库，避免把失败回答当成历史上下文。
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession

TITLE_LEN = 20  # 会话标题取首条用户消息的前 20 个字


def _active_session(db: Session, user_id: int) -> ChatSession | None:
    """用户最近活跃（最后有动静）的会话。"""
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        # id 兜底：同一秒内建的多个会话也能稳定取到最新那个
        .order_by(ChatSession.update_time.desc(), ChatSession.id.desc())
        .first()
    )


def extract_user_question(messages) -> str:
    """从请求的消息列表里取最后一条用户消息——即本轮要问的问题。"""
    for message in reversed(messages or []):
        role = getattr(message, "role", None)
        content = getattr(message, "content", None)
        if role == "user" and str(content or "").strip():
            return str(content).strip()
    return ""


def append_round(
    db: Session, user_id: int, user_text: str, assistant_text: str
) -> int | None:
    """把一轮完整问答写入数据库，返回会话 id。

    任何一边为空都不落库（流式失败 / 空回答时不留垃圾历史）。
    """
    user_text = (user_text or "").strip()
    assistant_text = (assistant_text or "").strip()
    if not user_text or not assistant_text:
        return None

    session = _active_session(db, user_id)
    if session is None:
        session = ChatSession(user_id=user_id, title=user_text[:TITLE_LEN])
        db.add(session)
        db.flush()  # flush 才能拿到自增 id，还不提交事务
    else:
        # 手动触一下 update_time，让「最近活跃」排序跟着最新消息走
        session.update_time = datetime.now()
        db.add(session)

    db.add(ChatMessage(session_id=session.id, role="user", content=user_text))
    db.add(
        ChatMessage(session_id=session.id, role="assistant", content=assistant_text)
    )
    db.commit()
    return session.id


def get_history(db: Session, user_id: int) -> dict:
    """最近活跃会话 + 全部消息（按时间正序），没有则返回空结构。"""
    session = _active_session(db, user_id)
    if session is None:
        return {"session_id": None, "title": None, "messages": []}
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.id.asc())
        .all()
    )
    return {
        "session_id": session.id,
        "title": session.title,
        "messages": [
            {"role": item.role, "content": item.content} for item in messages
        ],
    }


def clear_history(db: Session, user_id: int) -> int:
    """删除该用户全部会话与消息，返回删除的会话数。"""
    session_ids = [
        item.id
        for item in db.query(ChatSession).filter(ChatSession.user_id == user_id).all()
    ]
    if not session_ids:
        return 0
    db.query(ChatMessage).filter(ChatMessage.session_id.in_(session_ids)).delete(
        synchronize_session=False
    )
    db.query(ChatSession).filter(ChatSession.user_id == user_id).delete(
        synchronize_session=False
    )
    db.commit()
    return len(session_ids)
