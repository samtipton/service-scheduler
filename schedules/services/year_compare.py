"""Generate several months with one or more objectives, then score the jobs.

    python manage.py compare_objectives
    python manage.py compare_objectives FairJobs
    python manage.py compare_objectives CatchUpShare FairJobs --months 6
    python manage.py dump_compare_db
    python manage.py compare_objectives FairJobs --dump

Roster: a tiny Python world (load_compare_world), or --dump to load live.sql
(anonymized users, tasks, prefs, last year of assignments).

Uses a throwaway test database (see the management command). History is
Assignment rows: month n is in the 12-month window for month n+1.
is_official is unused.

Both objectives are scored on the same ruler, even Catch-up share:

    fair share of a task  =  (this person's preference / sum of preferences)
                             × how many cells of that task existed in the run
    fill_ratio            =  jobs they got  /  sum of those fair shares

1.0 means they got exactly their share. 0.5 means half. 2.0 means twice as many.

Printed KPI table
-----------------
months
    How many months were generated.

infeasible
    Months CBC could not fill at all. 0 is required.

unfilled
    Empty cells across the year (a Sunday of song leader with nobody in it).
    0 means every hole got a person.

exclusion_violations
    Times one person held two tasks that exclude each other on the same date
    (e.g. song leader and usher that Sunday). 0 is required.

consecutive_violations
    Times one person did the same task on two consecutive occurrences
    (two Sundays in a row of song leader). 0 is required.

fill_ratio_min / median / mean / max
    Across eligible people: jobs got ÷ jobs owed. Closer together, and closer
    to 1.0, is fairer. min 0 means someone owed jobs got none. max 1.96 means
    someone got about twice their share.

fill_ratio_stdev
    Spread of those ratios. Small means people were treated alike after
    eligibility; large means pile-on and starvation.

mad
    Mean absolute deviation: average of |jobs they did of a task − their fair
    share of that task|, over every (person, task) they are eligible for.
    This is the same “distance from target” FairJobs minimizes, scored
    after the fact. Smaller is closer to fair. Units are jobs.

max_abs_gap
    Worst single (person, task): how many jobs they were over or under their
    fair share. Smaller is better.

starved
    Active eligible people who got 0 jobs all year. Inactive members are
    skipped. 0 is the goal.

jobs_min / jobs_max
    Fewest and most jobs any eligible person got, raw counts. This is what
    the grid looks like, not adjusted for how many tasks they signed up for.
    A 1-task person at fair share will have a lower raw count than a 10-task
    person at fair share.

max_jobs_one_month
    Busiest one person was in any single month. Catch-up share used to dump
    4–6 jobs on someone behind; FairJobs caps that.

Extra lines the test prints (not in the table)
----------------------------------------------
p=2 song jobs / p=0.5 song jobs
    How many song-leader cells went to the person with preference 2 vs the
    person with preference 0.5. Preference 2 is owed about four times as many
    as 0.5, so FairJobs should give the p=2 person more.

new person month-1 jobs
    Jobs in January for the person who joined that month. Catch-up share can
    spike (they look infinitely behind). FairJobs starts them even and
    caps the first month at 3.
"""

import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time
from statistics import mean, median, pstdev

from django.utils import timezone

from schedules.models import Assignment, Schedule, Service, Task, TaskPreference
from schedules.services.fairness import add_months, as_date, date_tasks_for_schedule
from schedules.services.objectives import OBJECTIVES, get_objective
from schedules.services.scheduler import Scheduler
from users.models import User

MONTHS = 12
START = date(2026, 1, 1)
TEST_EMAIL = "test+{slug}@example.com"
JOINED = timezone.make_aware(datetime(2020, 1, 1))
DISPLAY_NAMES = {
    "FairJobsObjective": "Fair jobs",
    "CatchUpShareObjective": "Catch-up share",
}


def parse_datetask_date(value: str) -> date:
    year, month, day = (int(part) for part in value.split("-"))
    return date(year, month, day)


def generate_months(
    objective, start: date, n: int, creator, name_prefix: str, on_month=None
):
    """Solve n months in order and persist assignments. Returns (schedules, infeasible).

    on_month(done, total) is called after each month if given.
    """
    objective = get_objective(objective) if isinstance(objective, str) else objective
    schedules = []
    infeasible = 0
    prev = None
    for i in range(n):
        month_date = add_months(start.year, start.month, i)
        schedule = Schedule.objects.create(
            name=f"{name_prefix}-{month_date.year}-{month_date.month:02d}",
            date=month_date,
            user=creator,
            base_schedule=prev,
        )
        services = list(
            Service.objects.prefetch_related("tasks", "tasks__excludes").all()
        )
        scheduler = Scheduler(schedule, services, objective=objective)
        result, assignment_map = scheduler.solve()
        if result == -1:
            infeasible += 1
        else:
            _persist(schedule, assignment_map)
        schedules.append(schedule)
        prev = schedule
        if on_month:
            on_month(i + 1, n)
    return schedules, infeasible


