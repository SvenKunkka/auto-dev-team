# Production Workspace Policy

## Allowed execution root

By default, production AI tasks may only use repositories under:

```text
~/AutoDevPlatform/workspaces/
```

Each task must reference a dedicated Git repository below this root. Resolved
paths outside the root are rejected before Codex is invoked.

## Repository requirements

- One project per workspace directory.
- The workspace must be an initialized Git work tree.
- Create and review a clean baseline commit before the first `execute` task.
- Use repository-local Git identity where an automatic commit is required.
- Do not place Auto Dev Platform source code inside the workspace root.
- Do not use symlinks to reach files outside the workspace root.
- Keep secrets, credentials, signing keys and unrelated personal files out of
  AI-managed repositories.

## Benchmark separation

Benchmark definitions and source fixtures belong under:

```text
~/AutoDevBenchmarks/
```

That directory is not executable by the production runtime. For a controlled
pilot, create a fresh working copy under:

```text
~/AutoDevPlatform/workspaces/benchmark-001/
```

Confirm the working copy, baseline commit, `dry_run` plan and expected tests
before creating a separate task with `execution_mode=execute`.

## Lifecycle

1. Prepare or clone a repository into the production workspace root.
2. Verify its remote, branch, Git identity and clean status manually.
3. Run the task in `dry_run`.
4. Review the Supervisor plan.
5. Create a new `execute` task only after approval.
6. Review Evidence, commit artifact and Reviewer result.
7. Archive or remove completed disposable benchmark workspaces manually.
