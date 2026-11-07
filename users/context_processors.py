from users.access import can_create_group, can_schedule, current_group, visible_groups


def group_nav(request):
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return {}
    group = current_group(request)
    return {
        "current_group": group,
        "user_groups": visible_groups(user).order_by("name", "id"),
        "can_edit_schedules": can_schedule(user, group),
        "can_create_group": can_create_group(user),
    }
