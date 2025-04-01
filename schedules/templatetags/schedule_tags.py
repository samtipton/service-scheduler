from django import template

register = template.Library()


@register.filter
def addstr(arg1, arg2):
    """concatenate arg1 & arg2"""
    return str(arg1) + str(arg2)


@register.filter
def get_item(lst, index):
    """
    Template filter to access a list item by index.
    Usage: {{ my_list|get_item:index }}
    """
    try:
        return lst[index]
    except (IndexError, TypeError, KeyError):
        return None


@register.simple_tag
def get_service_day(service_week, service_days, service_day):
    """
    Template filter to get the calendar day for a given a service week and a service day.
    if service_day is None, return the first calendar day in service_week that is also in service_days.
    Usage: {% get_service_day service_week service_days service_day %}
    """
    if service_day is not None:
        return service_week[service_day]
    else:
        for i, day in enumerate(service_week):
            if i in service_days and day != 0:
                return day
    return None


@register.filter
def first_service_day_of_week(service_week, service_days):
    """
    Template filter to get the first day of the week that has a value != 0 that is also in service_days.
    Usage: {{ week|first_service_day_of_week: service_days }}
    Returns the first non-zero day in the week that is also in service_days, or None if all days are zero.
    """
    for i, day in enumerate(service_week):
        if day != 0 and i in service_days:
            return day
    return None
