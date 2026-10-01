# -*- coding: utf-8 -*-
"""
生成 README 用的 SVG 示意图，输出到 docs/images/。
仅用标准库，重跑即可重新生成全部图。
"""
import os
from xml.sax.saxutils import escape

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "images")

FONT = "PingFang SC, Microsoft YaHei, Noto Sans SC, sans-serif"
C_TEXT = "#1f2d3d"
C_SUB = "#5a6b7b"
C_LINE = "#607080"
C_SECTION = "#f7f8fa"
C_BLUE = "#d9ecff"
C_BLUE_S = "#2b7fd4"
C_GREEN = "#d8f3e4"
C_GREEN_S = "#1f9e6e"
C_YELLOW = "#ffe9a8"
C_YELLOW_S = "#d99a17"
C_PURPLE = "#e6e0ff"
C_PURPLE_S = "#6f5bd6"


class Svg:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.parts = []
        self.parts.append(
            '<rect width="100%" height="100%" fill="#ffffff"/>'
            '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            '<path d="M 0 0 L 10 5 L 0 10 z" fill="' + C_LINE + '"/></marker></defs>'
        )

    def rect(self, x, y, w, h, fill, stroke, rx=8, sw=1.2):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def text(self, x, y, s, size=14, fill=C_TEXT, anchor="middle", weight="normal"):
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{escape(s)}</text>'
        )

    def box(self, x, y, w, h, lines, fill=C_BLUE, stroke=C_BLUE_S, size=14, weight="normal"):
        self.rect(x, y, w, h, fill, stroke)
        lh = size * 1.45
        y0 = y + h / 2 - (len(lines) - 1) * lh / 2 + size * 0.35
        for i, s in enumerate(lines):
            self.text(x + w / 2, y0 + i * lh, s, size, C_TEXT, "middle", weight)

    def arrow(self, x1, y1, x2, y2, dashed=False, label=None, lsize=13, color=C_LINE, label_dy=-7):
        dash = ' stroke-dasharray="5,4"' if dashed else ""
        self.parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
            f'stroke-width="1.4"{dash} marker-end="url(#ar)"/>'
        )
        if label:
            self.text((x1 + x2) / 2, (y1 + y2) / 2 + label_dy, label, lsize, C_SUB)

    def section(self, x, y, w, h, label=None):
        self.rect(x, y, w, h, C_SECTION, "#e3e7ec", rx=10)
        if label:
            self.text(x + w - 14, y + 22, label, 13.5, C_SUB, "end")

    def cylinder(self, cx, y, w, h, lines, fill=C_BLUE, stroke=C_BLUE_S, size=13, ry=11):
        self.rect(cx - w / 2, y + ry, w, h - 2 * ry, fill, stroke, rx=0, sw=0)
        self.rect(cx - w / 2, y + ry, w, h - 2 * ry, fill, "none", rx=0, sw=0)
        self.parts.append(
            f'<path d="M {cx - w / 2} {y + ry} L {cx - w / 2} {y + h - ry} '
            f'A {w / 2} {ry} 0 0 0 {cx + w / 2} {y + h - ry} L {cx + w / 2} {y + ry}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>'
        )
        self.parts.append(
            f'<ellipse cx="{cx}" cy="{y + ry}" rx="{w / 2}" ry="{ry}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>'
        )
        lh = size * 1.4
        y0 = y + h / 2 - (len(lines) - 1) * lh / 2 + size * 0.35 + ry / 2
        for i, s in enumerate(lines):
            self.text(cx, y0 + i * lh, s, size, C_TEXT)

    def save(self, name):
        path = os.path.join(OUT, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" '
                f'height="{self.h}" viewBox="0 0 {self.w} {self.h}">\n'
                + "\n".join(self.parts)
                + "\n</svg>\n"
            )
        print("生成", os.path.normpath(path))


