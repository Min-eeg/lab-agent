# -*- coding: utf-8 -*-
"""对话记录持久化的单元测试（SQLite 内存库，不碰 MySQL、不调大模型）。

重点锁定这些行为契约：
1. 落库时机——只有完整问答（两边都非空）才入库，流式失败不留垃圾历史
2. 每个用户只有「最近一个活跃会话」，多轮问答进同一会话
3. 用户之间严格隔离（跨设备同步的前提是各看各的）
4. 清空对话时消息级联删除，且不影响其他用户
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
import app.models.user  # noqa: F401  users 表是 chat_sessions 的外键目标，必须先注册
from app.models.chat import ChatMessage, ChatSession
from app.services import chat_service


@pytest.fixture()
def db():
    """每个用例一个独立的内存库，跑完即弃。"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


class Msg:
    """ChatRequest 里消息对象的最小替身（pydantic ChatMessage 同构）"""

    def __init__(self, role, content):
        self.role = role
        self.content = content


# ---------- append_round ----------

def test_first_round_creates_session(db):
    session_id = chat_service.append_round(db, user_id=1, user_text="明天有什么实验室", assistant_text="有A和B")
    assert session_id is not None
    session = db.query(ChatSession).filter(ChatSession.user_id == 1).one()
    assert session.id == session_id
    assert session.title == "明天有什么实验室"
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).all()
    assert [(m.role, m.content) for m in messages] == [
        ("user", "明天有什么实验室"),
        ("assistant", "有A和B"),
    ]


def test_second_round_reuses_same_session(db):
    first = chat_service.append_round(db, 1, "问题一", "回答一")
    second = chat_service.append_round(db, 1, "问题二", "回答二")
    assert first == second
    assert db.query(ChatSession).filter(ChatSession.user_id == 1).count() == 1
    assert db.query(ChatMessage).filter(ChatMessage.session_id == first).count() == 4


def test_title_truncated_to_20_chars(db):
    long_question = "这是一条特别特别长的用户提问" * 5  # 50 字
    chat_service.append_round(db, 1, long_question, "回答")
    session = db.query(ChatSession).filter(ChatSession.user_id == 1).one()
    assert session.title == long_question[:20]
    assert len(session.title) == 20


def test_empty_side_never_persisted(db):
    """流式失败/空回答时不得落库——这是「done 才存」契约的底线。"""
    assert chat_service.append_round(db, 1, "", "回答") is None
    assert chat_service.append_round(db, 1, "问题", "") is None
    assert chat_service.append_round(db, 1, "   ", "回答") is None
    assert db.query(ChatSession).count() == 0
    assert db.query(ChatMessage).count() == 0


# ---------- get_history ----------

def test_get_history_empty_for_new_user(db):
    assert chat_service.get_history(db, 99) == {
        "session_id": None,
        "title": None,
        "messages": [],
    }


def test_get_history_returns_messages_in_order(db):
    chat_service.append_round(db, 1, "问题一", "回答一")
    chat_service.append_round(db, 1, "问题二", "回答二")
    history = chat_service.get_history(db, 1)
    assert history["title"] == "问题一"
    assert [m["role"] for m in history["messages"]] == [
        "user", "assistant", "user", "assistant",
    ]
    # 只含 role/content，不带数据库内部字段
    assert set(history["messages"][0].keys()) == {"role", "content"}


def test_users_are_isolated(db):
    """跨设备同步的前提：各看各的记录，绝不能串号。"""
    chat_service.append_round(db, 1, "用户一的问题", "给用户一的回答")
    chat_service.append_round(db, 2, "用户二的问题", "给用户二的回答")
    history1 = chat_service.get_history(db, 1)
    history2 = chat_service.get_history(db, 2)
    assert history1["session_id"] != history2["session_id"]
    assert history1["messages"][0]["content"] == "用户一的问题"
    assert history2["messages"][0]["content"] == "用户二的问题"


# ---------- clear_history ----------

def test_clear_history_cascades_messages(db):
    chat_service.append_round(db, 1, "问题一", "回答一")
    chat_service.append_round(db, 1, "问题二", "回答二")
    assert chat_service.clear_history(db, 1) == 1
    assert db.query(ChatSession).count() == 0
    assert db.query(ChatMessage).count() == 0
    # 清空后可以重新开始一段全新会话
    new_id = chat_service.append_round(db, 1, "新问题", "新回答")
    assert chat_service.get_history(db, 1)["session_id"] == new_id


def test_clear_history_only_affects_self(db):
    chat_service.append_round(db, 1, "用户一", "回答一")
    chat_service.append_round(db, 2, "用户二", "回答二")
    chat_service.clear_history(db, 1)
    assert chat_service.get_history(db, 1)["messages"] == []
    assert len(chat_service.get_history(db, 2)["messages"]) == 2


def test_clear_history_when_empty_is_noop(db):
    assert chat_service.clear_history(db, 99) == 0


# ---------- extract_user_question ----------

def test_extract_last_user_message(db):
    messages = [
        Msg("user", "第一问"),
        Msg("assistant", "第一答"),
        Msg("user", "第二问"),
    ]
    assert chat_service.extract_user_question(messages) == "第二问"


def test_extract_skips_blank_and_non_user(db):
    messages = [Msg("user", "有效问题"), Msg("user", "   "), Msg("assistant", "答")]
    assert chat_service.extract_user_question(messages) == "有效问题"


def test_extract_returns_empty_when_no_user_message(db):
    assert chat_service.extract_user_question([Msg("assistant", "答")]) == ""
    assert chat_service.extract_user_question([]) == ""
    assert chat_service.extract_user_question(None) == ""
