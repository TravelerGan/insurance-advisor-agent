# 安心保 · 保险条款问答助手

一个面向保险条款咨询的 AI 应用课程实践。用户可以浏览示例产品、发起多轮咨询。FastAPI 用 SSE 返回对话事件，LangGraph 根据意图把请求交给闲聊或保险顾问，并用 PostgreSQL 按会话保存状态。

## 试一试

启动后在顾问页问「示例住院医疗险的等待期是多少天？」再问「这个产品的年度免赔额是多少？」。仓库提供一份自编的虚构产品条款，便于对照回答和资料。

| 环节 | 实现 |
| --- | --- |
| 意图路由 | LangGraph 路由节点返回业务分支，顾问可以调用查询产品、检索条款和保存方案等工具。 |
| 条款入库 | 原流程由 MinerU 处理 PDF。仓库样例直接使用 Markdown，按标题切父块，再切较小的子块。 |
| 条款召回 | Milvus 按产品筛选并召回子块，结合重排定位结果，再用父块 ID 从 PostgreSQL 取完整上下文。 |
| 会话与接口 | FastAPI 提供商品列表、会话管理和流式聊天。PostgreSQL 保存会话信息和 LangGraph checkpoint。 |

## 本地运行

准备 Docker Compose、uv、Python 3.14 和 Node.js 22 或更新版本。配置 DeepSeek 对话密钥和 DashScope 向量化与重排密钥。

```bash
cp agent-service/.env.example agent-service/.env
cp deploy/milvus/user.example.yaml deploy/milvus/user.yaml
```

在 `agent-service/.env` 填写 `DEEPSEEK_API_KEY` 和 `DASHSCOPE_API_KEY`。把同一个 DashScope 密钥填入 `deploy/milvus/user.yaml` 的 `apikey` 字段。接入自己的 PDF 时，再配置 `MINERU_TOKEN`。

```bash
docker compose -f deploy/docker-compose.yml up -d --wait postgres milvus
cd agent-service
uv sync --locked
uv run --locked python scripts/ingest_rag.py
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8001
```

另开终端，从仓库根目录启动前端。

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

打开 [演示页面](http://127.0.0.1:5173) 或 [Swagger](http://127.0.0.1:8001/docs)。网页使用固定的本地演示身份。直接调用 API 时，先向 `POST /api/v1/chat-threads` 发送 `{"title":"条款咨询"}` 并带上 `x-user-id: 1`，再把返回的会话 ID 和问题提交到 `POST /api/v1/chat`。

## 项目结构

- `agent-service/app/agents/` 存放意图路由、顾问 Agent 和工具。
- `agent-service/app/rag/` 存放条款切分、索引和父块检索。
- `agent-service/app/modules/` 存放商品、会话、聊天和方案模块。
- `frontend/` 是 React + Vite 演示界面，`deploy/` 提供本地依赖及数据库初始化脚本。

后端分页回归检查可在填写配置后运行 `uv run --locked python -m unittest discover -s tests -v`，测试使用内存 SQLite 和模拟服务。前端可用 `npm run build` 验证构建。

项目源于 FastAPI + LangGraph 保险助手课程实践。示例产品与条款均为虚构。理赔和转人工分支为演示占位，登录使用本地演示身份。
