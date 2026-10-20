<!-- SVENKUNKKA-README-NAV:BEGIN -->
[中文项目说明](#project-overview-zh) · [English overview](#project-overview-en) · [维护者 X / Maintainer on X](https://x.com/Svenu1s5)
<!-- SVENKUNKKA-README-NAV:END -->

# Auto Dev Platform v1.6

## English Overview

Auto Dev Platform is a local-first task management workspace for coordinating AI-assisted software development. It combines FastAPI, SQLite, an agent runtime, and CrewAI to move a task through five isolated roles: Requirement Analyst, Supervisor, Developer, Verification Engineer, and Acceptance Reviewer.

The platform supports API-based task submission, persistent task state, structured execution logs, health checks, a Next.js dashboard, controlled rework loops, workspace locking, and Git-based evidence. Codex CLI and Claude Code integrations are optional and disabled by default. A `dry_run` / `execute` switch provides an additional safety boundary before an agent is allowed to make changes.

> **Security:** The dashboard is intended for trusted local users. It has no login or multi-user authorization layer, so bind it only to `127.0.0.1` and never expose it directly to the public internet. Keep API keys in local environment files and do not commit secrets.

Quick start:

```bash
git clone https://github.com/SvenKunkka/auto-dev-team.git
cd auto-dev-team
cp .env.example .env
uv sync
uv run python backend/main.py
```

Start the dashboard from `frontend/` with `npm ci && npm run dev`, then open `http://127.0.0.1:3000`.

Auto Dev Platform 是一个基于 FastAPI、SQLite、Agent Runtime 和 CrewAI 的
AI 开发任务管理平台基础版本。

> 安全提示：Dashboard 默认面向可信的本机用户，不包含登录与多用户权限。
> 请只绑定到 `127.0.0.1`，不要直接暴露到公网。

## 快速开始

```bash
git clone https://github.com/SvenKunkka/auto-dev-team.git
cd auto-dev-team
cp .env.example .env
uv sync
uv run python backend/main.py
```

另开一个终端启动 Dashboard：

```bash
cd auto-dev-team/frontend
cp .env.example .env.local
npm ci
npm run dev
```

浏览器访问 `http://127.0.0.1:3000`。不启用真实 Agent 时可保留示例密钥，
并让 `CODEX_ENABLED` 与 `CLAUDE_ENABLED` 维持 `false`。

Phase 1 支持通过 API 提交任务、持久化任务状态。当前执行链已扩展为
Requirement Analyst、Supervisor、Developer、Verification Engineer 和
Acceptance Reviewer 五个隔离角色。Phase 2 为 Developer Runtime 增加了
可选的 Codex CLI 执行模式，Phase 3 为 Reviewer Runtime 增加了可选的
Claude Code只读验收模式。Phase 4.1 增加 Supervisor Decision 和有限返工循环。
Phase 4.2 增加单机恢复、超时和工作区锁。原有 `crewai run` 入口继续保留。
Phase 4.3 增加单进程 Task Worker、周期心跳和优雅关闭。
Phase 5 增加持久化执行日志、健康检查、任务详情和人工控制 API。
Phase 6.1 增加 Next.js 内部 Web Dashboard。
Phase 6.2 将控制台升级为 Light Professional AI Development Workspace，
增加 Agent、任务管线和分区任务详情。
Phase 6.3 增加 Git workspace 安全门禁和 Developer 自动提交证据。
Phase 7 增加任务级 `dry_run / execute` 安全开关和首次 Pilot Benchmark。

## 当前能力

- FastAPI 提交和查询开发任务
- SQLite 保存任务、Agent 输出和执行历史
- CrewAI Agent 调度
- Requirement Analyst 使用 DeepSeek 澄清输入并生成结构化需求规格
- Supervisor 使用 Claude Code 规划任务、验收标准和返工决策
- Developer 默认使用 CrewAI mock 模式，也可启用 Codex CLI 修改目标工作区
- Developer Evidence Layer 收集 Git 变更和受控测试结果
- Verification Engineer 独立重跑批准的测试，再由 Kimi K3 核验代码与证据
- Reviewer 默认使用 DeepSeek 独立输出 `PASS`、`FAIL` 或 `BLOCKED`
- Supervisor 可对 Reviewer FAIL 作出 REWORK 或 BLOCKED 决策
- 服务启动时恢复非终态任务，并清理进程遗留工作区锁
- 同一 workspace 同时只允许一个 RUNNING 任务
- 同一 workspace 的新任务自动记录顺序和前置任务，前置任务未通过时保持
  `WAITING_DEPENDENCY`
- Supervisor 范围门禁会把过大或不可独立验收的任务退回
  `REQUIREMENTS_REVISION`，不会调用 Developer
- Developer 在任务专属 Git worktree/branch 中执行；只有最终 `PASSED`
  的提交才会快进集成交付分支
- Task Worker 持续轮询 SQLite QUEUED 任务，不阻塞 FastAPI 请求
- 结构化执行日志和 Health API 提供任务执行监控
- 支持暂停、取消和重新入队等人工控制
- 创建任务时可上传 TXT、Markdown、CSV、JSON、PDF 和 DOCX 需求文档
- Next.js 控制台展示 Agent、任务、Evidence、日志并提供人工控制入口
- Agent Runtime 抽象层，隔离 API、任务生命周期和具体 Agent 实现

运行架构：

```text
FastAPI
  ↓
Task Service
  ↓
Crew Service
  ↓
Agent Runtime
  ├── Requirement Analyst Runtime → DeepSeek / CrewAI
  ├── Supervisor Runtime → Claude Code
  ├── Developer Runtime  → CrewAI Developer / Codex CLI Adapter
  │                         ↓
  │                       Evidence Collection
  ├── Verification Runtime → 独立测试运行器 + Kimi K3 API
  └── Reviewer Runtime   → DeepSeek / CrewAI（可选 Claude 兼容模式）
  ↓
SQLite
```

## 环境

- macOS
- Python 3.12
- uv
- CrewAI 1.15.7
- FastAPI
- DeepSeek API

项目根目录 `.env`：

```env
DEEPSEEK_API_KEY=你的真实密钥
DEEPSEEK_MODEL=你的实际模型ID
DEEPSEEK_BASE_URL=https://api.deepseek.com
CODEX_ENABLED=false
CODEX_PATH=codex
CLAUDE_ENABLED=false
CLAUDE_PATH=claude
```

不要提交 `.env`，也不要把 API Key 写入请求或日志。

## Developer Runtime 与 Codex CLI

默认 `CODEX_ENABLED=false`，DeveloperRuntime 使用原有 CrewAI Developer，
不会调用 Codex CLI。启用时设置：

```env
CODEX_ENABLED=true
CODEX_PATH=codex
```

Adapter 使用以下非交互调用：

```text
codex exec
  --sandbox workspace-write
  --cd <workspace_path>
  --ephemeral
  --color never
  -
```

完整任务上下文通过 stdin 传入，不拼接成 shell 字符串。Adapter 会检查
`workspace_path` 存在且为目录，并默认拒绝 Auto Dev Platform 自身目录及其父子目录。
如确需开发平台自身，必须在代码组合层显式设置
`allow_platform_workspace=True`，普通任务输入不能绕过该限制。

## Developer Evidence Layer

Codex 模式的开发与验证流程：

```text
Requirement Analyst
  ↓
Supervisor
  ↓
Codex Developer
  ↓
Evidence Collection
  ↓
Verification Engineer
  ↓
Reviewer
```

Codex 完成后，Evidence Collector 使用固定只读 Git 命令收集：

- 当前分支
- `git status --porcelain`
- changed files
- staged 和 unstaged git diff

测试命令只能来自 Supervisor 输出中的 `required_tests`。支持 JSON：

```json
{
  "required_tests": ["uv run pytest -q"]
}
```

也支持逐行格式：

```text
REQUIRED_TEST: uv run pytest -q
```

Test Collector 不使用 shell，只允许预定义的测试工具命令；其他命令会记录为
`Test command is not allowed`，不会执行。

每次 Codex 开发证据写入 SQLite `task_artifacts` 表，包括：

- `git_diff`
- `changed_files`
- `test_results`
- `codex_output`
- `workspace_validation`
- `git_commit`（提交成功时）

## Workspace Validation 与 Git Commit Artifact

Codex Developer 执行前必须通过固定只读检查：

- `workspace_path` 存在
- 路径是目录
- 路径位于 Git work tree
- 路径不是 Auto Dev Platform 自身目录或其父子目录

验证失败时任务进入 `BLOCKED`，Developer 不会被调用，验证结果保存在
`task_artifacts.workspace_validation`。验证成功后才记录
`WORKSPACE_VALIDATED` 和 `CODE_CHANGE_STARTED`。

Codex 成功返回并完成 Evidence 采集后，Developer 使用固定参数执行
`git add --all` 和带任务ID的 `git commit`。成功提交的 hash 保存为
`task_artifacts.git_commit` 并记录 `GIT_COMMIT_CREATED`。提交失败只记录
`ERROR`，不会把已成功的 Developer 执行改为失败，也不会绕过 Reviewer。

Reviewer 默认使用 DeepSeek CrewAI，并会收到 RequirementSpec、Supervisor计划、
Developer Evidence 和 Verification Report。

### 有序交付与未验收代码隔离

部署后的新任务会按 workspace 建立 `sequence_no` 和
`predecessor_task_id`。同一 workspace 内：

1. 第一项任务进入 `QUEUED`；
2. 后续任务进入 `WAITING_DEPENDENCY`；
3. 前置任务只有进入 `PASSED` 或被人工明确 `CANCELED` 后，下一项才会入队；
4. `FAILED`、`BLOCKED` 和 `REQUIREMENTS_REVISION` 不会被 Worker 自动跳过；
5. Retry 保留原任务顺序；历史任务第一次 Retry 时加入新有序队列尾部。

正式执行时，Developer 不直接修改交付工作树。系统从当前交付分支创建
`auto-dev/task-<task-id>` 分支和独立 Git worktree。验证、验收和返工都在该
隔离工作区内完成：

- `PASSED`：使用 `git merge --ff-only` 集成交付分支，并保存
  `integrated_commit` artifact；
- `FAILED / BLOCKED / REQUIREMENTS_REVISION`：任务分支与 worktree 保留用于
  调试或 Retry，交付工作树保持不变；
- 交付工作树不干净或分支在执行期间发生变化：拒绝集成并进入 `BLOCKED`。

历史任务和历史提交不会被自动改写或回滚；以上隔离规则从升级后的新任务及
重新进入新队列的任务开始生效。

## Agent 模型路由

默认配置：

```env
CLAUDE_ENABLED=false
CLAUDE_PATH=claude
REVIEWER_MODE=deepseek
```

此时 Claude 角色保留本地兼容模式。启用 Claude Code：

```env
CLAUDE_ENABLED=true
CLAUDE_PATH=claude
REVIEWER_MODE=deepseek
```

启用后，Supervisor 通过只读 Claude Code Adapter 运行，只输出计划或返工
决策。Requirement Analyst 和 Reviewer 继续使用 DeepSeek。只有显式设置
`REVIEWER_MODE=claude` 才会启用保留的 Claude Reviewer 兼容模式。

Verification Engineer 使用 Kimi K3：

```env
VERIFICATION_PROVIDER=kimi
KIMI_API_KEY=你的Moonshot API Key
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k3
KIMI_REASONING_EFFORT=high
KIMI_MAX_TOKENS=4096
```

验证阶段先由本地确定性运行器执行 Supervisor 批准的 `required_tests`，随后
Kimi 只接收任务上下文、Developer Evidence、Git Diff和测试结果并生成
VerificationReport。Kimi API 不具备工作区写权限，也不能覆盖失败测试。

## Token-efficient Role Context

完整 Agent 输出和 Evidence 继续保存在 SQLite，模型调用则使用按角色生成的
最小充分上下文：

- Kimi 接收原始需求、RequirementSpec、Supervisor验收标准、最终Git Diff
  和确定性测试报告；
- DeepSeek Reviewer 接收原始需求、最终Git Diff、commit、确定性测试结果
  和 Kimi VerificationReport；
- Codex过程性对话、重复测试输出和重复命令历史不会再次发送给下游模型；
- 上传的原始需求文档只发送给 Requirement Analyst；后续角色使用其结构化
  RequirementSpec，避免每个角色重复读取整份文档；
- Codex CLI 使用 JSONL 输出，只保存最终开发摘要和 token usage；超长诊断
  仅保留首尾，完整代码证据仍由 Git Diff 和独立测试结果保存；
- 任务保存下一待执行阶段。恢复或人工 retry 会从失败阶段继续，不会重跑已经
  成功的 Requirement Analyst、Supervisor、Developer 或 Verification；
- JSON使用紧凑序列化，返工轮次仍保留最终累计证据。

该机制只减少重复传输，不删除角色、不跳过测试，也不改变原始证据的数据库留存。

完整五角色流程：

```text
Requirement Analyst
  ↓
Supervisor
  ↓
Codex Developer
  ↓
Evidence Collection
  ↓
Verification Engineer
  ↓
DeepSeek Reviewer
```

## 硬件产品智能体模板库

创建任务时可以从 `/agents/catalog` 读取预置角色、兼容模型和团队预设，并以
`workflow_steps` 保存真正有序的工作链。每个步骤都有独立 `step_id`、角色、
模型和顺序；同一专业角色可以重复出现并分别使用不同模型。历史字段
`selected_agents` 与 `agent_models` 继续保留用于旧任务和API兼容。核心需求
分析师和监督者始终参与；其余专业角色可以按任务不断添加：

- 市场研究员
- 用户洞察与评论研究员
- 竞品分析师
- 产品策略与PRD架构师
- 工业设计顾问
- UI/UX设计师
- 硬件系统架构师
- BOM与成本工程师
- 供应链与采购分析师
- 法规与认证专家
- DFX与制造工程师
- 硬件测试与验证策划师
- Codex开发者、验证工程师和独立验收者

内置团队预设包括产品机会研究、硬件产品立项、软件开发交付和完整硬件产品
团队。预设只是工作链起点，用户仍可添加、删除、上移、下移专业步骤并逐步
切换兼容模型。专业角色在 `RESEARCHING` 阶段严格按 `workflow_steps` 线性
执行，结果以步骤编号保存为 `specialist_output` Artifact，再交给Supervisor
整合。未启用开发交付闭环的产品研究任务不会调用Codex或修改工作区。

为保持角色隔离，需求分析师固定为第一步，监督者固定在研究链末尾；启用代码
交付时，尾部固定为 Developer → Verification Engineer → Reviewer。专业研究
区可以持续扩展到最多200个步骤。

可选AI按真实能力限制：

- 专业研究角色：DeepSeek、Claude Code或Kimi K3；
- Supervisor：Claude Code或DeepSeek；
- Developer：Codex CLI；
- Verification Engineer：Kimi K3或Claude Code；
- Reviewer：DeepSeek或Claude Code。

## 可扩展模型目录

`GET /models` 返回内置和自定义模型、供应商、真实模型ID、接口类型、配置状态
以及推理、多模态、视觉、长上下文、代码和工具调用等能力标签。`POST /models`
可以新增 OpenAI-compatible、Anthropic Messages 或人工交接模型；
`POST /models/{id}/credential` 更新凭证，`DELETE /models/{id}` 删除未被任务引用
的自定义模型。

API Key 只写入当前Mac用户的 macOS Keychain，服务名为
`com.autodevplatform.models`。SQLite仅保存 `keychain:<model_id>` 引用，所有
API响应均不包含密钥明文。服务重启时会从Keychain恢复内置API模型凭证。

UI/UX设计师默认使用 `claude_opus_design` 自动化设计配置，能力重点为视觉
推理、多模态、设计系统和交互原型。`claude_design_handoff` 对应Claude Design
人工交接：由于Claude Design当前没有可直接调用的公开API，该模式会返回人工
交接信息，而不会伪造自动执行结果。

历史内部ID `supervisor`、`developer`、`reviewer` 继续用于旧任务和状态机兼容，
新界面分别显示为“产品交付规划师”“软件实现工程师”和“产品质量验收经理”，
不再暴露笼统角色名称。

用户评论角色不会凭空生成评论。当前只分析上传文档、明确提供的来源和可见
工作区资料；缺少评论来源时仅生成受控采集计划。任意互联网抓取器尚未启用。

Claude Code Adapter 使用非交互只读配置：

```text
claude --print
  --permission-mode plan
  --tools Read,Grep,Glob
  --disallowedTools Edit,Write,NotebookEdit,Bash
  --no-session-persistence
  --safe-mode
```

Adapter 将需求规格、任务目标、requirements、验收标准、workspace、
Developer Evidence、Verification Report、Git diff和测试结果通过 stdin 交给
Claude。Claude 不能编辑、写入、删除、提交文件或执行 Bash。

Claude 的正式结论必须为 `FINAL_RESULT: PASS`、`FINAL_RESULT: FAIL` 或
`FINAL_RESULT: BLOCKED`。正文中的 PASS/FAIL/BLOCKED 不参与判定。

## Supervisor Decision 与受控返工

Reviewer 返回 FAIL 后，Supervisor 会收到任务、Reviewer结果、Developer Evidence
和当前 iteration，并返回：

```text
FINAL_ACTION: COMPLETE
FINAL_ACTION: REWORK
FINAL_ACTION: BLOCKED
```

REWORK 必须同时给出：

```text
DEVELOPER_TASK: <具体修复任务>
```

受控循环：

```text
Reviewer FAIL
  ↓
Supervisor Decision
  ↓ REWORK
REWORKING
  ↓
Developer
  ↓
Verification Engineer
  ↓
Reviewer
```

任务默认 `max_retry=3`，并有硬上限10。达到最大重试次数后直接进入 BLOCKED，
不会继续调用 Codex、Claude或 Supervisor。每轮结果保存在 `task_iterations`。
Supervisor 不能把 Reviewer FAIL 直接改成 PASSED；如果在 FAIL 后返回 COMPLETE，
任务保持 FAILED。

## 单机运行可靠性

Phase 4.2 增加以下任务字段：

- `started_at`
- `last_heartbeat`
- `timeout_seconds`，默认3600秒
- `blocked_reason`
- `required_action`

FastAPI 启动时会在后台扫描非终态任务。未超时且工作区存在的任务重置为
`QUEUED` 并恢复执行；超时任务进入 `FAILED`；工作区不可用的任务进入
`BLOCKED` 并保存人工处理要求。

`workspace_locks` 表提供单机互斥：

```text
workspace_path + ACTIVE → 同一时间只能属于一个task_id
```

任务所有正常、失败或异常退出路径都会释放锁。服务重启时，旧进程遗留的
ACTIVE 锁会标记为 STALE。

这是 SQLite 基础队列，不包含 Redis、Celery或分布式调度。锁冲突任务保持
`QUEUED`，等待后续恢复或再次触发。

## Task Worker、Heartbeat与优雅关闭

FastAPI 的 POST `/tasks` 只创建并入队任务，不直接运行 Agent。独立
`TaskWorker` 线程持续轮询 SQLite：

```text
QUEUED
  ↓ Workspace Lock
RUNNING
  ↓ TaskService
ANALYZING → PLANNING → DEVELOPING → VERIFYING → REVIEWING
```

Worker 当前为单进程、单任务串行执行。执行期间，独立 heartbeat 线程按周期更新
`last_heartbeat`，覆盖 RUNNING、ANALYZING、PLANNING、DEVELOPING、
VERIFYING、REVIEWING和REWORKING。

通过 `python backend/main.py` 启动时，Uvicorn 接收 SIGTERM 或 SIGINT 后会进入
FastAPI lifespan 关闭流程：

1. Worker停止轮询新任务；
2. 等待当前任务安全结束；
3. CrewService和Worker释放workspace lock；
4. 最终任务状态和heartbeat保存在SQLite。

## Development、Production 与 Benchmark 模式

### Development Source

开发源码就是克隆后的仓库目录，例如：

```text
~/Projects/auto-dev-team
```

用于代码修改、测试和构建。开发模式读取项目根目录 `.env`，数据库默认位于
源码目录的 `data/`，不会自动启用生产workspace限制。

### Production Runtime

独立运行实例位于：

```text
~/AutoDevPlatform/
├── backend/
├── frontend/
├── src/
├── data/
├── logs/
├── workspaces/
├── config/
├── start.sh
├── stop.sh
└── status.sh
```

生产配置为 `config/production.env`。它固定生产数据库和workspace根目录，
Codex与Claude默认保持关闭。

从开发源码更新生产副本：

```bash
./scripts/install-production.sh
```

安装脚本只同步程序目录，保留生产 `data`、`logs`、`workspaces` 和已有
`config/production.env`。

生产服务使用macOS launchd LaunchAgent，在当前用户登录后自动启动：

```bash
~/AutoDevPlatform/start.sh
~/AutoDevPlatform/status.sh
~/AutoDevPlatform/stop.sh
```

Backend与Task Worker运行在同一个FastAPI进程；Frontend使用独立launchd服务。
日志写入 `~/AutoDevPlatform/logs/`。

### Benchmark Mode

Benchmark定义和源fixture位于：

```text
~/AutoDevBenchmarks/
```

该目录位于生产workspace根目录之外，不能直接交给Codex。正式Pilot必须先创建
独立工作副本到 `~/AutoDevPlatform/workspaces/`。详细规则见
`docs/production/workspace-policy.md`。

## 启动 API（开发模式）

同步依赖：

```bash
uv sync
```

在项目虚拟环境中启动：

```bash
python backend/main.py
```

也可以直接使用：

```bash
uv run python backend/main.py
```

服务默认监听 `http://127.0.0.1:8000`。

## 启动 Web Dashboard（开发模式）

FastAPI 运行后，在另一个终端启动前端：

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

访问 `http://127.0.0.1:3000`。Dashboard 通过 Next.js 本地代理连接 FastAPI，
不需要修改后端 CORS 或 API。

系统状态：

```bash
curl http://127.0.0.1:8000/
```

部署健康检查：

```bash
curl http://127.0.0.1:8000/health
```

返回系统健康状态、SQLite 连通性、Worker 状态和当前队列长度。

创建任务：

```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "project_name": "产品知识系统",
    "workspace_path": "/absolute/path/to/project",
    "goal": "实现 Knowledge API",
    "requirements": ["统一查询入口", "支持型号识别"],
    "priority": "high",
    "execution_mode": "dry_run"
  }'
```

创建接口立即返回 `CREATED`，任务随后进入 `QUEUED`，由 Task Worker 异步执行。

使用需求文档创建任务：

```bash
curl -X POST http://127.0.0.1:8000/tasks/with-documents \
  -F 'project_name=产品知识系统' \
  -F 'workspace_path=/absolute/path/to/project' \
  -F 'goal=实现 Knowledge API' \
  -F 'requirements=["统一查询入口"]' \
  -F 'execution_mode=dry_run' \
  -F 'documents=@specification.pdf'
```

开发目标和需求列表可在上传需求文档后留空。最多上传 5 个文档，每个不超过
10 MB，总大小不超过 25 MB。文件保存在平台数据目录的
`uploads/<task_id>/` 中，并作为只读需求上下文提供给 Agent。

查询任务：

```bash
curl http://127.0.0.1:8000/tasks
curl http://127.0.0.1:8000/tasks/<task_id>
```

任务详情包含当前 Agent、迭代次数、heartbeat、Developer evidence 摘要和
持久化 execution logs。

人工控制：

```bash
curl -X POST http://127.0.0.1:8000/tasks/<task_id>/pause
curl -X POST http://127.0.0.1:8000/tasks/<task_id>/cancel
curl -X POST http://127.0.0.1:8000/tasks/<task_id>/retry
```

暂停和取消采用协作式控制：若 Agent CLI 正在执行，系统会等待该次调用返回，
随后停止进入下一阶段并释放 workspace lock。`retry` 仅接受
`PAUSED / CANCELED / FAILED / BLOCKED` 任务，并将其重新加入 `QUEUED`。

任务状态：

```text
CREATED
→ QUEUED
→ RUNNING
→ ANALYZING
→ PLANNING
→ DEVELOPING
→ VERIFYING
→ REVIEWING
→ FAILED → REWORKING → DEVELOPING → VERIFYING
→ PASSED / FAILED / BLOCKED
```

非终态任务也可由人工控制进入 `PAUSED / CANCELED`；其中 `CANCELED` 为终态，
`PAUSED` 只能通过 retry 重新入队，并且二者不会在服务重启时被自动恢复。
任务生命周期只使用 `PASSED / FAILED / BLOCKED`；Reviewer 的验收结论
只使用 `PASS / FAIL / BLOCKED`，两者不会混用。

## Observability 与人工控制

`execution_logs` 表按任务保存关键生命周期事件，包括：

- `TASK_CREATED`、`TASK_STARTED`、`TASK_FINISHED`
- `REQUIREMENT_ANALYSIS_STARTED`、`REQUIREMENT_ANALYSIS_FINISHED`
- `SUPERVISOR_STARTED`、`SUPERVISOR_FINISHED`
- `DEVELOPER_STARTED`、`CODEX_STARTED`、`TEST_STARTED`
- `VERIFICATION_STARTED`、`VERIFICATION_FINISHED`
- `REVIEW_STARTED`、`REWORK_STARTED`
- `ERROR`

人工暂停、取消和重试也会写入控制事件，方便后续 Dashboard 还原完整时间线。
日志由 Service/编排层写入；Runtime 仍不接触数据库或 HTTP。

任务数据默认保存在 `data/auto_dev_team.db`。数据库文件已被 Git 忽略。

## Execution Mode

每个任务必须记录执行模式：

```text
dry_run（默认）
  Requirement Analyst分析
  Supervisor规划
  不调用Developer
  不修改文件
  不创建Git commit
  不调用Reviewer

execute（必须显式选择）
  Requirement Analyst
  → Supervisor
  → Workspace Validation
  → Codex Developer
  → Evidence
  → Git Commit
  → Verification Engineer
  → Claude Reviewer
```

`CODEX_ENABLED=true` 不会覆盖任务级 `dry_run`。只有任务输入明确包含
`"execution_mode": "execute"` 时，系统才允许进入代码修改阶段。

## 第一次 Controlled Pilot Run

### Benchmark-001：基础成功链路

完整规范见 `docs/benchmark/benchmark-001.md`。执行顺序：

1. 创建独立、可丢弃的 Python Git 仓库并提交干净基线。
2. 首先以 `dry_run` 提交 Benchmark-001，只审阅 Supervisor 计划。
3. 人工确认 workspace、预期文件、验收标准和 required test。
4. 新建任务并显式选择 `execute`。
5. 观察 Workspace Validation、Codex、Evidence、commit和 Claude Review。
6. 人工核对 changed files、git diff、测试、commit hash与最终 PASS。

### Benchmark-002：受控 Rework

Benchmark-001 通过后再进行。准备一个测试可稳定复现、首次实现应被 Reviewer
判定为 `FAIL` 的小任务，并验证：

1. Reviewer 给出明确失败原因。
2. Supervisor Decision 返回 `REWORK` 和具体修复任务。
3. Developer 只修复失败点并创建下一轮 commit。
4. 新 Evidence 对应新一轮修改和测试。
5. Reviewer 第二轮返回 `PASS`。
6. `retry_count`、`task_iterations`、execution logs和两个commit artifact完整。

Benchmark-002 同样先执行 `dry_run`；未经人工确认不得切换到 `execute`。

## 保留 CrewAI CLI

`crewai run` 不再从源码读取硬编码项目目标。运行前通过环境变量传入：

```bash
export AUTO_DEV_PROJECT_GOAL='实现 Knowledge API'
crewai run
```

程序入口也支持 `--project-goal`：

```bash
uv run auto_dev_team --project-goal '实现 Knowledge API'
```

最终 Crew 验收报告仍写入 `output/acceptance_report.md`。

## 测试

```bash
uv run pytest
```

测试使用临时 SQLite 和 Mock Runtime，不会真实调用 DeepSeek。

## 当前限制

- Codex CLI 默认关闭，必须通过 `CODEX_ENABLED=true` 显式启用
- Claude Code默认关闭，必须通过 `CLAUDE_ENABLED=true` 显式启用
- Dashboard 当前面向可信的单机内部用户，不包含登录和多用户权限
- 后台任务运行在当前 FastAPI 进程内；服务重启时会从数据库恢复非终态任务
- Worker为单进程串行执行，不提供多机或分布式并发
- 恢复和人工 retry 支持角色阶段级断点续跑；单个 CLI 调用内部仍不支持指令级恢复
- 当前不包含 Docker、Redis、PostgreSQL、Kubernetes 或 LangGraph

## 后续计划

- Phase 2：Developer Runtime 支持 Codex CLI（当前）
- Phase 3：Reviewer Runtime 支持 Claude Code（当前）
- Phase 4.1：Supervisor Decision 与受控返工循环（当前）
- Phase 4.2：单机恢复、超时、BLOCKED信息与工作区锁（当前）
- Phase 4.3：Task Worker、周期心跳和优雅关闭（当前）
- Phase 5：Observability 与人工控制层（当前）
- Phase 6.1：Web Dashboard（当前）
- Phase 6.2：Dashboard 产品化优化（当前）
- Phase 6.3：Production Readiness Preparation（当前）
- Phase 7：Controlled Pilot Run Preparation（当前）
- Phase 6.4：Production Runtime Separation（当前）

## 许可证

本项目采用 [MIT License](LICENSE)，允许个人与商业用途、修改和再分发，
但不提供任何明示或暗示的担保。


---

<!-- SVENKUNKKA-PROJECT-INFO:BEGIN -->

<a id="project-overview-zh"></a>
## 中文项目说明

本地优先的 AI 开发任务平台，以 FastAPI、SQLite、CrewAI 和 Next.js 管理需求分析、监督、开发、验证及验收流程，提供持久化任务、日志、受控返工和 Git 证据。

**使用入口：** 配置 `.env` 后运行 `uv sync` 与 `uv run python backend/main.py`；在 `frontend/` 配置 `.env.local`，运行 `npm ci`、`npm run dev`。

**范围说明：** 界面面向可信本机用户，无登录及多用户权限；真实执行和可选 CLI 集成需要显式配置，默认保持安全开关关闭。

<a id="project-overview-en"></a>
## English project overview

A local-first AI development task platform using FastAPI, SQLite, CrewAI and Next.js to coordinate requirements, supervision, development, verification and acceptance, with persistent tasks, logs, controlled rework and Git evidence.

**Getting started:** Configure `.env`, then run `uv sync` and `uv run python backend/main.py`. Configure `.env.local` in `frontend/`, then run `npm ci` and `npm run dev`.

**Scope:** The dashboard is for trusted local users and has no login or multi-user authorization. Real execution and optional CLI integrations require explicit configuration; leave safety switches off until configured.

**仓库维护者 / Repository maintainer:** [SvenKunkka](https://github.com/SvenKunkka) · [X / Twitter](https://x.com/Svenu1s5)

<!-- SVENKUNKKA-PROJECT-INFO:END -->
