import re
from schedules.models import Task


class DateTask:
    def __init__(self, date: str, task: Task):
        self.date = date
        if type(task) != Task:
            raise ValueError("task must be a Task object")
        self.task = task

    @staticmethod
    def from_str(date_task_str: str):
        # check that str is in format YYYY-m-d-TASK_ID
        if not re.match(r"^\d{4}-\d{1,2}-\d{1,2}-[A-Za-z0-9_]+$", date_task_str):
            raise ValueError("date_task_str must be in format YYYY-MM-DD-TASK_ID")
        date, task_id = date_task_str.rsplit("-", 1)
        task = Task.objects.get(id=task_id)
        if not task:
            raise ValueError(f"task {task_id} not found")
        return DateTask(date, task)

    @property
    def task_id(self):
        return self.task.id

    @property
    def day_of_week(self):
        return self.task.service.day_of_week

    def __str__(self):
        return f"{self.date}-{self.task_id}"

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        if not isinstance(other, DateTask):
            return False
        return str(self) == str(other)
