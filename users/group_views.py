from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from users.access import (
    SESSION_GROUP,
    can_admin,
    can_create_group,
    current_group,
    visible_groups,
)
from users.models import Group, Membership


def _back(request):
    target = request.META.get("HTTP_REFERER") or ""
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect("schedules:index")


def _roster_context(request, error=""):
    group = current_group(request)
    memberships = []
    admin_count = 0
    if group is not None:
        memberships = list(
            Membership.objects.filter(group=group)
            .select_related("user")
            .order_by("user__last_name", "user__first_name", "user__email")
        )
        admin_count = sum(1 for row in memberships if row.role == Membership.ADMIN)
    return {
        "group": group,
        "memberships": memberships,
        "admin_count": admin_count,
        "can_manage": group is not None and can_admin(request.user, group),
        "roles": Membership.ROLE_CHOICES,
        "error": error,
    }


@login_required
def group_roster(request):
    return render(request, "users/group.html", _roster_context(request))


@login_required
@require_POST
def group_select(request):
    group = get_object_or_404(visible_groups(request.user), pk=request.POST.get("group"))
    request.session[SESSION_GROUP] = group.id
    return _back(request)


@login_required
@require_POST
def group_create(request):
    if not can_create_group(request.user):
        return HttpResponseForbidden("You cannot create a group.")
    name = (request.POST.get("name") or "").strip()
    if not name:
        return _back(request)
    group = Group.objects.create(name=name[:100])
    Membership.objects.create(
        user=request.user, group=group, role=Membership.ADMIN
    )
    request.session[SESSION_GROUP] = group.id
    return redirect("schedules:index")


def _managed_group(request):
    group = current_group(request)
    if group is None or not can_admin(request.user, group):
        return None
    return group


@login_required
@require_POST
def group_add(request):
    group = _managed_group(request)
    if group is None:
        return HttpResponseForbidden("You cannot add people to this group.")
    email = (request.POST.get("email") or "").strip()
    role = Membership.normalize_role(request.POST.get("role"))
    user = get_user_model().objects.filter(email__iexact=email).first()
    if user is None:
        return render(
            request,
            "users/group.html",
            _roster_context(
                request,
                error="No login with that email yet. Invite links are not built yet.",
            ),
        )
    Membership.objects.get_or_create(
        user=user, group=group, defaults={"role": role}
    )
    return redirect("group_roster")


@login_required
@require_POST
def group_role(request):
    group = _managed_group(request)
    if group is None:
        return HttpResponseForbidden("You cannot change roles in this group.")
    membership = get_object_or_404(Membership, pk=request.POST.get("membership"), group=group)
    role = request.POST.get("role")
    if role not in (Membership.USER, Membership.SCHEDULER, Membership.ADMIN):
        return redirect("group_roster")
    if membership.role == Membership.ADMIN and role != Membership.ADMIN:
        admins = Membership.objects.filter(group=group, role=Membership.ADMIN).count()
        if admins < 2:
            return redirect("group_roster")
    membership.role = role
    membership.save(update_fields=["role"])
    return redirect("group_roster")


@login_required
@require_POST
def group_remove(request):
    group = _managed_group(request)
    if group is None:
        return HttpResponseForbidden("You cannot remove people from this group.")
    membership = get_object_or_404(Membership, pk=request.POST.get("membership"), group=group)
    if membership.role == Membership.ADMIN:
        admins = Membership.objects.filter(group=group, role=Membership.ADMIN).count()
        if admins < 2:
            return redirect("group_roster")
    membership.delete()
    return redirect("group_roster")


@login_required
@require_POST
def group_delete(request):
    group = _managed_group(request)
    if group is None:
        return HttpResponseForbidden("You cannot delete this group.")
    group_id = group.id
    group.delete()
    if request.session.get(SESSION_GROUP) == group_id:
        request.session.pop(SESSION_GROUP, None)
    return redirect("schedules:index")
