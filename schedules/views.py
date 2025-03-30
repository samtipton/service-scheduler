from collections import defaultdict
from django.views import generic
from django.shortcuts import render
from schedules.models import Assignment, AssignmentStats, Service
from schedules.utils import (
    get_month_calendar,
    get_service_weeks,
)


class MonthView(generic.View):
    def get(self, request, year, month):
        month_calendar, month_name = get_month_calendar(year, month)

        services = Service.objects.all()

        service_days = {service.day_of_week for service in services}
        service_weeks = get_service_weeks(month_calendar, service_days)

        assignments = Assignment.objects.filter(
            assigned_at__year=year, assigned_at__month=month
        ).order_by("assigned_at")

        # Create a map of service_name to assignments for tasks in that service
        service_assignments = defaultdict(dict)
        for service in services:
            for assignment in assignments:
                if assignment.task.service_id == service.id:
                    assignment_key = f"{year}-{month}-{assignment.assigned_at.day}-{assignment.task.id}"
                    service_assignments[service.name][assignment_key] = assignment.user

        # Create map of eligible users for each task sorted by assignment delta
        tasks = set()
        for service in services:
            tasks.update(service.tasks.all())

        # Try to get assignment stats from cache
        # Cache miss, calculate assignment stats
        assignment_stats = {}

        # Option 1: Using a subquery with Django ORM
        for task in tasks:
            eligible_users = task.get_eligible_users()

            # Get the latest stats for each eligible user for this task
            latest_stats = (
                AssignmentStats.objects.filter(user__in=eligible_users, task=task)
                .order_by("user", "-created_at")
                .distinct("user")
            )

            for stat in latest_stats:
                assignment_stats[(task.id, stat.user.pk)] = stat

        eligible_users_for_task = defaultdict(list)
        for task in tasks:
            eligible_users = task.get_eligible_users()
            eligible_users_for_task[task.id] = sorted(
                eligible_users,
                key=lambda user: assignment_stats[(task.id, user.pk)].assignment_delta,
            )
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
            "interactive": True,
        }
        return render(request, "schedules/month_schedule.html", context)

    def post(self, request, year, month):
        """
        save assignments, mark as draft until commit?
        """
        pass


class MonthListView(generic.ListView):
    template_name = "schedules/month_list.html"
    context_object_name = "schedule_year_month_list"

    def get_queryset(self):
        from django.db.models import DateField, F, Func

        # Extract year and month from assigned_at dates
        # Then get distinct year/month pairs
        return (
            Assignment.objects.annotate(
                year=Func(
                    F("assigned_at"),
                    function="EXTRACT",
                    template="%(function)s(YEAR FROM %(expressions)s)",
                    output_field=DateField(),
                ),
                month=Func(
                    F("assigned_at"),
                    function="EXTRACT",
                    template="%(function)s(MONTH FROM %(expressions)s)",
                    output_field=DateField(),
                ),
            )
            .values("year", "month")
            .distinct()
            .order_by("-year", "-month")
        )
