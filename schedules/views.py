from collections import defaultdict
import json
from datetime import datetime
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views import generic
from django.shortcuts import get_object_or_404, render
from django.contrib.auth import get_user_model
from schedules.models import Assignment, AssignmentStats, Schedule, Service, Task
from schedules.services.scheduler import Scheduler
from schedules.utils import (
    get_month_calendar,
    get_service_weeks,
)
from django.views.decorators.csrf import csrf_exempt


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

        # create map of eligible users for each task sorted by assignment delta
        eligible_users_for_task = defaultdict(list)
        for service in services:
            for task in service.tasks.all():
                eligible_users = task.get_eligible_users()
                sorted_users = sorted(
                    eligible_users,
                    key=lambda user: assignment_stats_map.get((task.id, user.pk), 1),
                )
                eligible_users_for_task[task.id] = sorted_users
        eligible_users_for_task.default_factory = None

        context = {
            "year": year,
            "month": month,
            "services": services,
            "month_name": month_name,
            "service_days": service_days,
            "service_weeks": service_weeks,
            "service_assignments": service_assignments,
            "eligible_users_for_task": eligible_users_for_task,
            "col_span": len(service_weeks) + len(service_weeks) + 1,
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


@csrf_exempt
def generate_schedule_assignments(request, id):
    if request.method == "POST":
        schedule = Schedule.objects.get(id=id)
        services = Service.objects.prefetch_related(
            "tasks__users_with_preferences", "tasks__excludes"
        ).all()

        # parse results from schedule and send to generate
        assignment_map = json.loads(request.body) or {}

        scheduler = Scheduler(schedule, services, assignment_map)
        result, assignment_map = scheduler.solve()

        return JsonResponse({"result": result, "assignment_map": assignment_map})


@csrf_exempt
def save_schedule(request, id):
    """save assignments to database"""
    if request.method == "PUT":
        assignment_map = json.loads(request.body) or {}
        schedule = Schedule.objects.get(id=id)
        print(f"save schedule: {schedule.name} id:{id}")
        if not schedule:
            print("schedule not found")
            return JsonResponse({"success": False, "error": "Schedule not found"})

        if assignment_map:
            # extract first names and last names from assignment map
            first_names = []
            last_names = []
            for user_name_inverted in assignment_map.values():
                first_names.append(user_name_inverted.split(", ")[1])
                last_names.append(user_name_inverted.split(", ")[0])
            # get users in batch, create map of user inverted name to user
            users = get_user_model().objects.filter(
                first_name__in=first_names, last_name__in=last_names
            )
            user_map = {user.inverted_name(): user for user in users}

            # get tasks in batch, create map of task id to task
            # TODO add schedule to service
            # TODO get tasks from schedule's services
            tasks = Task.objects.all()
            task_map = {task.id: task for task in tasks}

            for date_task_str, user_name_inverted in assignment_map.items():
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
                if created:
                    print(f"created assignment {assignment}")
                else:
                    print(f"updated assignment {assignment}")

        return JsonResponse({"success": True})
    return JsonResponse({"success": False}, status=405)


@csrf_exempt
def clear_schedule(request, id):
    """commit assignments to database"""
    if request.method == "DELETE":
        print("clear schedule")
        # get schedule and delete all assignments
        schedule = Schedule.objects.get(id=id)
        schedule.assignments.all().delete()
        return JsonResponse({"success": True})
    return JsonResponse({"success": False}, status=405)


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
        return HttpResponseRedirect(f"/schedules/{schedule.id}")

    # If not POST, redirect to the schedules page
    return HttpResponseRedirect("schedules:index")
