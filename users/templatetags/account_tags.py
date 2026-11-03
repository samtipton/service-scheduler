from django import template

from users.access import admin_groups

register = template.Library()


@register.filter
def is_group_admin(user):
    return admin_groups(user).exists()