# ---------------------------------------------------------------- 时序图工具
def sequence(name, actors, msgs, w=980, actor_w=128, actor_h=44, row=50, note=None):
    n = len(actors)
    margin = actor_w / 2 + 28
    gap = (w - 2 * margin) / (n - 1) if n > 1 else 0
    top = 30
    h = top + actor_h + len(msgs) * row + (70 if note else 30) + actor_h
    s = Svg(w, h)
    xs = [margin + i * gap for i in range(n)]

    def actor_row(y):
        for i, a in enumerate(actors):
            s.box(xs[i] - actor_w / 2, y, actor_w, actor_h, [a], size=14)

    actor_row(top)
    bottom = top + actor_h + len(msgs) * row + (70 if note else 30)
    for x in xs:
        s.parts.append(
            f'<line x1="{x}" y1="{top + actor_h}" x2="{x}" y2="{bottom}" '
            f'stroke="#c3ccd6" stroke-width="1.2" stroke-dasharray="4,4"/>'
        )
    y = top + actor_h + row / 2 + 8
    for m in msgs:
        fx, tx, label, dashed = m
        if fx == "L":
            fx_i, tx_i = 0, 1
            x1, x2 = xs[0], xs[0] + 46
        else:
            x1, x2 = xs[fx], xs[tx]
        s.arrow(x1, y, x2, y, dashed=dashed)
        s.text((x1 + x2) / 2, y - 8, label, 13, C_TEXT)
        y += row
    actor_row(bottom)
    if note:
        s.rect(margin - 10, bottom + actor_h + 16, w - 2 * margin + 20, 34, "#fdf6e3", "#e8d49a", rx=6)
        s.text(w / 2, bottom + actor_h + 38, note, 13, "#7a5b12")
    s.save(name)
    return xs


# 1. 系统架构 ---------------------------------------------------------------
s = Svg(960, 580)
s.section(280, 16, 660, 128, "前端")
s.box(400, 48, 420, 76, ["页面：登录 / 首页 / 实验室 / 设备 / 预约 / AI 助手", "（图片点击预览 · 对话本地持久化 · 打字机输出）"], size=14)

s.section(280, 190, 660, 196, "后端 FastAPI")
s.box(310, 226, 250, 62, ["AI API", "/api/ai/chat · /chat/stream"], size=13.5)
s.box(600, 226, 310, 62, ["业务 API", "auth / user / lab / equipment / reservation / files"], size=13.5)
s.box(430, 316, 340, 52, ["Service 层（业务逻辑 + Agent 工具实现）"], size=13.5)
s.arrow(435, 288, 530, 314)
s.arrow(755, 288, 670, 314)

s.section(16, 246, 236, 116, "外部模型")
s.box(36, 288, 196, 56, ["大模型 API", "OpenAI 兼容接口"], size=13.5)
s.arrow(310, 257, 200, 300, label="LLM 调用", label_dy=-10)

s.section(280, 430, 660, 134, "数据层")
s.cylinder(390, 456, 170, 92, ["MySQL", "用户/实验室/设备/预约"])
s.cylinder(590, 456, 170, 92, ["ChromaDB", "知识库向量"])
s.box(690, 470, 230, 66, ["本地模型目录 data/models", "bge-small-zh-v1.5 离线加载"], fill=C_GREEN, stroke=C_GREEN_S, size=13)
s.arrow(520, 368, 420, 452)
s.arrow(600, 368, 590, 452, dashed=True)
s.arrow(720, 368, 780, 466, dashed=True)
s.save("architecture.svg")

# 2. 预约主流程 -------------------------------------------------------------
sequence(
    "reservation-flow.svg",
    ["学生", "前端 Vue3", "FastAPI", "MySQL", "管理员"],
    [
        (0, 1, "选实验室 / 时段", False),
        (1, 2, "创建预约", False),
        (2, 3, "校验冲突并写入 status=0", False),
        (2, 1, "待审核（页面提示）", True),
        (4, 1, "打开预约审核页", False),
        (1, 2, "同意 / 拒绝", False),
        (2, 3, "更新状态", False),
        (2, 1, "审核完成（通知学生）", True),
    ],
    note="另有定时任务扫描过期预约：到了预约开始时间仍是待审核 → 自动取消",
)

