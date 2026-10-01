from typing import Any
from pydantic import BaseModel

class Response(BaseModel):
    """统一封装返回格式"""
    code: int
    message: str
    data: Any = None

    @classmethod
    def success(cls, data: Any = None, message: str = "success"):
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(cls, code: int=500, message: str = "error"):
        return cls(code=code, message=message)

class PageResponse(BaseModel):
    list: Any=[]
    total: int=0