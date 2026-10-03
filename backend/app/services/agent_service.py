from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, AIMessageChunk
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from collections.abc import Iterator
from datetime import datetime
from typing import Any
from app.common.exceptions import BusinessException
from app.models.user import User
from app.schemas.ai import ChatRequest
from app.services import agent_tools
from app.config import settings
import traceback

SYSTEM_PROMPT_TEMPLATE = """你是智能实验室预约系统的 Agent，回答要简洁。
你可以：
1. 使用 search_lab_docs 查询实验室的规则、安全、开放时间等问题
2. 使用 list_open_labs / list_lab_equipments  查询真实的实验室和设备
3. 再用户进行了预约确认后，使用 create_lab_reservation 来进行真实的预约落库
4. 使用 get_today 来进行日期的换算

## 当前时间
今天是 {today}（{weekday}），当前时间约 {now}。
**所有日期换算都以这个日期为准**，不要凭记忆猜测今天的日期。
"明天" = {today} 的后一天，"后天" = {today} 的后两天，以此类推。
如果仍然需要确认日期，可以调用 get_today 复核。

## 必须遵守
当用户提到了 今天、明天、后天 等日期相关的问题，请先调用 get_today 来获取日期，**不要直接返回 我需要确定明天的具体日期**。

在提交预约之前必须向用户复述：实验室ID与名称（或设备ID和名称）、日期、开始时间、结束时间。并得到用户确认再进行实际操作。
用户没说【确认】【确认预约】【就这样预约】等确定性回复之前，不要调用 create_lab_reservation。
工作流的确认环节里如果缺少了 lab_id，请先 list_open_labs 查到了 lab_id 再创建，不要瞎写。
工作流的确认环节里如果缺少了 equipment_id，请先 list_lab_equipments 查到了 equipment_id 再创建，不要瞎写。

**用户回复【确认】后要立刻调用 create_lab_reservation**：直接复用你上一条消息里复述给用户的
实验室ID、日期、开始时间、结束时间，不要重新推算日期、不要重新查询、再向用户确认一次。
这是最容易出错的一步：一旦重新推算日期，模型常会算错成过去的日期，导致预约被判为过期而失败。

**确认轮禁止过度澄清（重要）**：用户回复【确认】时，若你上一条消息里已经给出过具体的
实验室ID/名称和日期时间，就必须直接调用 create_lab_reservation 提交。
绝对不要再列一遍实验室清单问"您想预约哪一个"——用户已经确认过了，再问一次就是没完没了。
只有当上一条消息里**确实没有**具体实验室（用户从头到尾没说想约哪间）时，才允许反问。

## 必须检索的问题（禁止凭记忆回答）
以下问题必须先调用 search_lab_docs 检索知识库，再依据检索结果回答，**不允许直接凭印象作答**：
- 预约规则：能不能取消、怎么取消、已通过的预约能否取消、预约要等多久
- 开放时间：某实验室几点开、几点关、周末开不开
- 安全规范：实验室有什么注意事项、某类设备能不能用、怎么操作
- 设备使用：怎么登记、能不能预约大型设备、有没有培训要求
- 账号与角色：学生和管理员有什么区别
知识库是唯一事实来源。即使你"知道"答案，也必须检索后再回答——
你的记忆可能过时，而知识库与系统真实行为保持一致（检索结果里会明确写出实际规则）。

## 工具使用纪律
- **同一个工具在一次回复里最多调用一次**。查过一次开放实验室列表就拿到全部信息了，
  不要换个说法再查一遍——重复调用会空转耗尽轮次上限。
- 已经从工具结果里拿到的信息，直接用它来回答或创建预约，不要为了"再确认一次"重复调工具。
- 一次回复里最多做一件事：要么查资料回答用户，要么提交预约，不要既查又提交又再查。

预约成功后状态是待审核，必须管理员确认后实验室（或设备）才能使用。
调用 create_lab_reservation 后，必须以工具返回的 JSON 为准：
- ok 为 true 才可以说预约成功，并把返回的 reservation_id（预约单号）告诉用户
- ok 为 false 时必须如实告知用户预约失败及 error 中的原因，**绝对禁止说预约成功或预约好了**
传入 create_lab_reservation 的日期格式为 YYYY-MM-DD（如 2026-09-30），时间格式为 HH:MM 24小时制（如 09:00）。
不要瞎编数据库里没有的实验室或者设备信息。
如果是问开放时间或者实验室规则，优先调用 search_lab_docs，不要凭空回复。
"""

_WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def build_system_prompt() -> str:
    """把服务器真实日期注入提示词。

    实测教训: 不注入时模型在"确认"这一轮会凭记忆编造今天的日期
    (它以为是 2026-09-21), 把 10-03 的预约判成过期, 预约直接失败。
    """
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    return SYSTEM_PROMPT_TEMPLATE.format(
        today=today,
        weekday=_WEEKDAYS[now.weekday()],
        now=now.strftime("%H:%M"),
    )

# 工具英文名 → 页面上给人看的中文过程文案
TOOL_LABELS = {
    "search_lab_docs": "检索实验室知识库",
    "list_open_labs": "查询开放实验室",
    "list_lab_equipments": "查询实验室设备",
    "create_lab_reservation": "提交预约",
    "get_today": "获取今天日期",
}


def _chunk_text(chunk: Any) -> str:
    """从模型流式 chunk 里抠出纯文本。

    content 有时是 str，有时是 [{type, text}, ...] 这种块列表，要统一成字符串。
    """
    if chunk is None:
        return ""
    # chunk 可能是 AIMessageChunk，真正字在 .content
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text") or "")
            elif isinstance(part, str):
                parts.append(part)
        return "".join(parts)
    return str(content) if content is not None else ""


def _tool_output_preview(output: Any, limit: int = 200) -> str:
    """把工具结果收成短预览，避免整段 JSON 刷到前端过程区。"""
    # LangGraph 里工具结果经常是 ToolMessage，正文在 .content
    content = getattr(output, "content", output)
    text = content if isinstance(content, str) else str(content)
    # 太长就截断，末尾加省略号
    return text if len(text) <= limit else text[:limit] + "…"


def _build_history(data: ChatRequest) -> list:
    """前端只传 user/assistant 文本，转成 LangChain 消息对象。"""
    history = []
    for message in data.messages or []:
        if message.role == "user" and message.content.strip():
            history.append(HumanMessage(content=message.content.strip()))
        elif message.role == "assistant" and message.content.strip():
            history.append(AIMessage(content=message.content.strip()))
    if not history:
        raise BusinessException(message="请输入您要对话的内容")
    return history


