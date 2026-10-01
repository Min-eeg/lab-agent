from app.database import Base
from sqlalchemy.orm import Mapped,mapped_column

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float



class User(Base):
    __tablename__ = "users"
    __table_args__ = {"comment": "用户信息表"}

    username: Mapped[str] = mapped_column(String(50), nullable=False, comment="账号")
    password: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码")
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="名称")
    phone: Mapped[str | None] = mapped_column(String(20), comment="手机号")
    email: Mapped[str | None] = mapped_column(String(50), comment="邮箱")
    role: Mapped[str] = mapped_column(String(20), nullable=False, comment="角色: admin:管理员, user:学生")
    avatar: Mapped[str | None] = mapped_column(String(200), comment="头像")
    status: Mapped[int]= mapped_column(default=1, comment="状态: 1:正常, 0:禁用")