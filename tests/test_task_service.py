from backend.database.sqlite import SQLiteDatabase
from backend.models.task import TaskCreate, TaskStatus
from backend.services.task_service import TaskService


class StubCrewService:
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database
        self.called_with: list[str] = []

    def run_task(self, task_id: str):
        self.called_with.append(task_id)
        return self.database.update_task(task_id, status=TaskStatus.PASSED)


def test_task_service_creates_lists_gets_and_runs_tasks(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "platform.db")
    database.initialize()
    crew_service = StubCrewService(database)
    service = TaskService(database, crew_service)  # type: ignore[arg-type]
    task_input = TaskCreate(
        project_name="平台",
        workspace_path="/tmp/platform",
        goal="建立API",
        requirements=[],
        priority="normal",
    )

    created = service.create_task(task_input)
    finished = service.run_task(created.task_id)

    assert created.status is TaskStatus.CREATED
    assert finished.status is TaskStatus.PASSED
    assert service.get_task(created.task_id) is not None
    assert len(service.list_tasks()) == 1
    assert crew_service.called_with == [created.task_id]
