# Benchmark-001：受控基础开发任务

## 测试目标

验证 Auto Dev Platform 第一次真实执行链路能够在一个独立、可丢弃的 Git
仓库内完成小型代码修改，同时留下可复核的计划、代码、测试、Evidence、Review
和 commit artifact。

本规范只定义 Pilot，不授权立即执行。正式运行前必须由人工确认 workspace、
基线 commit、执行模式和模型开关。

## 测试项目

- 项目名称：`auto-dev-pilot-calculator`
- 项目类型：Python 3.12 小型库
- Workspace：人工创建的独立临时 Git 仓库，禁止使用 Auto Dev Platform 仓库
- 基线要求：
  - Git working tree clean
  - 已存在初始 commit
  - 已配置仓库级 Git user name 和 email
  - `pytest` 可以在不联网的情况下运行
- 任务目标：增加两个整数求和函数，并为正常值、负数和零编写测试
- Required test：`uv run pytest -q`

## 预期修改文件

- `src/pilot_calculator.py`
- `tests/test_pilot_calculator.py`
- 如项目现有包结构要求，可最小修改对应的 `__init__.py`

不允许修改：

- Workspace 之外的任何文件
- Auto Dev Platform 源码
- Git 配置、远程地址和分支保护配置
- 与任务无关的依赖或项目设置

## 预期 Codex 行为

1. 只在指定 workspace 内工作。
2. 阅读 Supervisor 的目标、需求、验收标准和 required tests。
3. 进行最小代码修改，不重构无关模块。
4. 执行 `uv run pytest -q`。
5. 输出修改摘要、测试结果和已知限制。
6. 不自行判断最终 PASS，不修改 Reviewer 结果。
7. 完成后由平台创建带 task ID 的 Git commit。

## 预期 Evidence

- `workspace_validation.valid = true`
- Git branch 和执行前后状态可读取
- `changed_files` 至少包含：
  - `src/pilot_calculator.py`
  - `tests/test_pilot_calculator.py`
- `git_diff` 能完整展示函数和测试变更
- `test_results` 包含 `uv run pytest -q`
- 测试 exit code 为 `0`
- `codex_output` 非空
- `git_commit` 为有效 commit hash
- Execution logs 包含：
  - `WORKSPACE_VALIDATED`
  - `CODE_CHANGE_STARTED`
  - `CODE_CHANGE_FINISHED`
  - `GIT_COMMIT_CREATED`

## 预期 Claude 结果

Claude Code 使用只读模式检查需求、代码、Git diff、测试结果和 Evidence。

满足以下条件时预期：

```text
FINAL_RESULT: PASS
```

必须确认：

- 实现与目标一致
- 正常值、负数和零均有测试
- required test 成功
- 没有无关文件修改
- Evidence 与真实 workspace 状态一致

如果测试失败、功能不完整或出现无关修改，应返回 `FAIL`；如果 workspace、
依赖或需求导致无法验收，应返回 `BLOCKED`。
