# Auto Dev Control Center

Next.js、TypeScript、Tailwind CSS 和 shadcn/ui 构建的 Auto Dev Platform
内部管理控制台。Phase 6.2 使用 Light Professional Workspace 视觉体系，
面向日常任务管理与 Agent 执行审查。

## 本地运行

先在项目根目录启动 FastAPI：

```bash
uv run python backend/main.py
```

再启动控制台：

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

访问 `http://127.0.0.1:3000`。

默认连接 `http://127.0.0.1:8000`。可在 `.env.local` 中修改：

```env
AUTO_DEV_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

浏览器请求通过 Next.js `/api/backend/*` 代理转发到 FastAPI，因此无需修改
FastAPI CORS 或接口设计。

## 页面

- `/`：Dashboard、任务指标、Agent 状态和最近任务
- `/missions`：全部开发任务
- `/agents`：专业角色模板、默认模型能力与实时状态
- `/tasks/new`：创建任务
- `/tasks/[id]`：Overview、Execution、Evidence、Logs、Review五个详情视图
- `/tasks/[id]/control`：暂停、取消和重试
- `/logs`：跨任务结构化执行日志
- `/settings`：只读运行环境状态

创建任务默认使用 `dry_run`，只运行产品交付规划。只有在表单中显式选择
`execute` 才允许 Codex 修改文件并创建 Git commit。任务详情 Overview 会显示
当前 execution mode。

## 验证

```bash
npm test
npm run lint
npm run build
```
