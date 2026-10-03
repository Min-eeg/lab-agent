import asyncio
from contextlib import asynccontextmanager
from fastapi.exceptions import RequestValidationError
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from app.config import UPLOAD_DIR, settings, setup_langsmith_tracing
from app.models.user import User  # noqa: F401  确保模型已注册到 Base.metadata
from app.models.lab import Lab  # noqa: F401  确保模型已注册到 Base.metadata
from app.models.equipment import Equipment  # noqa: F401  确保模型已注册到 Base.metadata
from app.models.reservation import Reservation  # noqa: F401  确保模型已注册到 Base.metadata
from app.database import Base, engine
from app.api import api, reservation
from starlette.middleware.cors import CORSMiddleware
from app.common.exceptions import (
    BusinessException,
    business_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    global_exception_handler
)
from app.services import reservation_service, kb_service
from app.common import logger

# LangSmith 链路追踪：必须在创建 LLM 实例之前设置环境变量，
# LangChain 的所有子对象（ChatOpenAI / ToolNode / LangGraph 图）会自动继承
if setup_langsmith_tracing():
    logger.info(f"LangSmith 追踪已开启，项目: {settings.LANGSMITH_PROJECT}")
else:
    logger.info("未配置 LANGSMITH_API_KEY，链路追踪保持关闭")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 预热向量库：模型加载（约 15s）挪到启动阶段，避免首个请求超过前端 30s 超时
    try:
        await asyncio.to_thread(kb_service.warmup)  # to_thread：别阻塞事件循环
    except Exception:
        logger.exception("向量库预热失败，服务继续启动")

    # 延迟建表：放在启动钩子里，避免导入模块时因数据库不可达而直接崩溃
    try:
        Base.metadata.create_all(bind=engine)
        print("数据库表已就绪")
    except Exception as e:  # 数据库异常时服务仍可启动，并给出清晰提示
        print(f"警告: 数据库建表失败（服务仍会启动）: {e}")
    # 后台任务：定期扫描过期预约（create_task 调度；不能直接 await，否则会被 while True 卡死在启动）
    scan_task = asyncio.create_task(reservation_service.run_expire_scan())

    yield

    # 应用关闭时取消扫描任务，避免悬挂协程
    scan_task.cancel()
    try:
        await scan_task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
    )
app.include_router(api)

app.add_exception_handler(BusinessException, business_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# 挂载静态的文件目录
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/")
async def root():
    return {"message": "FastAPI is running!"}
