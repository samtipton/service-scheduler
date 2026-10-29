from collections import defaultdict
import json
import pdfkit
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
from config.settings import BASE_DIR
from schedules.models import Assignment, AssignmentStats, Schedule, Service, Task
from schedules.services.fairness import build_fairness_window
from schedules.services.objectives import (
    CatchUpShareObjective,
    FairJobsObjective,
    get_objective,
)
from schedules.services.scheduler import Scheduler
from schedules.utils import (
    get_month_calendar,
    get_service_weeks,
)
from django.views.decorators.csrf import csrf_exempt
import os


class MonthView(generic.View):

    def get(self, request, id):
        schedule = Schedule.objects.get(id=id)

        year = schedule.date.year
        month = schedule.date.month
        month_calendar, month_name = get_month_calendar(year, month)

        # TODO consider moving these queries to ScheduleManager
        # Prefetch related objects to minimize queries

        # TODO check if we can prefetch tasks here
        services = Service.objects.prefetch_related(
            "tasks__users_with_preferences", "tasks__excludes"
        ).all()

        assignments = schedule.assignments.select_related(
            "task", "user", "task__service"
        )
        assignment_stats = AssignmentStats.objects.filter(
            schedule=schedule if assignments.count() > 0 else schedule.base_schedule
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
                schedule, services, get_user_model().objects.filter(is_active=True)
            )

        # create map of eligible users for each task sorted by assignment delta
        # or FairJobs ranking (count_so_far − target)
        eligible_users_for_task = defaultdict(list)
        for service in services:
            for task in service.tasks.all():
                eligible_users = list(task.get_eligible_users())
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
        return Schedule.objects.all().order_by("-date")


# TODO add csrf
@csrf_exempt
def generate_schedule_assignments(request, id):
    if request.method == "POST":
        schedule = Schedule.objects.get(id=id)
        services = Service.objects.prefetch_related(
            "tasks__users_with_preferences", "tasks__excludes"
        ).all()

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
        user.inverted_name(): user for user in get_user_model().objects.all()
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
    tasks = Task.objects.all()
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


# TODO add csrf
@csrf_exempt
def update_schedule(request, id):
    """update assignments in database"""
    if request.method == "PUT":
        assignment_map = json.loads(request.body) or {}
        schedule = Schedule.objects.get(id=id)
        print(f"update schedule: {assignment_map}")
        if not schedule:
            print("schedule not found")
            return JsonResponse({"success": False, "error": "Schedule not found"})

        if assignment_map:
            update_assignments_in_schedule(schedule, assignment_map)

        return JsonResponse({"success": True}, status=204)
    return JsonResponse({"success": False}, status=405)


# TODO move views into their own files
@csrf_exempt
def pdf(request, id):
    if request.method == "GET":
        schedule = Schedule.objects.get(id=id)

        year = schedule.date.year
        month = schedule.date.month
        month_calendar, month_name = get_month_calendar(year, month)

        # TODO consider moving these queries to ScheduleManager
        # Prefetch related objects to minimize queries
        # TODO ask about how reusable bits of view context are encapsulated in django

        # TODO check if we can prefetch tasks here
        services = Service.objects.all()

        assignments = schedule.assignments.select_related(
            "task", "user", "task__service"
        )

        service_days = {service.day_of_week for service in services}
        service_weeks = get_service_weeks(month_calendar, service_days)

        # Create a map of service_name to assignments for tasks in that service
        service_assignments = defaultdict(dict)
        for assignment in assignments:
            assignment_key = (
                f"{year}-{month}-{assignment.assigned_at.day}-{assignment.task.id}"
            )
            service_assignments[assignment.task.service.name][
                assignment_key
            ] = assignment.user

        # Read the CSS file
        app_static_dir = os.path.join(BASE_DIR, "schedules", "static", "schedules")
        css_path = os.path.join(app_static_dir, "schedule.css")

        if os.path.exists(css_path):
            with open(css_path, "r") as f:
                css_content = f.read()
        else:
            # Fallback to empty CSS if file not found
            css_content = ""

        context = {
            "year": year,
            "month": month,
            "month_name": month_name,
            "services": services,
            "service_days": service_days,
            "service_weeks": service_weeks,
            "service_assignments": service_assignments,
            "css_content": css_content,
            "col_span": len(service_weeks) + len(service_weeks) + 1,
        }
        html_content = render(
            request, "schedules/pdf_month_schedule.html", context
        ).content.decode("utf-8")
        options = {
            "page-size": "Legal",
            "orientation": "Landscape",
            "encoding": "UTF-8",
            "no-outline": None,
            "quiet": "",
            "disable-external-links": "",
            "disable-internal-links": "",
            "enable-local-file-access": "",
        }
        pdf = pdfkit.from_string(html_content, False, options=options)

        # return pdf as attachment, content-dipsosition attachment filename
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="schedule-{month}-{year}.pdf"'
        )
        response["Content-Length"] = len(pdf)
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"

        # Add X-Content-Type-Options to prevent MIME type sniffing
        response["X-Content-Type-Options"] = "nosniff"

        # If this is an AJAX request, we need to handle it differently
        # Currently not requeseting with ajax,
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            # For AJAX requests, we'll return a JSON response with the PDF data
            return JsonResponse(
                {
                    "pdf_data": pdf.decode("latin1"),
                    "filename": f"schedule-{month}-{year}.pdf",
                }
            )

        return response
    return HttpResponse(status=405)


# TODO add csrf
@csrf_exempt
def clear_schedule(request, id):
    """commit assignments to database"""

    schedule = Schedule.objects.get(id=id)
    if request.method == "DELETE":
        # only allow the user who created the schedule to clear it
        if request.user == schedule.user:
            print("clear schedule")
            # get schedule and delete all assignments
            schedule.assignments.all().delete()
            return JsonResponse({"success": True})
        else:
            return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)
    return JsonResponse({"success": False}, status=405)


def delete_schedule(request, id):
    schedule = get_object_or_404(Schedule, id=id)
    if request.method != "POST":
        return HttpResponseRedirect("/schedules/")
    if not schedule.can_be_deleted_by(request.user):
        return HttpResponseForbidden("You cannot delete this schedule.")
    schedule.delete()
    return HttpResponseRedirect("/schedules/", status=303)


def rename_schedule(request, id):
    schedule = get_object_or_404(Schedule, id=id)
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

        base_schedule_id = request.POST.get("base_schedule")
        base_schedule = None
        if base_schedule_id:
            base_schedule = get_object_or_404(Schedule, id=base_schedule_id)

        # Create new schedule
        schedule = Schedule.objects.create(
            name=name,
            description=description,
            date=date,
            user=user,
            base_schedule=base_schedule,
        )

        # Redirect to the schedule detail page
        return HttpResponseRedirect(f"/schedules/{schedule.id}", status=303)

    # If not POST, redirect to the schedules page
    return HttpResponseRedirect("schedules:index")