# 3. 预约状态机 -------------------------------------------------------------
s = Svg(780, 440)
s.parts.append('<circle cx="390" cy="36" r="9" fill="#4a5568"/>')
s.arrow(390, 45, 390, 82)
s.text(452, 70, "学生提交", 13.5, C_SUB)
s.box(310, 86, 160, 54, ["待审核 status=0"], fill=C_YELLOW, stroke=C_YELLOW_S, weight="bold")
bx, by, bw, bh = 100, 250, 170, 54
s.box(bx, by, bw, bh, ["已通过 status=1"], fill=C_GREEN, stroke=C_GREEN_S)
s.box(bx + 215, by, bw, bh, ["已拒绝 status=2"])
s.box(bx + 430, by, bw, bh, ["已取消 status=3"])
s.arrow(330, 140, 190, 246, label="管理员同意", label_dy=-8)
s.arrow(390, 140, 385, 246, label="管理员拒绝", label_dy=22)
s.arrow(450, 140, 590, 246, label="学生取消（仅待审核可取消）", label_dy=-8)
s.arrow(450, 140, 605, 246, dashed=True)
s.text(640, 176, "过期未开始", 12.5, C_SUB)
s.text(640, 193, "定时任务自动取消", 12.5, C_SUB)
s.parts.append('<circle cx="390" cy="380" r="10" fill="none" stroke="#4a5568" stroke-width="2"/>')
s.parts.append('<circle cx="390" cy="380" r="4.5" fill="#4a5568"/>')
for x in (185, 400, 615):
    s.arrow(x, 304, 390 if abs(x - 390) > 5 else 390, 366)
s.save("reservation-state.svg")

# 4. AI 能力叠加 ------------------------------------------------------------
s = Svg(760, 640)
steps = [
    ("用户提问", "#eef2f7", "#8a97a6"),
    ("① 基础对话：直连大模型", C_BLUE, C_BLUE_S),
    ("② + RAG：检索知识库再回答", C_GREEN, C_GREEN_S),
    ("③ + Tool Calling：查 MySQL / 写预约", C_PURPLE, C_PURPLE_S),
    ("④ LangGraph Agent：agent ⇄ tools 循环", C_YELLOW, C_YELLOW_S),
    ("⑤ SSE 流式：过程可见 · 逐字输出", C_YELLOW, C_YELLOW_S),
]
y = 26
for i, (t, f, st) in enumerate(steps):
    s.box(160, y, 440, 62, [t], fill=f, stroke=st, size=15)
    if i < len(steps) - 1:
        s.arrow(380, y + 62, 380, y + 96)
    y += 100
s.save("ai-layers.svg")

# 5. RAG 流程 ---------------------------------------------------------------
s = Svg(980, 420)
s.section(40, 230, 900, 150, "入库（离线 · 一次性）")
s.box(80, 280, 210, 66, ["Markdown 知识库", "预约规则/开放时间/安全规范 等 7 篇"], size=13)
s.box(370, 280, 210, 66, ["bge-small-zh-v1.5", "本地向量化（离线）"], size=13)
s.cylinder(720, 280, 200, 78, ["ChromaDB Collection"])
s.arrow(290, 313, 366, 313)
s.arrow(580, 313, 616, 313)
s.section(40, 30, 900, 160, "提问（在线 · 每次对话）")
s.box(80, 78, 180, 62, ["用户问题"], size=14)
s.box(320, 78, 180, 62, ["向量化"], size=14)
s.box(560, 78, 170, 62, ["相似检索 Top-K"], size=14)
s.box(760, 78, 150, 62, ["大模型回答"], fill=C_GREEN, stroke=C_GREEN_S, size=14)
s.arrow(260, 109, 316, 109)
s.arrow(500, 109, 556, 109)
s.arrow(730, 109, 756, 109)
s.arrow(560, 150, 700, 285, dashed=True, label="命中相关文档", label_dy=-8)
s.arrow(645, 140, 800, 152, dashed=True, label="注入 Prompt", label_dy=-6)
s.rect(60, 396, 860, 4, "#e3e7ec", "none", rx=2)
s.text(490, 414, "要点：开放时间、安全规范这类回答以检索到的文档为准，而不是靠模型自由发挥。", 13.5, "#7a5b12")
s.save("rag-flow.svg")

