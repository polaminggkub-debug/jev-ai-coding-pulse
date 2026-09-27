"""Offline build metadata, with the next scheduled run derived from workflow cron."""
import datetime as dt
import json
import re
from pathlib import Path

UTC = dt.timezone.utc


def cron_values(field, maximum):
    values = set()
    for part in field.split(','):
        base, _, step = part.partition('/')
        stride = int(step or 1)
        if stride < 1:
            raise ValueError('Invalid cron step')
        if base == '*':
            start, end = 0, maximum
        elif '-' in base:
            start, end = map(int, base.split('-'))
        else:
            start = end = int(base)
        if not 0 <= start <= end <= maximum:
            raise ValueError('Invalid cron range')
        values.update(range(start, end + 1, stride))
    return sorted(values)


def next_run(workflow, now):
    schedules = re.findall(r'cron:\s*[\"\']([^\"\']+)[\"\']', Path(workflow).read_text())
    candidates = []
    for schedule in schedules:
        minute, hour, day, month, weekday = schedule.split()
        if (day, month, weekday) != ('*', '*', '*'):
            raise ValueError('Pulse update metadata requires a daily cron schedule')
        for offset in (0, 1):
            date = (now + dt.timedelta(days=offset)).date()
            for h in cron_values(hour, 23):
                for m in cron_values(minute, 59):
                    candidate = dt.datetime.combine(date, dt.time(h, m), UTC)
                    if candidate > now:
                        candidates.append(candidate)
    return min(candidates).isoformat().replace('+00:00', 'Z') if candidates else None


def metadata(rows, days, source, workflow, now=None):
    dates = days or sorted({row['date'] for row in rows if row.get('date')})
    updated = now or dt.datetime.now(UTC).replace(microsecond=0)
    stats_path = Path(source) / 'run-stats.json'
    stats = json.loads(stats_path.read_text()) if stats_path.is_file() else {}
    return {
        'days': dates, 'startDate': dates[0] if dates else None,
        'endDate': dates[-1] if dates else None,
        'updatedAt': updated.isoformat().replace('+00:00', 'Z'),
        'nextUpdateAt': next_run(workflow, updated), 'runStats': stats,
    }
