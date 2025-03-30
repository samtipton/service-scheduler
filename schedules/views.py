from collections import defaultdict
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.views import generic
from django.shortcuts import get_object_or_404, render
from schedules.models import Assignment, AssignmentStats, Schedule, Service
from schedules.utils import (
    get_month_calendar,
    get_service_weeks,
)


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


class MonthView(generic.View):
    def blank_schedule(self, schedule):
        # TODO create assignments for the schedule
        return HttpResponse(f"Schedule: {schedule.name}")

    def get(self, request, id):
        schedule = Schedule.objects.get(id=id)

        if schedule.assignments.count() == 0:
            return self.blank_schedule(schedule)

        year = schedule.date.year
        month = schedule.date.month
        month_calendar, month_name = get_month_calendar(year, month)

        # Prefetch related objects to minimize queries
        services = Service.objects.prefetch_related(
            "tasks__users_with_preferences"
        ).all()
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