def _persist(schedule, assignment_map: dict[str, str]):
    users = {user.inverted_name(): user for user in User.objects.filter(is_active=True)}
    tasks = {task.id: task for task in Task.objects.all()}
    rows = []
    for date_task_str, inverted_name in assignment_map.items():
        if not inverted_name:
            continue
        date_str, task_id = date_task_str.rsplit("-", 1)
        on = parse_datetask_date(date_str)
        rows.append(
            Assignment(
                schedule=schedule,
                task=tasks[task_id],
                user=users[inverted_name],
                assigned_at=timezone.make_aware(datetime(on.year, on.month, on.day)),
            )
        )
    Assignment.objects.bulk_create(rows)


def score_months(schedules, infeasible: int = 0) -> dict:
    """Score a run on the FairJobs ruler. Field meanings: module docstring."""
    services = list(Service.objects.prefetch_related("tasks", "tasks__excludes").all())
    holes = Counter()
    date_tasks = []
    for schedule in schedules:
        for date_task in date_tasks_for_schedule(schedule, services):
            holes[date_task.task_id] += 1
            date_tasks.append(date_task)

    assignments = list(
        Assignment.objects.filter(schedule__in=schedules).select_related("user", "task")
    )
    filled = len(assignments)
    unfilled = len(date_tasks) - filled

    count_ut = Counter((row.user_id, row.task_id) for row in assignments)
    count_u = Counter(row.user_id for row in assignments)
    count_u_month = Counter(
        (row.user_id, as_date(row.assigned_at).year, as_date(row.assigned_at).month)
        for row in assignments
    )

    prefs = {
        (pref.user_id, pref.task_id): pref.value
        for pref in TaskPreference.objects.filter(
            value__gt=0, user__is_active=True
        )
    }
    pref_total = defaultdict(float)
    for (_, task_id), value in prefs.items():
        pref_total[task_id] += value

    abs_gaps = []
    fill_ratios = []
    residuals = []
    starved = 0
    for (user_id, task_id), value in prefs.items():
        denom = pref_total.get(task_id, 0)
        target = (value / denom) * holes[task_id] if denom else 0.0
        got = count_ut[(user_id, task_id)]
        abs_gaps.append(abs(got - target))

    load_target = defaultdict(float)
    for (user_id, task_id), value in prefs.items():
        denom = pref_total.get(task_id, 0)
        if denom:
            load_target[user_id] += (value / denom) * holes[task_id]

    for user_id, target in load_target.items():
        got = count_u[user_id]
        residual = got - target
        residuals.append(residual)
        if target > 0:
            fill_ratios.append(got / target)
            if got == 0:
                starved += 1

    unique_people = defaultdict(set)
    for user_id, task_id in count_ut:
        unique_people[task_id].add(user_id)

    jobs_by_user = [count_u[user_id] for user_id in load_target] or [0]
    month_loads = list(count_u_month.values()) or [0]

    return {
        "months": len(schedules),
        "infeasible": infeasible,
        "unfilled": unfilled,
        "exclusion_violations": _exclusion_violations(assignments),
        "consecutive_violations": _consecutive_violations(schedules, services, assignments),
        "fill_ratio_min": min(fill_ratios) if fill_ratios else 0.0,
        "fill_ratio_max": max(fill_ratios) if fill_ratios else 0.0,
        "fill_ratio_mean": mean(fill_ratios) if fill_ratios else 0.0,
        "fill_ratio_median": median(fill_ratios) if fill_ratios else 0.0,
        "fill_ratio_stdev": pstdev(fill_ratios) if len(fill_ratios) > 1 else 0.0,
        "mad": mean(abs_gaps) if abs_gaps else 0.0,
        "max_abs_gap": max(abs_gaps) if abs_gaps else 0.0,
        "starved": starved,
        "jobs_min": min(jobs_by_user),
        "jobs_max": max(jobs_by_user),
        "max_jobs_one_month": max(month_loads),
        "unique_people": {task_id: len(ids) for task_id, ids in unique_people.items()},
        "count_ut": dict(count_ut),
        "count_u": dict(count_u),
        "count_u_month": dict(count_u_month),
        "holes": dict(holes),
    }