def stream_agent(
    db: Session, current_user: User, data: ChatRequest, dry_run: bool = False
) -> Iterator[dict]:
    """生成器：边跑 Agent 边 yield 事件，供 SSE 推给前端。

    事件类型：status / tool_start / tool_end / token / done / error
    dry_run=True 时预约工具只校验不落库（评测集批量回归用）
    """
    try:
        history = _build_history(data)
        agent = build_agent(db, current_user, dry_run=dry_run)
        # *history：把列表拆开，和 SystemMessage 拼成完整 messages
        inputs = {"messages": [SystemMessage(content=build_system_prompt()), *history]}

        # yield = 先交出这一条，函数暂停；前端收到后再继续往下跑
        yield {"type": "status", "message": "正在思考…"}

        # langgraph 原生双流: messages 给逐字 token, updates 给节点级事件(工具开始/结束)
        # 注: langchain-core 1.x 已移除 stream_events(v2), 不要再用
        for mode, chunk in agent.stream(
            inputs,
            config={
                "recursion_limit": 15,  # agent⇄tools 来回上限，防空转(10 在多工具场景下偶发不够)
                # LangSmith 链路标签：在平台上按这些字段筛选/检索某次对话
                "metadata": {
                    "user_id": current_user.id,
                    "username": current_user.username,
                    "mode": "stream",
                },
                "run_name": "agent_booking_stream",
            },
            stream_mode=["messages", "updates"],
        ):
            if mode == "messages":
                # chunk = (消息增量, 元数据)；工具结果(ToolMessageChunk)跳过，只吐模型正文
                msg_chunk, _meta = chunk
                if isinstance(msg_chunk, AIMessageChunk):
                    text = _chunk_text(msg_chunk)
                    if text:
                        yield {"type": "token", "content": text}
            elif mode == "updates":
                # chunk = {节点名: 该节点产出的消息列表}
                for node, update in (chunk or {}).items():
                    new_msgs = (update or {}).get("messages") or []
                    for msg in new_msgs:
                        if node == "agent":
                            # agent 节点产出的 AIMessage 带 tool_calls = 它决定要调工具
                            for call in (getattr(msg, "tool_calls", None) or []):
                                name = call.get("name") or ""
                                yield {
                                    "type": "tool_start",
                                    "name": name,
                                    "label": TOOL_LABELS.get(name, name),  # 没有中文映射就退回英文名
                                }
                        elif node == "tools":
                            # tools 节点产出 ToolMessage = 工具执行完毕
                            name = getattr(msg, "name", "") or ""
                            yield {
                                "type": "tool_end",
                                "name": name,
                                "label": TOOL_LABELS.get(name, name),
                                # 只给预览；完整结果仍在图内部 messages 里给模型用
                                "preview": _tool_output_preview(msg),
                            }

        # 正常跑完：不要在 done 里再带一份全文，前端已经用 token 拼好了
        yield {"type": "done"}
    except BusinessException as exc:
        # 流已经是 SSE，错误也要用 yield，别 raise 成普通 JSON
        yield {"type": "error", "message": exc.message}
    except Exception:
        traceback.print_exc()
        yield {"type": "error", "message": "大模型调用失败，请稍后重试"}


def build_agent(db: Session, current_user: User, dry_run: bool = False):
    # dry_run: 评测模式, create_lab_reservation 只校验不落库
    tools = agent_tools.build_tools(db, current_user, dry_run=dry_run)
    llm = ChatOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        temperature=0,
        streaming=True,
    ).bind_tools(tools)

    def agent_node(state: MessagesState):
        """langGraph 执行的工作流 的节点

        必须用 invoke：返回完整的 AIMessage 才能进 state。
        llm.stream() 返回的是生成器, 塞进 state 会报
        NotImplementedError: Unsupported message type: <class 'generator'>。
        逐字流式靠 llm(streaming=True) + stream_events 的 on_chat_model_stream 事件。
        """
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)  # 调用大模型的节点
    graph.add_node("tools", ToolNode(tools))  # tool call的节点
    graph.add_edge(START, "agent")  # 流程的起点，call LLM
    graph.add_conditional_edges(
        "agent", tools_condition
    )  # 看有无 tool_call  有就继续call  没有就END 输出
    graph.add_edge("tools", "agent")  # 让agent看tool调用的结果
    return graph.compile()


def run_agent(db: Session, current_user: User, data: ChatRequest):
    """大模型对话"""
    if not data.messages:
        raise BusinessException(message="对话内容为空")
    history = []
    for message in data.messages:
        if message.role == "user" and message.content.strip():
            history.append(HumanMessage(content=message.content.strip()))
        elif message.role == "assistant" and message.content.strip():
            history.append(AIMessage(content=message.content.strip()))
    if not history:
        raise BusinessException(message="请输入您要对话的内容")

    agent = build_agent(db, current_user)
    try:
        result = agent.invoke(
            {"messages": [SystemMessage(content=build_system_prompt()), *history]},
            config={
                "recursion_limit": 15,
                # LangSmith 链路标签：在平台上按这些字段筛选/检索某次对话
                "metadata": {"user_id": current_user.id, "username": current_user.username},
                "run_name": "agent_booking",
            },
        )  # 设置对话循环的上限是10轮
    except BusinessException:
        raise
    except Exception:
        raise BusinessException(message="大模型调用失败，请稍后重试")

    messages = result.get("messages") or []
    if not messages:
        raise BusinessException(message="大模型没有任何返回内容")
    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.content.strip():
            content = message.content.strip()
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            if str(content).strip():
                return str(content).strip()
