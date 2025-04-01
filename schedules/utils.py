import calendar


def has_services_this_week(week, service_days):
    """
    Check if a week has any services scheduled.

    Args:
        week: A list representing a week from calendar.monthcalendar
        service_days: A set of days (0-6) that have services scheduled

    Returns:
        bool: True if any day in service_days has a non-zero value in the week
    """
    return any(week[day] != 0 for day in service_days if day is not None)


def get_service_weeks(
    calendar_weeks: list[list[int]], service_days: set[int]
) -> list[list[int]]:
    """
    Get weeks that have services scheduled.

    Args:
        calendar_weeks: List of weeks from calendar.monthcalendar
        service_days: A set of days (0-6) that have services scheduled

    Returns:
        list: Weeks that have at least one service scheduled
    """
    return [
        week for week in calendar_weeks if has_services_this_week(week, service_days)
    ]


def get_month_calendar(year, month):
    """
    Get the calendar data for a specific month.

    Args:
        year: Integer representing the year
        month: Integer representing the month (1-12)

    Returns:
        tuple: Calendar data for the month and month name
    """
    calendar.setfirstweekday(calendar.SUNDAY)
    return calendar.monthcalendar(year, month), calendar.month_name[month]


def get_service_day(service_week: list[list[int]], service_days, service_day):
    """
    get the calendar day for a given a service week and a service day.
    if service_day is None, return the first calendar day in service_week that is
    also in service_days.

    Must be same logic as in schedule_tags#get_service_day
    """
    if service_day is not None:
        return service_week[service_day]
    else:
        for i, day in enumerate(service_week):
            if i in service_days and day != 0:
                return day
    return None
