"""Use four UTC candidates; select the two valid Helsinki schedules, including DST."""
import argparse
from datetime import datetime, timezone, time
from .models import HELSINKI


def due(cron, now):
    day = now.astimezone(HELSINKI).date()
    expected = {f'0 {datetime.combine(day, time(hour), HELSINKI).astimezone(timezone.utc).hour} * * *' for hour in (9, 15)}
    return cron in expected


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--event', required=True)
    parser.add_argument('--cron', default='')
    args = parser.parse_args()
    print('true' if args.event != 'schedule' or due(args.cron, datetime.now(timezone.utc)) else 'false')