# 6. Tool Calling 时序 ------------------------------------------------------
sequence(
    "tool-calling.svg",
    ["用户", "后端 FastAPI", "大模型", "MySQL"],
    [
        (0, 1, "现在有哪些开放的实验室？", False),
        (1, 2, "messages + tools 定义", False),
        (2, 1, "tool_calls: list_open_labs", True),
        (1, 3, "lab_service 查询 status=1", False),
        (3, 1, "实验室列表 JSON", True),
        (1, 2, "工具结果塞回 messages", False),
        (2, 1, "自然语言回答", True),
        (1, 0, "最终回复", True),
    ],
)

# 7. LangGraph Agent 循环 ---------------------------------------------------
s = Svg(980, 440)
s.box(430, 24, 120, 46, ["START"], fill="#eef2f7", stroke="#8a97a6")
s.arrow(490, 70, 490, 108)
s.parts.append(
    f'<polygon points="490,112 640,196 490,280 340,196" fill="{C_YELLOW}" '
    f'stroke="{C_YELLOW_S}" stroke-width="1.4"/>'
)
s.text(490, 202, "agent 调用大模型", 15, C_TEXT, "middle", "bold")
s.box(200, 320, 220, 58, ["tools 执行工具"], fill=C_PURPLE, stroke=C_PURPLE_S, size=15)
s.box(610, 322, 220, 54, ["END 返回文本"], fill=C_GREEN, stroke=C_GREEN_S, size=15)
s.arrow(400, 262, 300, 316, label="有 tool_calls", label_dy=-8)
s.arrow(585, 262, 700, 318, label="没有 tool_calls", label_dy=-8)
s.arrow(230, 316, 420, 268)
s.text(268, 286, "工具结果回填 messages", 12.5, C_SUB)
s.rect(700, 60, 264, 190, C_SECTION, "#e3e7ec", rx=10)
s.text(832, 88, "工具集（5 个）", 14, C_TEXT, "middle", "bold")
tools = ["get_today 换算今天/明天", "list_open_labs 查开放实验室", "list_lab_equipments 查设备",
         "search_lab_docs 检索知识库", "create_lab_reservation 写预约落库"]
for i, t in enumerate(tools):
    s.text(716, 120 + i * 26, "· " + t, 12.5, C_SUB, "start")
s.rect(60, 330, 560, 60, "#fdf6e3", "#e8d49a", rx=8)
s.text(340, 355, "recursion_limit 限制 agent ⇄ tools 来回次数，防止模型空转；", 13, "#7a5b12")
s.text(340, 376, "工具失败返回 ok:false，系统提示词要求模型如实转述，禁止谎报成功", 13, "#7a5b12")
s.save("langgraph-agent.svg")

# 8. SSE 流式时序 -----------------------------------------------------------
sequence(
    "sse-flow.svg",
    ["前端 fetch 流解析", "FastAPI StreamingResponse", "LangGraph"],
    [
        (0, 1, "POST /api/ai/chat/stream", False),
        (1, 2, "agent.stream(stream_mode=[messages, updates])", False),
        (2, 1, "工具节点更新（updates 通道）", True),
        (1, 0, "data: {type: tool_start/tool_end} → 显示「正在查询开放实验室…」", True),
        (2, 1, "token 增量（messages 通道 AIMessageChunk）", True),
        (1, 0, "data: {type: token} → 气泡逐字追加", True),
        (2, 1, "图执行结束", True),
        (1, 0, "data: {type: done}", True),
    ],
    w=1080,
    note="前端事件结构统一为 status / tool_start / tool_end / token / done / error，组件外的模块级 store 承接流，切页面不断流",
)

