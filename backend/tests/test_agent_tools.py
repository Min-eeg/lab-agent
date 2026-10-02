# -*- coding: utf-8 -*-
"""
Agent 工具的契约测试: 不调大模型, 只验证工具本身的行为契约。

关注三件事:
1. 工具返回值必须是可解析的 JSON（agent 要靠它判断成功/失败）
2. 失败时必须 ok:false + error（LLM 靠这两个字段如实转述, 缺了就可能谎报成功）
3. dry_run 模式绝不落库（评测集批量回归的前提）
"""
import json

import pytest

from app.models.reservation import Reservation
from app.services import agent_tools


class User:
    id = 1
    role = "student"
    username = "tester"


class FakeLab:
    id = 2
    name = "电子电路实验室"
    location = "综合实验楼102"
    capacity = 30
    open_time = "08:00"
    close_time = "22:00"
    status = 1
    description = "测试用"


class FakeEquipment:
    id = 5
    name = "GPU 服务器"
    spec = "A100"
    status = 1
    lab_id = 2
    lab_name = "电子电路实验室"
    quantity = 1


class Page:
    def __init__(self, items, total):
        self.list = items
        self.total = total


class FakeDB:
    def __init__(self):
        self.added = []
        self.committed = 0

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 1
        self.added.append(obj)

    def commit(self):
        self.committed += 1


@pytest.fixture
def tools():
    db = FakeDB()
    return agent_tools.build_tools(db, User()), db


def _find(tools, name):
    return next(t for t in tools if t.name == name)


class TestGetToday:
    def test_returns_iso_date(self, tools):
        from datetime import datetime

        today, _ = tools
        out = _find(today, "get_today").invoke({})
        # 必须是 YYYY-MM-DD, 提示词要求模型按这个格式换算
        datetime.strptime(out, "%Y-%m-%d")
        assert len(out) == 10


class TestListOpenLabs:
    def test_json_shape(self, monkeypatch, tools):
        labs, _ = tools
        monkeypatch.setattr(
            "app.services.lab_service.get_lab_page_list",
            lambda *a, **k: Page([FakeLab()], 1),
        )
        out = _find(labs, "list_open_labs").invoke({"keywords": ""})
        data = json.loads(out)
        assert data["total"] == 1
        assert data["labs"][0]["id"] == 2
        assert data["labs"][0]["name"] == "电子电路实验室"


class TestListLabEquipments:
    def test_json_shape(self, monkeypatch, tools):
        labs, _ = tools
        monkeypatch.setattr(
            "app.services.equipment_service.get_equipment_page_list",
            lambda *a, **k: Page([FakeEquipment()], 1),
        )
        out = _find(labs, "list_lab_equipments").invoke({"lab_id": 2})
        data = json.loads(out)
        assert data["total"] == 1
        assert data["equipments"][0]["id"] == 5


class TestCreateReservationContract:
    def test_dry_run_does_not_write(self, monkeypatch):
        """dry_run=True 时必须走完校验但不落库, 返回假预约单号"""
        db = FakeDB()
        # 让校验全过: monkeypatch 掉 create_reservation 防止误落库
        called = []
        monkeypatch.setattr(
            "app.services.reservation_service.create_reservation",
            lambda *a, **k: called.append(1) or 888,
        )
        dry = agent_tools.build_tools(db, User(), dry_run=True)
        out = json.loads(
            _find(dry, "create_lab_reservation").invoke(
                {
                    "lab_id": 2,
                    "date": "2099-01-01",
                    "start_time": "14:00",
                    "end_time": "16:00",
                }
            )
        )
        assert out["ok"] is True
        assert out["dry_run"] is True
        assert out["reservation_id"] == -1
        assert called == [], "dry_run 不应调用落库函数"
        assert db.added == [], "dry_run 不应写入 Session"

    def test_failure_returns_ok_false_and_error(self, monkeypatch):
        """失败必须返回 ok:false + error, 否则 LLM 可能把失败说成成功"""
        from app.common.exceptions import BusinessException

        def boom(*a, **k):
            raise BusinessException(message="该时段已预约")

        monkeypatch.setattr(
            "app.services.reservation_service.create_reservation", boom
        )
        db = FakeDB()
        normal = agent_tools.build_tools(db, User())
        out = json.loads(
            _find(normal, "create_lab_reservation").invoke(
                {
                    "lab_id": 2,
                    "date": "2099-01-01",
                    "start_time": "14:00",
                    "end_time": "16:00",
                }
            )
        )
        assert out["ok"] is False
        assert "该时段已预约" in out["error"]
        # 失败时绝不能出现 reservation_id, 否则模型可能当成成功
        assert "reservation_id" not in out

    def test_exception_also_returns_structured_error(self, monkeypatch):
        """未捕获异常也要转成结构化错误, 不能把栈抛给模型"""

        def boom(*a, **k):
            raise RuntimeError("数据库炸了")

        monkeypatch.setattr(
            "app.services.reservation_service.create_reservation", boom
        )
        db = FakeDB()
        out = json.loads(
            _find(agent_tools.build_tools(db, User()), "create_lab_reservation").invoke(
                {
                    "lab_id": 2,
                    "date": "2099-01-01",
                    "start_time": "14:00",
                    "end_time": "16:00",
                }
            )
        )
        assert out["ok"] is False
        assert "数据库炸了" in out["error"]


class TestSystemPrompt:
    def test_contains_real_date(self):
        """回归: 提示词必须注入真实日期, 否则模型会编造今天导致预约被判过期"""
        from datetime import datetime

        from app.services.agent_service import build_system_prompt

        prompt = build_system_prompt()
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in prompt, "系统提示词必须包含服务器真实日期"
        assert "今天" in prompt

    def test_requires_confirmation_before_booking(self):
        from app.services.agent_service import build_system_prompt

        prompt = build_system_prompt()
        assert "确认" in prompt
        # 防幻觉护栏不能被删掉
        assert "绝对禁止说预约成功" in prompt