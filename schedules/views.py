from collections import defaultdict
import json
from datetime import datetime
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseRedirect,
    JsonResponse,
)
from django.utils import timezone
from django.views import generic
from django.shortcuts import get_object_or_404, render
from django.contrib.auth import get_user_model
from schedules.models import Assignment, AssignmentStats, Schedule, Service, Task
from schedules.services.fairness import build_fairness_window
from schedules.services.objectives import (
    CatchUpShareObjective,
    FairJobsObjective,
    get_objective,
)
from schedules.services.pdf import pdf_filename, render_schedule_pdf
from schedules.services.scheduler import Scheduler
from schedules.utils import (
    get_month_calendar,
    get_service_weeks,
)
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie

from schedules.guard import visible_schedule
from users.access import can_schedule, current_group, roster_for


@method_decorator(ensure_csrf_cookie, name="get")
class MonthView(generic.View):

    def get(self, request, id):
        schedule = visible_schedule(request, id)

        year = schedule.date.year
        month = schedule.date.month
        month_calendar, month_name = get_month_calendar(year, month)

        # TODO consider moving these queries to ScheduleManager
        # Prefetch related objects to minimize queries

        # TODO check if we can prefetch tasks here
        services = Service.objects.filter(group=schedule.group).prefetch_related(
            "tasks__users_with_preferences", "tasks__excludes"
        )

        assignments = schedule.assignments.select_related(
            "task", "user", "task__service"
        )
        assignment_stats = AssignmentStats.objects.filter(
            schedule=schedule
        ).select_related("task", "user")

        service_days = {service.day_of_week for service in services}
        service_weeks = get_service_weeks(month_calendar, service_days)

        # Collect assignment stats in a dictionary
        assignment_stats_map = {
            (stat.task.id, stat.user.pk): stat.assignment_delta
            for stat in assignment_stats
        }

        # Create a map of service_name to assignments for tasks in that service
        service_assignments = defaultdict(dict)
        for assignment in assignments:
            assignment_key = (
                f"{year}-{month}-{assignment.assigned_at.day}-{assignment.task.id}"
            )
            service_assignments[assignment.task.service.name][
                assignment_key
            ] = assignment.user

        objective_name = request.GET.get("objective", FairJobsObjective.name)
        fairness_window = None
        if objective_name == FairJobsObjective.name:
            fairness_window = build_fairness_window(
                schedule, services, roster_for(schedule.group)
            )

        # create map of eligible users for each task sorted by assignment delta
        # or FairJobs ranking (count_so_far − target)
        roster_ids = set(roster_for(schedule.group).values_list("pk", flat=True))
        eligible_users_for_task = defaultdict(list)
        for service in services:
            for task in service.tasks.all():
                eligible_users = [
                    user
                    for user in task.get_eligible_users()
                    if user.pk in roster_ids
                ]
                if fairness_window is not None:
                    sorted_users = sorted(
                        eligible_users,
                        key=lambda user, tid=task.id: fairness_window.ranking_key(
                            user.pk, tid
                        ),
                    )
                else:
                    sorted_users = sorted(
                        eligible_users,
                        key=lambda user: assignment_stats_map.get((task.id, user.pk), 1),
                    )
                eligible_users_for_task[task.id] = sorted_users
        eligible_users_for_task.default_factory = None

        context = {
            "schedule": schedule,
            "year": year,
            "month": month,
            "services": services,
            "month_name": month_name,
            "service_days": service_days,
            "service_weeks": service_weeks,
            "service_assignments": service_assignments,
            "eligible_users_for_task": eligible_users_for_task,
            "col_span": len(service_weeks) + len(service_weeks) + 1,
            "objective_name": objective_name,
            "objective_choices": [
                (FairJobsObjective.name, "Fair jobs"),
                (CatchUpShareObjective.name, "Catch-up share (old)"),
            ],
        }
        return render(request, "schedules/month_schedule.html", context)

    def post(self, request, year, month):
        """
        save assignments, mark as draft until commit?
        """
        pass


class MonthListView(generic.ListView):
    template_name = "schedules/month_list.html"
    context_object_name = "schedules"

    def get_queryset(self):
        group = current_group(self.request)
        if group is None:
            return Schedule.objects.none()
        return Schedule.objects.filter(group=group).order_by("-date")


def generate_schedule_assignments(request, id):
    if request.method == "POST":
        schedule = visible_schedule(request, id)
        services = Service.objects.filter(group=schedule.group).prefetch_related(
            "tasks__users_with_preferences", "tasks__excludes"
        )

        # parse results from schedule and send to generate
        # Could also take assignments from schedule itself
        payload = json.loads(request.body) or {}
        if "assignments" in payload or "objective" in payload:
            assignment_map = payload.get("assignments") or {}
            objective_name = payload.get("objective") or FairJobsObjective.name
        else:
            assignment_map = payload
            objective_name = FairJobsObjective.name

        scheduler = Scheduler(
            schedule,
            services,
            assignment_map,
            objective=get_objective(objective_name),
        )
        result, assignment_map = scheduler.solve()
        print(f"schedule result: {result}")

        update_assignments_in_schedule(schedule, assignment_map)

        return JsonResponse({"result": result, "assignment_map": assignment_map})


