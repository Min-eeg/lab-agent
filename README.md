# Lab Agent — 智能实验室预约管理系统

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3-4FC08D?logo=vuedotjs&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2-1C3C3C?logo=langchain&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-5.7-4479A1?logo=mysql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

一个前后端分离的实验室预约系统：常规的**实验室 / 设备 / 预约 / 审核业务**之上，接入了一个真正能"动手干活"的 **AI 助手**——它不只是问答，而是通过 Tool Calling 直接查库、和用户确认后把预约写进数据库，全过程 SSE 流式可见。

---

## ✨ 功能特性

**学生端**
- 浏览开放中的实验室与设备（图片点击放大，整组翻看）
- 选择时段提交预约、查看我的预约、待审核状态下取消
- 首页角色化引导（我的预约状态统计、快捷入口）

**管理员端**
- 实验室 / 设备 / 用户管理（封面与图片上传）
- 预约审核（通过 / 拒绝），首页动态展示待审核数量
- 过期预约定时扫描，自动取消（FastAPI lifespan + asyncio 后台任务）

**AI 助手（核心亮点）**
- 🔎 **RAG 知识问答**：预约规则、开放时间、安全规范等回答基于本地知识库检索，有据可依
- 🛠 **Tool Calling 落库**：5 个业务工具，LLM 决策直连 MySQL，对话确认后真实生成预约单
- ⚡ **流式全链路**：LangGraph 双 stream_mode → SSE 事件流 → 前端打字机 + 工具过程可视化（"正在查询开放实验室…"）
- 🛡 **防幻觉防护**：时间参数归一化校验、工具失败强制如实回述，杜绝"假成功"
- 💾 **对话持久化**：切页面不断流，刷新后对话仍在（模块级 store + localStorage 按用户隔离）

## 📷 界面预览

<!-- 建议截几张图放到 docs/screenshots/ 后取消注释：
| 首页 | AI 助手 |
| --- | --- |
| ![](docs/screenshots/home.png) | ![](docs/screenshots/ai-chat.png) |
| 实验室管理 | 预约审核 |
| ![](docs/screenshots/lab-admin.png) | ![](docs/screenshots/audit.png) |
-->

## 🏗 系统架构

![系统架构](docs/images/architecture.png)

## 🔁 预约业务

预约主流程（学生提交 → 管理员审核）：

![预约主流程](docs/images/architecture.png)

预约状态机（`0 待审核 / 1 已通过 / 2 已拒绝 / 3 已取消`，待审核状态超时未审核会被定时任务自动取消）：

![预约状态机](docs/images/architecture.png)

## 🤖 AI 助手

AI 能力分五层叠加——从纯对话，到 RAG、Tool Calling、LangGraph Agent，再到 SSE 流式：

![AI 能力叠加](docs/images/architecture.png)

**LangGraph Agent 循环**：有 `tool_calls` 就执行工具并回填结果继续决策，没有则返回文本；`recursion_limit` 防空转：

![LangGraph Agent](docs/images/architecture.png)

**一次典型的对话式预约（端到端）**：

![AI 预约端到端](docs/images/ai-reservation-e2e.png)

**工具集**（按请求动态构建，工具内部复用 Service 层，天然继承鉴权与业务校验）：

| 工具 | 作用 |
| --- | --- |
| `get_today` | 获取服务器当前日期，把"明天"这类相对时间换算成具体日期 |
| `list_open_labs` | 查询开放中的实验室（支持关键词） |
| `list_lab_equipments` | 查询某实验室的设备列表 |
| `search_lab_docs` | RAG 检索知识库（预约规则 / 开放时间 / 安全规范…） |
| `create_lab_reservation` | 创建预约并写入 MySQL（含时段冲突、开放时间、格式校验） |

**Tool Calling 完整时序**：

![Tool Calling](docs/images/architecture.png)

## 📚 RAG 知识库

![RAG 流程](docs/images/architecture.png)

- 知识库为 7 篇主题聚焦的 Markdown（`backend/data/kb/`）：预约规则、预约状态说明、开放时间、安全规范、设备使用、实验室介绍、常见问题
- **按文件粒度入库**：一篇文档 = 一条向量，主题聚焦保证检索精度
- 向量模型 `bge-small-zh-v1.5` **本地化部署**，知识库与 embedding 均可完全离线运行
- 修改 `data/kb/` 下的文档后，删除 `data/chroma/` 重启即可自动重建向量库

## ⚡ 流式输出

![SSE 流式](docs/images/architecture.png)

- 后端：`agent.stream(stream_mode=["messages", "updates"])` —— `messages` 通道取 token 增量，`updates` 通道识别工具节点的开始 / 结束
- 事件协议统一：`status / tool_start / tool_end / token / done / error`
- 前端：fetch 读取 SSE 流手动解析，**对话状态放在组件外的模块级 store**——流式中途切换页面，回复在后台拼完后依然完整保存

