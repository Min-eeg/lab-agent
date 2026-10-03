# -*- coding: utf-8 -*-
"""
RAG 检索的性能回归测试。

背景（真实踩过的坑）:
    kb_service.get_embedding_fn() 里曾硬编码 model_name="BAAI/bge-small-zh-v1.5"，
    而顶部明明已经算好了本地路径 _model_name。硬编码会让 sentence-transformers
    每次都去 HuggingFace 做版本检查/下载 —— 国内网络下实测单次加载 40.8 秒，
    检索耗时 11.37 秒。改用 _model_name 后检索降到 0.01 秒。

所以这里用测试把"必须用本地模型"锁住，避免回退。
"""
import time

import pytest


class TestLocalModelUsage:
    def test_uses_resolved_model_name(self):
        """必须用 _model_name（本地路径优先），不能硬编码线上模型名"""
        from app.services import kb_service

        assert kb_service._model_name == str(kb_service.LOCAL_MODEL_DIR) or (
            kb_service._model_name == "BAAI/bge-small-zh-v1.5"
        ), "_model_name 应当是本地目录（本地模型存在时）或线上名兜底"

    def test_no_hardcoded_model_name_in_source(self):
        """源码里不允许在 get_embedding_fn 中出现硬编码的线上模型名"""
        import inspect

        from app.services import kb_service

        src = inspect.getsource(kb_service.get_embedding_fn)
        # 只允许出现 _model_name 变量引用，不允许字面量
        assert 'model_name="BAAI' not in src, "get_embedding_fn 又硬编码了线上模型名"
        assert "model_name=_model_name" in src, "应使用 _model_name 变量"

    def test_offline_mode_enabled_when_local_model_present(self):
        """本地模型就绪时应设置 HF_HUB_OFFLINE，避免联网校验拖慢启动"""
        import os

        from app.services import kb_service

        local_ready = (kb_service.LOCAL_MODEL_DIR / "config.json").exists()
        if local_ready:
            assert os.environ.get("HF_HUB_OFFLINE") == "1", (
                "本地模型可用时应设置 HF_HUB_OFFLINE=1 跳过联网版本检查"
            )

    def test_embedding_fn_is_cached(self):
        """get_embedding_fn 必须复用同一实例，不能每次重建"""
        from app.services import kb_service

        first = kb_service.get_embedding_fn()
        second = kb_service.get_embedding_fn()
        assert first is second, "embedding 函数应被缓存复用（重建会导致每次都加载模型）"


@pytest.mark.slow
class TestSearchPerformance:
    def test_search_is_fast_after_warmup(self, monkeypatch):
        """预热后每次检索应达到毫秒级（曾经的性能坑是 11 秒）"""
        from app.services import kb_service

        kb_service.warmup()  # 预热
        start = time.time()
        kb_service.search("化学实验室开放时间")
        elapsed = time.time() - start
        # 放宽到3 秒留足CI 机器波动余量；实测本地是 0.01 秒
        assert elapsed < 3, f"检索耗时 {elapsed:.2f}s，明显变慢（检查是否又走了线上模型）"

    def test_search_returns_expected_docs(self):
        """检索质量不能因为换模型而退化"""
        from app.services import kb_service

        kb_service.warmup()
        result = kb_service.search("化学实验室开放时间")
        assert "开放时间" in result, "开放时间查询应命中开放时间文档"