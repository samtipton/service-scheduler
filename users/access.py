from django.contrib.auth import get_user_model

from users.models import Group, Membership


def sole_group():
    """The only congregation, when the database has exactly one.

    Seed commands use this when they have to attach rows to that congregation.
    Zero groups, or more than one, returns None. This does not create a group.
    """
    groups = list(Group.objects.order_by("id")[:2])
    if len(groups) != 1:
        return None
    return groups[0]


SESSION_GROUP = "group_id"


def current_group(request):
    """The group selected in the top bar.

    A person in one group gets that group. A person in several keeps the
    last choice that is still one of theirs. A person in none gets None.
    """
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return None
    groups = list(visible_groups(user).order_by("name", "id"))
    if not groups:
        request.session.pop(SESSION_GROUP, None)
        return None
    chosen_id = request.session.get(SESSION_GROUP)
    chosen = next((group for group in groups if group.id == chosen_id), None)
    if chosen is None:
        chosen = groups[0]
        request.session[SESSION_GROUP] = chosen.id
    return chosen


def visible_groups(user):
    if not getattr(user, "is_authenticated", False):
        return Group.objects.none()
    return Group.objects.filter(memberships__user=user).distinct()


def admin_groups(user):
    if not getattr(user, "is_authenticated", False):
        return Group.objects.none()
    return Group.objects.filter(
        memberships__user=user, memberships__role=Membership.ADMIN
    ).distinct()


def _group_id(group):
    if group is None:
        return None
    return group.pk if hasattr(group, "pk") else group


def _has_role(user, group, roles):
    """Membership decides. Staff and superuser use Django admin, not this check."""
    group_id = _group_id(group)
    if group_id is None or not getattr(user, "is_authenticated", False):
        return False
    return Membership.objects.filter(
        user=user,
        group_id=group_id,
        role__in=roles,
    ).exists()


def can_view(user, group):
    """Open this group's schedules. A read-only member is included."""
    return _has_role(
        user,
        group,
        [Membership.USER, Membership.SCHEDULER, Membership.ADMIN],
    )


def can_schedule(user, group):
    """Create or change this group's schedules. A read-only member is not."""
    return _has_role(
        user,
        group,
        [Membership.SCHEDULER, Membership.ADMIN],
    )


def can_create_group(user):
    """An admin can open another congregation. A scheduler cannot.

    Someone with no membership yet still can. That is how the first group
    gets its admin. Staff can too.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff or user.is_superuser:
        return True
    roles = set(
        Membership.objects.filter(user=user).values_list("role", flat=True)
    )
    if not roles:
        return True
    return Membership.ADMIN in roles


def can_admin(user, group):
    group_id = _group_id(group)
    if group_id is None or not getattr(user, "is_authenticated", False):
        return False
    return Membership.objects.filter(
        user=user, group_id=group_id, role=Membership.ADMIN
    ).exists()


def roster_for(group):
    """Active people the solver may assign.

    A group with memberships uses those members. A group with none, which is
    how the test database starts, still uses every active user.
    """
    User = get_user_model()
    active = User.objects.filter(is_active=True)
    group_id = _group_id(group)
    if group_id is None:
        return active
    members = active.filter(memberships__group_id=group_id)
    if members.exists():
        return members
    return active