## 🧱 技术栈

![技术栈](docs/images/architecture.png)

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3（`<script setup>`）、Element Plus、Vite、Axios + fetch SSE |
| 后端 | FastAPI、SQLAlchemy 2.x、Pydantic v2、PyJWT、python-multipart |
| AI | LangGraph 1.2、LangChain（OpenAI 兼容接口）、ChromaDB、sentence-transformers + bge-small-zh-v1.5 |
| 数据 | MySQL 5.7 |

## 🚀 快速开始

### 环境要求

- Python 3.10+（开发使用 3.13）
- Node.js 18+
- MySQL 5.7+

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

在 `backend/` 下创建 `.env`：

```env
DATABASE_URL=mysql+pymysql://root:你的密码@localhost:3306/lab_agent?charset=utf8mb4
JWT_SECRET_KEY=换成一串随机字符串
JWT_EXPIRE_HOURS=24
JWT_ALGORITHM=HS256
LLM_API_KEY=你的大模型APIKey
LLM_BASE_URL=https://api.example.com/v1
LLM_MODEL=模型名
```

下载 embedding 模型到本地（约 95MB，默认走 ModelScope 镜像，国内网络友好）：

```bash
python scripts/download_model.py
```

首次启动自动建表、构建向量库、开启过期预约扫描任务：

```bash
uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 <http://localhost:5173>。演示账号：`admin / admin`（管理员）、`aaa / 123`（学生）。

## 📁 项目结构

```
lab-agent
├── backend
│   ├── app
│   │   ├── api/            # 路由层：auth / user / lab / equipment / reservation / files / ai
│   │   ├── services/       # 业务层：含 agent_tools（5 个工具）、agent_service（LangGraph 图）、kb_service（RAG）
│   │   ├── models/         # SQLAlchemy 模型
│   │   ├── schemas/        # Pydantic 请求/响应模型
│   │   ├── dependencies/   # 鉴权等通用依赖
│   │   ├── common/         # logger / 统一异常
│   │   └── main.py         # 应用入口（lifespan：建表 + 预热 + 后台扫描任务）
│   ├── data
│   │   ├── kb/             # RAG 知识库（7 篇 Markdown，随仓库提交）
│   │   ├── chroma/         # 向量库（运行时生成，不提交）
│   │   └── models/         # 本地模型（脚本下载，不提交）
│   ├── scripts/download_model.py   # 模型下载脚本（ModelScope 镜像）
│   └── requirements.txt
├── frontend
│   └── src
│       ├── api/            # 接口封装（含 SSE 流式解析）
│       ├── views/          # 页面（AIChat / Home / Lab / LabEquipment / Profile …）
│       ├── layouts/        # 布局与侧边菜单（高亮跟随路由）
│       ├── router/
│       └── utils/          # request 拦截器 / chatStore（组件外对话状态）/ file
└── docs/images/            # README 示意图（scripts/gen_diagrams_png.py 生成）
```

## 💡 工程细节与踩坑记录

这部分是项目里最"值钱"的经验，都做了实测复现与修复：

1. **LLM 传参的字符串比较坑**：模型把时间传成 `"9:00"`，与 `"11:00"` 做字符串比较时 `'9' > '1'`，被误判"结束时间早于开始时间"。修复：入库前统一做日期/时间归一化（兼容 `2026-9-30`、`2026/10/01`、`14:00:00` 等写法），彻底非法输入明确报错。
2. **杜绝"假成功"**：工具调用失败时 LLM 可能无视失败结果谎称"预约好了"。修复：工具返回结构化 `ok / reservation_id`，系统提示词硬约束——`ok:true` 才许说成功且必须报预约单号，`ok:false` 必须如实转述失败原因。
3. **模型本地化**：国内网络访问 huggingface 证书校验失败、hf-mirror 也被限流。修复：下载脚本改走 ModelScope，模型落盘 `data/models/`，启动优先离线加载（`HF_HUB_OFFLINE=1`），换机器一键重下。
4. **流式 API 迁移**：`langchain-core 1.x` 移除了 `stream_events(version="v2")`，迁移到 LangGraph 原生 `stream_mode=["messages","updates"]` 双通道方案；同时踩过 `llm.stream()` 返回生成器被塞进图状态的坑（节点内应使用 `invoke`）。
5. **流式状态与组件生命周期**：对话状态住在组件实例里，切页面即销毁、回复只剩半截。修复：重构为模块级 store 承接流式任务，组件只是视图——切走后流继续跑，切回来还能看到打字机继续输出。

## 🗺 Roadmap

- [ ] Agent 评测集（固定用例批量回归，量化回答质量）
- [ ] 接入 LangSmith 做工具调用链路追踪
- [ ] 对话记录后端持久化（跨设备同步）
- [ ] 核心业务与工具的单元测试 / CI

## 📄 License

[MIT](LICENSE)
