from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeSettings:
    environment: str
    data_dir: Path
    workspace_root: Path | None
    env_file: Path

    @classmethod
    def from_environment(cls, project_root: Path) -> "RuntimeSettings":
        environment = os.getenv(
            "AUTO_DEV_ENV", "development"
        ).strip().lower()
        if environment not in {"development", "production"}:
            raise ValueError(
                "AUTO_DEV_ENV must be 'development' or 'production'"
            )
        data_dir = Path(
            os.getenv("AUTO_DEV_DATA_DIR", str(project_root / "data"))
        ).expanduser().resolve()
        workspace_value = os.getenv("AUTO_DEV_WORKSPACES_ROOT")
        workspace_root = (
            Path(workspace_value).expanduser().resolve()
            if workspace_value
            else None
        )
        env_file = Path(
            os.getenv(
                "AUTO_DEV_ENV_FILE",
                str(project_root / ".env"),
            )
        ).expanduser().resolve()
        if environment == "production" and workspace_root is None:
            raise ValueError(
                "AUTO_DEV_WORKSPACES_ROOT is required in production"
            )
        return cls(
            environment=environment,
            data_dir=data_dir,
            workspace_root=workspace_root,
            env_file=env_file,
        )
