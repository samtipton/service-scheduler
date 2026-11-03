from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from messaging.forms import EmailTemplateForm
from messaging.models import EmailTemplate, SentEmail
from messaging.services.brevo import BrevoError
from messaging.services.recipients import active_roster, roster_label
from messaging.services.send import (
    NotOneAddress,
    parse_test_address,
    rendered_message,
    send_schedule_email,
    send_test_email,
)
from schedules.guard import visible_schedule
from schedules.models import Schedule
from users.access import current_group, visible_groups


def _page(section):
    return {"section": section}


def _visible_schedules(request):
    group = current_group(request)
    if group is None:
        return Schedule.objects.none()
    return Schedule.objects.filter(group=group).order_by("-date")


def _compose_context(request, fixed_schedule=None):
    if fixed_schedule is not None:
        roster = active_roster(fixed_schedule.group)
    else:
        group = current_group(request)
        roster = active_roster(group) if group is not None else []
    return {
        "schedules": _visible_schedules(request),
        "templates": EmailTemplate.objects.all(),
        "roster": list(roster),
        "fixed_schedule": fixed_schedule,
    }


def new_email(request):
    return render(
        request,
        "messaging/new_email.html",
        {**_page("new"), **_compose_context(request)},
    )


def compose(request):
    schedule = visible_schedule(request, request.GET.get("schedule"))
    return render(
        request,
        "messaging/_compose.html",
        _compose_context(request, fixed_schedule=schedule),
    )


def template_list(request):
    return render(
        request,
        "messaging/template_list.html",
        {**_page("templates"), "templates": EmailTemplate.objects.all()},
    )


def template_create(request):
    form = EmailTemplateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        template = form.save(commit=False)
        template.created_by = request.user
        template.save()
        return redirect("messaging:template_list")
    return render(
        request,
        "messaging/template_form.html",
        {**_page("templates"), "form": form, "heading": "New template"},
    )


def template_edit(request, pk):
    template = get_object_or_404(EmailTemplate, pk=pk)
    form = EmailTemplateForm(request.POST or None, instance=template)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("messaging:template_list")
    return render(
        request,
        "messaging/template_form.html",
        {**_page("templates"), "form": form, "heading": template.name},
    )


def sent_list(request):
    return render(
        request,
        "messaging/sent_list.html",
        {
            **_page("sent"),
            "sent_emails": SentEmail.objects.filter(
                schedule__in=_visible_schedules(request)
            ).select_related("schedule"),
        },
    )


def sent_detail(request, pk):
    sent = get_object_or_404(
        SentEmail.objects.select_related("schedule", "sent_by", "template"),
        pk=pk,
        schedule__group__in=visible_groups(request.user),
    )
    return render(
        request,
        "messaging/sent_detail.html",
        {**_page("sent"), "sent": sent},
    )


def reminders(request):
    return render(request, "messaging/reminders.html", _page("reminders"))


@require_POST
def preview(request):
    schedule = visible_schedule(request, request.POST.get("schedule"))
    template = get_object_or_404(EmailTemplate, pk=request.POST.get("template"))
    subject, body = rendered_message(schedule, template)
    return JsonResponse(
        {
            "subject": subject,
            "body": body,
            "recipients": [
                roster_label(user) for user in active_roster(schedule.group)
            ],
        }
    )


def _send_result(request, schedule, template, sent=None, message="", test_email=""):
    ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if message:
        if ajax:
            return JsonResponse({"error": message}, status=400)
        context = {**_page("new"), **_compose_context(request), "error": message}
        context["selected_schedule"] = str(schedule.pk)
        context["selected_template"] = str(template.pk)
        context["test_email"] = test_email
        return render(request, "messaging/new_email.html", context, status=400)
    detail = redirect("messaging:sent_detail", pk=sent.pk)
    if ajax:
        return JsonResponse({"url": detail.url})
    return detail


@require_POST
def send(request):
    schedule = visible_schedule(request, request.POST.get("schedule"))
    template = get_object_or_404(EmailTemplate, pk=request.POST.get("template"))
    try:
        sent = send_schedule_email(schedule, template, request.user)
    except BrevoError as exc:
        return _send_result(request, schedule, template, message=str(exc))
    return _send_result(request, schedule, template, sent=sent)


@require_POST
def send_test(request):
    schedule = visible_schedule(request, request.POST.get("schedule"))
    template = get_object_or_404(EmailTemplate, pk=request.POST.get("template"))
    raw = request.POST.get("test_email", "")
    try:
        address = parse_test_address(raw)
        sent = send_test_email(schedule, template, request.user, address)
    except NotOneAddress as exc:
        return _send_result(request, schedule, template, message=str(exc), test_email=raw)
    except BrevoError as exc:
        return _send_result(
            request, schedule, template, message=str(exc), test_email=raw
        )
    return _send_result(request, schedule, template, sent=sent)


def messaging_home(request):
    return redirect("messaging:new_email")
