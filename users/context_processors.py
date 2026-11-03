from users.access import current_group, visible_groups


def group_nav(request):
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return {}
    return {
        "current_group": current_group(request),
        "user_groups": visible_groups(user).order_by("name", "id"),
    }
