from datetime import timedelta, datetime, time
from zoneinfo import ZoneInfo

def business_minutes_between(start, end, policy):
    if end <= start:
        return 0
    zone = ZoneInfo(policy['timezone'])
    a, b = start.astimezone(zone), end.astimezone(zone)
    day, total = a.date(), 0
    holidays = set(policy.get('holidays', []))
    while day <= b.date():
        if day.weekday() < 5 and day.isoformat() not in holidays:
            left = datetime.combine(day, time(policy['start']), zone)
            right = datetime.combine(day + timedelta(days=1), time(0), zone) if policy['end'] == 24 else datetime.combine(day, time(policy['end']), zone)
            total += max(0, (min(b, right) - max(a, left)).total_seconds() / 60)
        day += timedelta(days=1)
    return total

def business_due(start, minutes, policy):
    zone = ZoneInfo(policy['timezone'])
    current = start.astimezone(zone)
    remaining = minutes
    holidays = set(policy.get('holidays', []))
    # Business hours ensure bounded progress; API validates all policy values.
    while remaining > 0:
        day = current.date()
        if current.weekday() >= 5 or day.isoformat() in holidays:
            current = datetime.combine(day + timedelta(days=1), time(policy['start']), zone)
            continue
        opening = datetime.combine(day, time(policy['start']), zone)
        closing = datetime.combine(day + timedelta(days=1), time(0), zone) if policy['end'] == 24 else datetime.combine(day, time(policy['end']), zone)
        current = max(current, opening)
        available = max(0, (closing - current).total_seconds() / 60)
        if remaining <= available:
            return current + timedelta(minutes=remaining)
        remaining -= available
        current = datetime.combine(day + timedelta(days=1), time(policy['start']), zone)
    return current

def snapshot(project):
    return {'timezone': project.timezone, 'start': project.business_start, 'end': project.business_end,
            'holidays': project.holidays, 'firstResponseMinutes': project.first_response_minutes,
            'resolutionMinutes': project.resolution_minutes}
