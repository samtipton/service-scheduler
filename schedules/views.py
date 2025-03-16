from django.views import generic
from django.http import HttpResponse
from schedules.models import Assignment
import calendar


def month_view(request, year, month):
    month_name = calendar.month_name[month]
    return HttpResponse(f"Schedule for {month_name} {year}")


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