def _exclusion_violations(assignments) -> int:
    pairs = set()
    for task in Task.objects.prefetch_related("excludes"):
        for other in task.excludes.all():
            if task.id < other.id:
                pairs.add((task.id, other.id))
    by_user_date = defaultdict(set)
    for row in assignments:
        by_user_date[(row.user_id, as_date(row.assigned_at))].add(row.task_id)
    n = 0
    for task_ids in by_user_date.values():
        for left, right in pairs:
            if left in task_ids and right in task_ids:
                n += 1
    return n


def _consecutive_violations(schedules, services, assignments) -> int:
    dates_by_task = defaultdict(set)
    for schedule in schedules:
        for date_task in date_tasks_for_schedule(schedule, services):
            dates_by_task[date_task.task_id].add(parse_datetask_date(date_task.date))
    consecutive = []
    for task_id, dates in dates_by_task.items():
        ordered = sorted(dates)
        consecutive.extend((task_id, a, b) for a, b in zip(ordered, ordered[1:]))
    held = defaultdict(set)
    for row in assignments:
        held[(row.user_id, row.task_id)].add(as_date(row.assigned_at))
    n = 0
    user_ids = {row.user_id for row in assignments}
    for task_id, earlier, later in consecutive:
        for user_id in user_ids:
            dates = held[(user_id, task_id)]
            if earlier in dates and later in dates:
                n += 1
    return n


def format_table(columns: dict[str, dict]) -> str:
    """columns: objective name → score dict."""
    keys = [
        "months",
        "infeasible",
        "unfilled",
        "exclusion_violations",
        "consecutive_violations",
        "fill_ratio_min",
        "fill_ratio_median",
        "fill_ratio_mean",
        "fill_ratio_max",
        "fill_ratio_stdev",
        "mad",
        "max_abs_gap",
        "starved",
        "jobs_min",
        "jobs_max",
        "max_jobs_one_month",
    ]
    names = list(columns)
    width = max(22, *(len(name) + 2 for name in names))
    header = f"{'KPI':<26}" + "".join(f"{name:>{width}}" for name in names)
    lines = [header, "-" * len(header)]
    for key in keys:
        row = f"{key:<26}"
        for name in names:
            value = columns[name][key]
            if isinstance(value, float):
                row += f"{value:>{width}.3f}"
            else:
                row += f"{value:>{width}}"
        lines.append(row)
    return "\n".join(lines)


@dataclass
class Highlight:
    label: str
    person: User
    task: Task | None = None
    month1: bool = False


@dataclass
class CompareWorld:
    creator: User
    people: dict
    tasks: dict
    highlights: list
    start: date
    aliases: dict = field(default_factory=dict)
    source: str = ""

    @property
    def p2(self):
        return self.people.get(self.aliases.get("p2", "u0"))

    @property
    def p05(self):
        return self.people.get(self.aliases.get("p05", "u1"))

    @property
    def new(self):
        return self.people.get(self.aliases.get("new", "u7"))

    @property
    def song(self):
        return self.tasks.get(self.aliases.get("song", "yc_song"))


def resolve_objectives(names: list[str] | None) -> list[str]:
    """Full class name, or a unique substring (FairJobs, CatchUpShare)."""
    if not names:
        return list(OBJECTIVES.keys())
    resolved = []
    for name in names:
        if name in OBJECTIVES:
            resolved.append(name)
            continue
        matches = [key for key in OBJECTIVES if name.lower() in key.lower()]
        known = ", ".join(OBJECTIVES)
        if len(matches) == 1:
            resolved.append(matches[0])
        elif not matches:
            raise ValueError(f"Unknown objective {name!r}. Choose from: {known}")
        else:
            raise ValueError(f"Ambiguous objective {name!r}: {', '.join(matches)}")
    return resolved


def _user(slug, first, last, joined=None):
    user = User.objects.create_user(
        email=TEST_EMAIL.format(slug=slug),
        first_name=first,
        last_name=last,
        password="x",
    )
    if joined is not None:
        User.objects.filter(pk=user.pk).update(date_joined=joined)
        user.refresh_from_db()
    return user


