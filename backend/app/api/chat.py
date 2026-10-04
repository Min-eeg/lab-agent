from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["AI对话记录相关API"])


@router.get("/history")
def get_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """拉取当前用户最近的对话记录（换设备登录后恢复聊天用）。"""
    return Response.success(data=chat_service.get_history(db, current_user.id))


@router.delete("/history")
def clear_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """清空当前用户的全部对话记录（对应前端「清空对话」按钮）。"""
    chat_service.clear_history(db, current_user.id)
    return Response.success()
