from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = {"comment": "AI 对话会话"}

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, comment="所属用户", nullable=False
    )
    title: Mapped[str] = mapped_column(
        String(100), comment="会话标题（取首条用户消息前20字）", default="新对话"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = {"comment": "AI 对话消息"}

    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id"), index=True, comment="所属会话", nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(20), comment="角色: user / assistant", nullable=False
    )
    content: Mapped[str] = mapped_column(Text, comment="消息正文", nullable=False)
