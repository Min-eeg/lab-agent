import time
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File
import os
from pathlib import Path
from app.common.response import Response
from app.common.exceptions import BusinessException
from app.config import ALLOWED_EXTENSIONS, BASE_DIR, MAX_FILE_SIZE, UPLOAD_DIR
from app.schemas.file import FileResponse

router=APIRouter(prefix="/files", tags=["文件上传下载接口"])

@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    """文件上传接口"""
    if not file.filename:
        raise BusinessException(message="文件名不能为空")

    # 原始的文件名 用户头像.jpg
    orignal_name = os.path.basename(file.filename)
    # 文件后缀 .jpg
    ext = Path(orignal_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise BusinessException(message=f"不支持的文件后缀：{ext}")
    # 文件大小校验
    if file.size and file.size > MAX_FILE_SIZE:
        raise BusinessException(message=f"文件大小不能超过{MAX_FILE_SIZE // 1024 //1024}MB")
    # 设置唯一的文件名
    disk_name = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}{ext}"
    #文件存储的实际路径
    save_path = UPLOAD_DIR / disk_name

    #流式写入文件
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return Response.success(
        data= FileResponse(
            original_name=orignal_name,
            disk_name=disk_name,
            size=file.size,
            url=f"/uploads/{disk_name}",
        )
    )
