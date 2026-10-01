from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import Integer, String
from app.database import Base

class Lab(Base):
    __tablename__ = "labs"
    __table_args__= {"comment": "实验室信息"}

    name: Mapped[str] = mapped_column(String(50), comment="名称")
    location: Mapped[str | None] = mapped_column(String(100), comment="位置",nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, comment="实验室容量",default=0)
    open_time: Mapped[str | None] = mapped_column(String(50), comment="开放开始时间",nullable=True)
    close_time: Mapped[str | None] = mapped_column(String(50), comment="开放结束时间",nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), comment="简介",nullable=True)
    img: Mapped[str | None] = mapped_column(String(200), comment="封面图片",nullable=True)
    status: Mapped[int] = mapped_column(Integer, comment="实验室状态:0:不可用 1:可用",default=1) # 0:不可用 1:可用