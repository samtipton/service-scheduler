import os
from collections import defaultdict

import pdfkit
from django.template.loader import render_to_string

from config.settings import BASE_DIR
from schedules.models import Service
from schedules.utils import get_month_calendar, get_service_weeks

PDF_OPTIONS = {
    "page-size": "Legal",
    "orientation": "Landscape",
    "encoding": "UTF-8",
    "no-outline": None,
    "quiet": "",
    "disable-external-links": "",
    "disable-internal-links": "",
    "enable-local-file-access": "",
}


def pdf_filename(schedule):
    return f"schedule-{schedule.date.month}-{schedule.date.year}.pdf"


def build_pdf_context(schedule):
    year = schedule.date.year
    month = schedule.date.month
    month_calendar, month_name = get_month_calendar(year, month)
    services = Service.objects.all()
    assignments = schedule.assignments.select_related("task", "user", "task__service")
    service_days = {service.day_of_week for service in services}
    service_weeks = get_service_weeks(month_calendar, service_days)

    service_assignments = defaultdict(dict)
    for assignment in assignments:
        assignment_key = (
            f"{year}-{month}-{assignment.assigned_at.day}-{assignment.task.id}"
        )
        service_assignments[assignment.task.service.name][assignment_key] = (
            assignment.user
        )

    css_path = os.path.join(BASE_DIR, "schedules", "static", "schedules", "schedule.css")
    if os.path.exists(css_path):
        with open(css_path, "r") as f:
            css_content = f.read()
    else:
        css_content = ""

    return {
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


def render_schedule_pdf(schedule):
    """Legal landscape PDF bytes. No browser and no calendar page."""
    html_content = render_to_string(
        "schedules/pdf_month_schedule.html", build_pdf_context(schedule)
    )
    return pdfkit.from_string(html_content, False, options=PDF_OPTIONS)
