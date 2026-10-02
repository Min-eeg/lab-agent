# -*- coding: utf-8 -*-
"""
预约服务的纯逻辑单元测试（不碰数据库、不调大模型）。

重点覆盖历史上真实踩过的坑：
1. 时间参数规范化（LLM 会传 "9:00" / "2026-9-30" / "14:00:00"）
2. 0/1 状态字段不能用真值判断（status=0 也是有效值）
3. 时间字符串比较的坑（"9:00" > "11:00"）
"""
from datetime import datetime, timedelta

import pytest

from app.models.reservation import Reservation
from app.schemas.reservation import ReservationCreateRequest
from app.services.reservation_service import (
    _norm_date,
    _norm_time,
    create_reservation,
)


class User:
    """最小用户替身，避免依赖数据库"""

    id = 1
    role = "student"


class FakeLab:
    """实验室替身"""

    def __init__(self, status=1, open_time="08:00", close_time="22:00"):
        self.id = 1
        self.name = "测试实验室"
        self.status = status
        self.open_time = open_time
        self.close_time = close_time


class FakeDB:
    """记录 add/commit 的假 Session，并按服务真实查询顺序返回假数据。

    服务里的校验链: 查实验室 → 查设备 → 查冲突预约, 这里逐个喂回替身对象。
    """

    def __init__(self, lab="__default__", equipment=None, conflict=None):
        self.added = []
        self.committed = 0
        # lab=None 表示"实验室不存在"这个分支, 所以不能用 None 当默认值
        self.lab = FakeLab() if lab == "__default__" else lab
        self.equipment = equipment
        self.conflict = conflict

    def add(self, obj):
        # 真实 DB 在 commit 后由数据库回填自增主键, 这里模拟一下
        if getattr(obj, "id", None) is None:
            obj.id = 999
        self.added.append(obj)

    def commit(self):
        self.committed += 1

    def refresh(self, obj):
        pass

    def query(self, model, *args, **kwargs):
        name = getattr(model, "__name__", "")
        db = self

        class _Q:
            def filter(self, *a, **k):
                return self

            def first(self):
                return None

        if name == "Lab":
            q = _Q()
            q.first = lambda: db.lab
            return q
        if name == "Equipment":
            q = _Q()
            q.first = lambda: db.equipment
            return q
        if name == "Reservation":
            # 冲突预约: 服务最后一步要判断时段是否已被占用
            q = _Q()
            q.first = lambda: db.conflict
            return q
        return _Q()


# ---------------------------------------------------------------- 规范化


class TestNormalize:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("9:00", "09:00"),
            ("09:00", "09:00"),
            ("9:5", "09:05"),
            ("14:00:00", "14:00"),
            ("14:00", "14:00"),
            ("23:59:59", "23:59"),
        ],
    )
    def test_time(self, raw, expected):
        assert _norm_time(raw) == expected

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("2026-9-30", "2026-09-30"),
            ("2026-09-30", "2026-09-30"),
            ("2026/10/01", "2026-10-01"),
            ("2026.10.01", "2026-10-01"),
        ],
    )
    def test_date(self, raw, expected):
        assert _norm_date(raw) == expected

    @pytest.mark.parametrize("raw", ["明天", "下周一", "", "abc", "2026-13-45", "2026年10月1日"])
    def test_invalid_raises(self, raw):
        from app.common.exceptions import BusinessException

        with pytest.raises(BusinessException):
            _norm_date(raw)


class TestStringCompareTrap:
    """回归: 字符串比较下 '9:00' > '11:00'，曾导致合法时段被判为非法"""

    def test_nine_oclock_is_earlier_than_eleven(self):
        assert "09:00" < "11:00"
        # 这就是为什么必须先规范化再比较
        assert _norm_time("9:00") < _norm_time("11:00")


# ---------------------------------------------------------------- 创建预约


def _req(**kwargs):
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    data = {
        "lab_id": 1,
        "equipment_id": None,
        "date": tomorrow,
        "start_time": "14:00",
        "end_time": "16:00",
        "remark": None,
    }
    data.update(kwargs)
    return ReservationCreateRequest(**data)


class TestCreateReservation:
    def test_normalizes_and_returns_id(self):
        db = FakeDB()
        rid = create_reservation(
            db, User(), _req(start_time="9:00", end_time="11:00")
        )
        assert isinstance(rid, int)
        assert db.committed == 1
        saved = db.added[0]
        # 入库值必须是规范化后的, 否则字符串比较会出错
        assert (saved.start_time, saved.end_time) == ("09:00", "11:00")

    def test_rejects_end_before_start(self):
        from app.common.exceptions import BusinessException

        with pytest.raises(BusinessException):
            create_reservation(
                FakeDB(), User(), _req(start_time="14:00", end_time="11:00")
            )

    def test_rejects_past_date(self):
        from app.common.exceptions import BusinessException

        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        with pytest.raises(BusinessException):
            create_reservation(FakeDB(), User(), _req(date=yesterday))

    def test_rejects_invalid_date_format(self):
        from app.common.exceptions import BusinessException

        with pytest.raises(BusinessException):
            create_reservation(FakeDB(), User(), _req(date="明天"))

    def test_rejects_closed_lab(self):
        from app.common.exceptions import BusinessException

        with pytest.raises(BusinessException):
            create_reservation(FakeDB(lab=FakeLab(status=0)), User(), _req())

    def test_rejects_missing_lab(self):
        from app.common.exceptions import BusinessException

        with pytest.raises(BusinessException):
            create_reservation(FakeDB(lab=None), User(), _req())

    def test_rejects_before_open_time(self):
        from app.common.exceptions import BusinessException

        with pytest.raises(BusinessException):
            create_reservation(
                FakeDB(lab=FakeLab(open_time="09:00")),
                User(),
                _req(start_time="08:00", end_time="10:00"),
            )

    def test_rejects_after_close_time(self):
        from app.common.exceptions import BusinessException

        with pytest.raises(BusinessException):
            create_reservation(
                FakeDB(lab=FakeLab(close_time="18:00")),
                User(),
                _req(start_time="16:00", end_time="19:00"),
            )

    def test_rejects_time_conflict(self):
        """时段冲突: 已有 14:00-16:00 的预约, 再约 15:00-17:00 应被拒"""
        from app.common.exceptions import BusinessException

        db = FakeDB(conflict=Reservation(id=1))
        with pytest.raises(BusinessException):
            create_reservation(
                db, User(), _req(start_time="15:00", end_time="17:00")
            )


# ---------------------------------------------------------------- 状态字段


class TestStatusField:
    """回归: status=0(待审核) 是有效值，早期用 `if status:` 会把它过滤掉"""

    def test_zero_status_is_valid_value(self):
        res = Reservation(id=1, lab_id=1, date="2026-10-01", start_time="14:00", end_time="16:00", status=0)
        assert res.status == 0
        # 真值判断在这里是错的
        assert not res.status
        assert res.status is not None

    def test_status_values_are_ints(self):
        for value in (0, 1, 2, 3):
            res = Reservation(id=1, lab_id=1, date="2026-10-01", start_time="14:00", end_time="16:00", status=value)
            assert isinstance(res.status, int)