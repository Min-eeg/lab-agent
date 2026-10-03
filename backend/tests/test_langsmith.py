# -*- coding: utf-8 -*-
"""
LangSmith 追踪接入的测试。

核心原则: 没配 API key 时必须"完全无感"——
不设环境变量、不报错、不影响业务。配了 key 才启用。
"""
import os

import pytest


class TestTracingToggle:
    def test_disabled_without_key(self, monkeypatch):
        from app.config import Settings, setup_langsmith_tracing

        monkeypatch.setenv("LANGSMITH_API_KEY", "")
        monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
        monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)

        assert setup_langsmith_tracing() is False
        # 关键: 没配 key 时绝不能污染环境变量
        assert "LANGSMITH_TRACING" not in os.environ
        assert "LANGCHAIN_TRACING_V2" not in os.environ

    def test_enabled_with_key(self, monkeypatch):
        from app.config import setup_langsmith_tracing, settings

        monkeypatch.setattr(settings, "LANGSMITH_API_KEY", "ls__dummy")
        monkeypatch.setattr(settings, "LANGSMITH_PROJECT", "test-project")

        assert setup_langsmith_tracing() is True
        assert os.environ["LANGSMITH_TRACING"] == "true"
        # 老版本变量名也要设，避免不同 langchain 版本行为不一致
        assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
        assert os.environ["LANGSMITH_API_KEY"] == "ls__dummy"
        assert os.environ["LANGSMITH_PROJECT"] == "test-project"

    def test_agent_carries_trace_metadata(self):
        """工具/图调用应带上 metadata，才能在 LangSmith 里按用户筛选链路"""
        import inspect

        from app.services import agent_service

        src = inspect.getsource(agent_service)
        assert "metadata" in src, "agent 调用缺少 metadata 标签"
        assert "run_name" in src, "agent 调用缺少 run_name（链路名）"


class TestConfigDefaults:
    def test_settings_importable_without_env_file(self):
        """无 .env 时配置仍可加载（CI 与单元测试依赖这一点）"""
        from app.config import settings

        assert settings.DATABASE_URL
        assert settings.LLM_MODEL

    def test_langsmith_fields_exist(self):
        from app.config import Settings

        fields = Settings.model_fields
        for name in ("LANGSMITH_API_KEY", "LANGSMITH_PROJECT", "LANGSMITH_ENDPOINT"):
            assert name in fields, f"缺少配置项 {name}"