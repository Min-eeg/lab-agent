from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

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

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8")

settings = Settings()


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
