from django.http import Http404
from django.shortcuts import get_object_or_404

from schedules.models import Schedule
from users.access import can_schedule, can_view


def visible_schedule(request, schedule_id):
    schedule = get_object_or_404(Schedule, pk=schedule_id)
    if not can_view(request.user, schedule.group_id):
        raise Http404()
    return schedule


def editor_schedule(request, schedule_id):
    """The schedule, or 403 when this person can see it but not change it."""
    schedule = visible_schedule(request, schedule_id)
    if not can_schedule(request.user, schedule.group_id):
        from django.http import HttpResponseForbidden

        return schedule, HttpResponseForbidden("You cannot change this schedule.")
    return schedule, None
