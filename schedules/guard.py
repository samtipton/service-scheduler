from django.http import Http404
from django.shortcuts import get_object_or_404

from schedules.models import Schedule
from users.access import can_schedule


def visible_schedule(request, schedule_id):
    schedule = get_object_or_404(Schedule, pk=schedule_id)
    if not can_schedule(request.user, schedule.group_id):
        raise Http404()
    return schedule