# 9. 技术栈速览 -------------------------------------------------------------
s = Svg(1000, 330)
s.section(24, 40, 250, 150, "前端")
s.box(48, 78, 90, 44, ["Vue3"], size=13.5)
s.box(146, 78, 104, 44, ["Element Plus"], size=13)
s.box(48, 132, 90, 44, ["Vite"], size=13.5)
s.box(146, 132, 104, 44, ["Axios/SSE"], size=13)
s.section(300, 40, 420, 150, "后端")
s.box(322, 78, 100, 44, ["FastAPI"], size=13.5)
s.box(430, 78, 120, 44, ["SQLAlchemy"], size=13.5)
s.box(558, 78, 140, 44, ["LangGraph 1.2"], size=13.5)
s.box(322, 132, 120, 44, ["Pydantic v2"], size=13.5)
s.box(450, 132, 130, 44, ["LangChain"], size=13.5)
s.box(588, 132, 110, 44, ["ChromaDB"], size=13.5)
s.section(748, 40, 228, 150, "数据 / 模型")
s.box(770, 74, 90, 44, ["MySQL"], size=13.5)
s.box(868, 74, 90, 44, ["向量库"], size=13.5)
s.box(770, 128, 90, 44, ["bge 本地", "模型"], fill=C_GREEN, stroke=C_GREEN_S, size=12.5)
s.box(868, 128, 90, 44, ["大模型", "API"], fill=C_YELLOW, stroke=C_YELLOW_S, size=12.5)
s.arrow(274, 115, 296, 115)
s.arrow(720, 115, 744, 115)
s.save("tech-stack.svg")

# 10. 一次 AI 预约端到端 ----------------------------------------------------
s = Svg(660, 760)
flow = [
    ("用户：帮我预约明天下午的计算机实验室", C_BLUE, C_BLUE_S),
    ("SSE 连接建立（POST /api/ai/chat/stream）", "#eef2f7", "#8a97a6"),
    ("status: 正在思考…", "#eef2f7", "#8a97a6"),
    ("tool: get_today —— 把「明天」换算成日期", C_PURPLE, C_PURPLE_S),
    ("tool: list_open_labs —— 找开放的实验室", C_PURPLE, C_PURPLE_S),
    ("可选 tool: search_lab_docs —— 检索预约规则", C_GREEN, C_GREEN_S),
    ("token: 复述 lab_id / 日期 / 时段，请用户确认", C_YELLOW, C_YELLOW_S),
    ("用户回复：确认预约", C_BLUE, C_BLUE_S),
    ("tool: create_lab_reservation —— 参数规范化 + 校验后落库", C_PURPLE, C_PURPLE_S),
]
y = 26
for i, (t, f, st) in enumerate(flow):
    lines = [t] if len(t) <= 26 else None
    s.box(90, y, 480, 52, [t], fill=f, stroke=st, size=13.5)
    if i < len(flow) - 1:
        s.arrow(330, y + 52, 330, y + 78)
    y += 78
s.box(70, y + 10, 250, 58, ["MySQL：新预约 status=0", "（待审核，可在我的预约中查看）"], fill=C_GREEN, stroke=C_GREEN_S, size=12.5)
s.box(340, y + 10, 250, 58, ["回复用户：已提交", "（如实报告预约单号 / 失败原因）"], fill=C_GREEN, stroke=C_GREEN_S, size=12.5)
s.arrow(250, y - 4, 200, y + 6)
s.arrow(410, y - 4, 460, y + 6)
s.save("ai-reservation-e2e.svg")

print("全部完成")
