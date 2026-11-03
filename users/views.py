from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from users.access import admin_groups, can_admin
from users.mail import send_password_mail
from users.models import Membership


@login_required
def member_list(request):
    groups = admin_groups(request.user)
    if not groups.exists():
        return HttpResponseForbidden("You cannot manage logins.")
    memberships = (
        Membership.objects.filter(group__in=groups)
        .select_related("user", "group")
        .order_by("group__name", "user__last_name", "user__email")
    )
    return render(
        request,
        "users/members.html",
        {
            "memberships": memberships,
            "groups": groups,
            "roles": Membership.ROLE_CHOICES,
        },
    )


@login_required
@require_POST
def member_create(request):
    groups = admin_groups(request.user)
    group = get_object_or_404(groups, pk=request.POST.get("group"))
    email = (request.POST.get("email") or "").strip()
    first_name = (request.POST.get("first_name") or "").strip()
    last_name = (request.POST.get("last_name") or "").strip()
    role = request.POST.get("role") or Membership.SCHEDULER
    if role not in (Membership.ADMIN, Membership.SCHEDULER):
        role = Membership.SCHEDULER
    if not email or not first_name or not last_name:
        return redirect("members")

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    created = False
    if user is None:
        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=None,
        )
        user.set_unusable_password()
        user.is_staff = False
        user.is_superuser = False
        user.save()
        created = True
    Membership.objects.get_or_create(
        user=user, group=group, defaults={"role": role}
    )
    # A failed first send leaves an unusable password. Submitting again resends.
    # An existing login that already has a password is not mailed.
    if created or not user.has_usable_password():
        send_password_mail(request, user)
    return redirect("members")


@login_required
@require_POST
def member_deactivate(request, pk):
    membership = get_object_or_404(Membership.objects.select_related("user", "group"), pk=pk)
    if not can_admin(request.user, membership.group_id):
        return HttpResponseForbidden("You cannot manage logins.")
    if membership.user_id == request.user.id:
        return redirect("members")
    membership.user.is_active = False
    membership.user.save(update_fields=["is_active"])
    return redirect("members")
