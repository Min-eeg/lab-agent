import os

# 国内网络直连 huggingface.co 会 SSL 证书校验失败, 走国内镜像兜底
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from pydoc import doc
from typing import final
from chromadb.api.models.Collection import Collection
from chromadb.utils import embedding_functions
import chromadb
from app.config import BASE_DIR

KB_DIR = BASE_DIR / "data" / "kb"
CHROMA_DIR = BASE_DIR / "data" / "chroma"
# 本地模型目录(由 scripts/download_model.py 从 ModelScope 下载)
LOCAL_MODEL_DIR = BASE_DIR / "data" / "models" / "bge-small-zh-v1.5"

_collection = None

# 优先加载本地模型(离线可用); 没有时才从网上拉取
if (LOCAL_MODEL_DIR / "config.json").exists() and (
    (LOCAL_MODEL_DIR / "model.safetensors").exists()
    or (LOCAL_MODEL_DIR / "pytorch_model.bin").exists()
):
    _model_name = str(LOCAL_MODEL_DIR)
    # 本地模型已就绪, 禁用 huggingface_hub 的在线版本检查, 避免断网时启动卡在重试上
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
else:
    _model_name = "BAAI/bge-small-zh-v1.5"

_embedding_fn = None


def get_embedding_fn():
    """懒加载 embedding 模型：只加载一次，之后进程内复用同一个实例。

    关键: 必须用 _model_name(本地路径优先)，不要硬编码 "BAAI/bge-small-zh-v1.5"。
    硬编码会让 sentence-transformers 每次都去 HuggingFace 做版本检查/下载，
    国内网络下这一来就是 30~40 秒(实测 40.8s)，而本地模型加载只需 1~2 秒。
    """
    global _embedding_fn
    if _embedding_fn is not None:
        return _embedding_fn
    _embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=_model_name  # 复用顶部算好的：本地目录存在则用本地，否则回落线上名
    )
    return _embedding_fn


def get_collcetion() -> Collection:
    """向量库的初始化"""

    global _collection
    if _collection is not None:
        return _collection
    KB_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    col = client.get_or_create_collection(
        name="lab_kb", embedding_function=get_embedding_fn()
    )
    if col.count() == 0:
        ids = []
        docs = []
        metas = []
        for path in sorted(KB_DIR.glob("*.md")):
            text = path.read_text(encoding="UTF-8").strip()
            if not text:
                continue
            docs.append(text)
            ids.append(path.stem)
            metas.append({"source": path.name})
        if docs:
            col.add(ids=ids, documents=docs, metadatas=metas)
    _collection = col
    return col


def warmup():
    """启动时预热：把模型加载 + 首次检索的开销付在启动阶段，别落在第一个用户请求上"""
    col = get_collcetion()
    if col.count() > 0:
        col.query(query_texts=["预热"], n_results=1)


def search(query: str):
    """根据关键字去检索向量库"""
    col = get_collcetion()
    if col.count() == 0:
        return ""
    limit = min(5, col.count())
    res = col.query(query_texts=[query], n_results=limit)
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    distances = (res.get("distances") or [[]])[0]

    """
    以下是检索出来的资料：
    [预约规则.md]

    # 实验室预约规则...

    
    [安全规范.md]

    安全规范....
    """
    score_parts = []
    for doc, metas, dist in zip(docs, metas, distances):
        # 0-1 越接近1表示越相关
        score = 1 / (1 + dist)
        if score < 0.5:
            continue
        name = metas.get("source") or ""
        score_parts.append({"score": score, "content": f"[{name}]\n{doc}"})
    print(f"检索出来的 score_parts：{score_parts}")
    score_parts.sort(key=lambda x: x["score"], reverse=True)
    final_parts = [item["content"] for item in score_parts[:2]]
    return "\n\n".join(final_parts)
