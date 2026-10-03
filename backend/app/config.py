from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent# 后端根目录

# 默认值仅用于"无 .env 的场景"(单元测试 / CI)。
# 单元测试用FakeDB 替身, 不连真实库也不调大模型, 所以这些占位值不会被真正使用。
# 生产环境请务必配置 .env —— 缺配置时这些占位值会让连接失败, 而不是静默用错配置。
DEFAULTS = {
    "DATABASE_URL": "mysql+pymysql://root:password@localhost:3306/lab_agent?charset=utf8mb4",
    "JWT_SECRET_KEY": "dev-only-insecure-secret-key",
    "LLM_API_KEY": "dev-only-placeholder",
    "LLM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "LLM_MODEL": "qwen-plus",
    # LangSmith 未配置 key 时保持空，追踪自动关闭（不填也能正常跑）
    "LANGSMITH_API_KEY": "",
    "LANGSMITH_PROJECT": "lab-agent",
}


class Settings(BaseSettings):
    # 给了默认值, 单元测试/CI 没有 .env 也能导入; 本地 .env 会覆盖它们
    DATABASE_URL: str = DEFAULTS["DATABASE_URL"]

    JWT_SECRET_KEY: str = DEFAULTS["JWT_SECRET_KEY"]
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    LLM_API_KEY: str = DEFAULTS["LLM_API_KEY"]
    LLM_BASE_URL: str = DEFAULTS["LLM_BASE_URL"]
    LLM_MODEL: str = DEFAULTS["LLM_MODEL"]

    # LangSmith 链路追踪（可选）：填了 API key 自动开启，没填完全不影响
    LANGSMITH_API_KEY: str = DEFAULTS["LANGSMITH_API_KEY"]
    LANGSMITH_PROJECT: str = DEFAULTS["LANGSMITH_PROJECT"]
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8")


settings = Settings()


def setup_langsmith_tracing() -> bool:
    """把追踪配置写进环境变量，LangChain 会自动读取。

    为什么用环境变量而不是传 callback:
    LangChain / LangGraph 的所有子对象（ChatOpenAI、ToolNode、整张图）
    都会自动继承，无需在每个节点手工传参 —— 一行配置全局生效。

    没配 API key 时返回 False，追踪保持关闭，完全不影响正常业务。
    """
    if not settings.LANGSMITH_API_KEY:
        return False
    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
    os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    # 兼容老版本环境变量名，避免不同版本行为不一致
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_TRACING"] = "true"
    return True


UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
    ".md",
}
