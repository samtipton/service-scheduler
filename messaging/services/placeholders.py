def fill_placeholders(text, schedule):
    """Replace {{month}} and {{year}}. Leave every other character as typed."""
    month = schedule.date.strftime("%B")
    year = str(schedule.date.year)
    return text.replace("{{month}}", month).replace("{{year}}", year)