def update_assignments_in_schedule(schedule: Schedule, assignment_map: dict[str, str]):
    """update assignments in database"""
    assignment_to_delete = []
    user_map = {
        user.inverted_name(): user for user in roster_for(schedule.group)
    }

    # Copy so we never mutate the caller's dict while iterating.
    assignment_map = dict(assignment_map)
    for date_task_str, user_name in list(assignment_map.items()):
        if user_name is None:
            assignment_to_delete.append(date_task_str)
            assignment_map.pop(date_task_str, None)
        elif user_name not in user_map:
            # Unknown or still typing. User.inverted_name() is the wire format.
            assignment_map.pop(date_task_str, None)

    # get tasks in batch, create map of task id to task
    # TODO add schedule to service model
    # TODO get tasks from schedule's services
    tasks = Task.objects.filter(group=schedule.group)
    task_map = {task.id: task for task in tasks}

    for date_task_str in assignment_to_delete:
        date_and_task_id = date_task_str.rsplit("-", 1)
        date_str = date_and_task_id[0]
        task_id = date_and_task_id[1]
        task = task_map[task_id]
        print(f"deleting assignment {date_task_str}")
        Assignment.objects.filter(
            schedule=schedule,
            task=task,
            assigned_at=datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.get_current_timezone()
            ),
        ).delete()

    for date_task_str, user_name_inverted in assignment_map.items():
        if user_name_inverted:
            date_and_task_id = date_task_str.rsplit("-", 1)
            task_id = date_and_task_id[1]
            date_str = date_and_task_id[0]
            user = user_map[user_name_inverted]
            task = task_map[task_id]
            date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.get_current_timezone()
            )
            assignment, created = Assignment.objects.update_or_create(
                schedule=schedule,
                task=task,
                assigned_at=date,
                defaults={"user": user},
            )
            # if created:
            #     print(f"created assignment {assignment}")
            # else:
            #     print(f"updated assignment {assignment}")


def update_schedule(request, id):
    """update assignments in database"""
    if request.method == "PUT":
        assignment_map = json.loads(request.body) or {}
        schedule = visible_schedule(request, id)
        print(f"update schedule: {assignment_map}")
        if not schedule:
            print("schedule not found")
            return JsonResponse({"success": False, "error": "Schedule not found"})

        if assignment_map:
            update_assignments_in_schedule(schedule, assignment_map)

        return JsonResponse({"success": True}, status=204)
    return JsonResponse({"success": False}, status=405)


def pdf(request, id):
    if request.method == "GET":
        schedule = visible_schedule(request, id)
        pdf_bytes = render_schedule_pdf(schedule)
        filename = pdf_filename(schedule)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Content-Length"] = len(pdf_bytes)
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        response["X-Content-Type-Options"] = "nosniff"

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "pdf_data": pdf_bytes.decode("latin1"),
                    "filename": filename,
                }
            )

        return response
    return HttpResponse(status=405)


def clear_schedule(request, id):
    """Delete every assignment on a schedule this user can edit."""

    schedule = visible_schedule(request, id)
    if request.method != "DELETE":
        return JsonResponse({"success": False}, status=405)
    schedule.assignments.all().delete()
    return JsonResponse({"success": True})


def delete_schedule(request, id):
    schedule = visible_schedule(request, id)
    if request.method != "POST":
        return HttpResponseRedirect("/schedules/")
    if not schedule.can_be_deleted_by(request.user):
        return HttpResponseForbidden("You cannot delete this schedule.")
    schedule.delete()
    return HttpResponseRedirect("/schedules/", status=303)


def rename_schedule(request, id):
    schedule = visible_schedule(request, id)
    if request.method != "POST":
        return HttpResponseRedirect("/schedules/")
    if not schedule.can_be_deleted_by(request.user):
        return HttpResponseForbidden("You cannot rename this schedule.")
    name = (request.POST.get("name") or "").strip()
    if name:
        schedule.name = name
        schedule.save(update_fields=["name"])
    return HttpResponseRedirect("/schedules/", status=303)


def create_schedule(request):
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        date = request.POST.get("date")
        user = request.user

        group = current_group(request)
        if group is None or not can_schedule(request.user, group):
            return HttpResponseForbidden("You cannot create a schedule.")

        schedule = Schedule.objects.create(
            name=name,
            description=description,
            date=date,
            user=user,
            group=group,
        )

        # Redirect to the schedule detail page
        return HttpResponseRedirect(f"/schedules/{schedule.id}", status=303)

    # If not POST, redirect to the schedules page
    return HttpResponseRedirect("schedules:index")