def load_compare_world(start: date | None = None) -> CompareWorld:
    """Tiny Sunday roster used by the command and the test. Not production people."""
    start = start or START
    creator = _user("year-creator", "Year", "Creator", joined=JOINED)
    service = Service.objects.create(
        name="Sunday AM", day_of_week=0, start_time=time(10, 0)
    )
    song = Task.objects.create(
        id="yc_song", name="Song Leader", service=service, order=1
    )
    usher = Task.objects.create(
        id="yc_usher", name="Usher", service=service, order=2
    )
    song.excludes.add(usher)

    people = {}
    for i in range(8):
        joined = JOINED
        if i == 7:
            joined = timezone.make_aware(datetime(start.year, start.month, 1))
        people[f"u{i}"] = _user(
            f"year-u{i}", f"YearU{i}", "Test", joined=joined
        )

    TaskPreference.objects.create(user=people["u0"], task=song, value=2.0)
    TaskPreference.objects.create(user=people["u1"], task=song, value=0.5)
    for user in list(people.values())[2:]:
        TaskPreference.objects.create(user=user, task=song, value=1.0)
    for user in list(people.values())[:4]:
        TaskPreference.objects.create(user=user, task=usher, value=1.0)

    hist_month = add_months(start.year, start.month, -1)
    history = Schedule.objects.create(
        name=f"history-{hist_month.year}-{hist_month.month:02d}",
        date=hist_month,
        user=creator,
    )
    Assignment.objects.create(
        schedule=history,
        task=song,
        user=people["u2"],
        assigned_at=timezone.make_aware(
            datetime(hist_month.year, hist_month.month, 7)
        ),
    )

    return CompareWorld(
        creator=creator,
        people=people,
        tasks={"yc_song": song, "yc_usher": usher},
        highlights=[
            Highlight("p=2 song jobs", people["u0"], task=song),
            Highlight("p=0.5 song jobs", people["u1"], task=song),
            Highlight("new person month-1 jobs", people["u7"], month1=True),
        ],
        start=start,
        aliases={"p2": "u0", "p05": "u1", "new": "u7", "song": "yc_song"},
        source="tiny roster",
    )


def world_from_database() -> CompareWorld:
    """Roster already in the current database (loaded from live.sql)."""
    latest = Assignment.objects.order_by("-assigned_at").first()
    if latest is None:
        raise ValueError("Dump has no assignments.")
    last = as_date(latest.assigned_at)
    start = add_months(last.year, last.month, 1)
    creator = (
        User.objects.filter(is_superuser=True).order_by("pk").first()
        or User.objects.order_by("pk").first()
    )
    if creator is None:
        raise ValueError("Dump has no users.")
    people = {user.email: user for user in User.objects.all()}
    tasks = {task.id: task for task in Task.objects.all()}
    n_asg = Assignment.objects.count()
    source = (
        f"live dump  start={start.isoformat()}  "
        f"{len(people)} users  {len(tasks)} tasks  {n_asg} history assignments"
    )
    return CompareWorld(
        creator=creator,
        people=people,
        tasks=tasks,
        highlights=[],
        start=start,
        source=source,
    )


def build_compare_world(start: date | None = None) -> CompareWorld:
    return load_compare_world(start)


def format_report(scores: dict, world: CompareWorld) -> str:
    lines = [world.source, format_table(scores)] if world.source else [format_table(scores)]
    for highlight in world.highlights:
        parts = []
        for label, score in scores.items():
            if highlight.month1:
                value = score["count_u_month"].get(
                    (highlight.person.pk, world.start.year, world.start.month), 0
                )
            else:
                task_id = highlight.task.id if highlight.task else None
                value = score["count_ut"].get((highlight.person.pk, task_id), 0)
            parts.append(f"{label}={value}")
        lines.append(f"{highlight.label}: {'  '.join(parts)}")
    return "\n".join(lines)


def run_comparison(
    objectives=None,
    months: int = MONTHS,
    world: CompareWorld | None = None,
    on_progress=None,
):
    """Generate `months` for each objective, score, print-ready text.

    objectives: class names or unique substrings. Empty/None runs every
    registered objective. Each run is deleted before the next so history
    does not leak. Returns (text, scores_by_label, world).

    on_progress(label, done, total) is called after each generated month.
    """
    random.seed(0)
    names = resolve_objectives(objectives)
    world = world or load_compare_world()
    scores = {}
    for name in names:
        objective = get_objective(name)
        label = DISPLAY_NAMES.get(name, name)

        def tick(done, total, label=label):
            if on_progress:
                on_progress(label, done, total)

        schedules, infeasible = generate_months(
            objective,
            world.start,
            months,
            world.creator,
            name_prefix=f"test-year-{name}",
            on_month=tick,
        )
        scores[label] = score_months(schedules, infeasible)
        Schedule.objects.filter(pk__in=[s.pk for s in schedules]).delete()
    return format_report(scores, world), scores, world
