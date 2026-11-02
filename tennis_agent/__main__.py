import argparse
import logging
from datetime import datetime, timezone
from .adapters import sources
from .delivery import FileSink
from .http import Http
from .models import consolidate, target_dates

LOG = logging.getLogger(__name__)


def collect(now, adapters=None, http_factory=Http):
    dates = target_dates(now)
    results, all_slots = [], []
    for adapter in adapters if adapters is not None else sources():
        http = http_factory()
        candidate, checked = [], []
        try:
            for day in dates:
                before = len(http.evidence)
                daily = adapter.fetch(day, http)
                if any(s.venue != adapter.name or s.start.date() != day for s in daily):
                    raise ValueError('Adapter returned wrong venue/date')
                candidate.extend(daily)
                checked.append({'date': day.isoformat(), 'offered_60_minute_sessions': sum(
                    (s.end - s.start).total_seconds() == 3600 for s in daily), 'requests': http.evidence[before:]})
            filtered, duplicates = consolidate(candidate, now)
            all_slots.extend(filtered)
            results.append({'venue': adapter.name, 'status': 'ok', 'matching_slots': len(filtered),
                            'duplicates_removed': duplicates, 'dates': checked})
            LOG.info('%s: validated both dates; %d matching sessions', adapter.name, len(filtered))
        except Exception as exc:
            LOG.error('%s: source failed (%s): %s', adapter.name, type(exc).__name__, str(exc)[:160])
            results.append({'venue': adapter.name, 'status': 'error', 'matching_slots': 0,
                            'error': f'Source validation failed ({type(exc).__name__}); availability unknown',
                            'dates': checked, 'requests': http.evidence})
    slots, duplicates = consolidate(all_slots, now)
    ok = bool(results) and all(r['status'] == 'ok' for r in results)
    return {'schema_version': 1, 'checked_at': now.isoformat(), 'timezone': 'Europe/Helsinki',
            'dates': [d.isoformat() for d in dates], 'status': 'complete' if ok else 'partial',
            'validation_passed': ok, 'sources': results, 'duplicates_removed': duplicates,
            'slots': [s.to_dict() for s in slots]}


def main():
    parser = argparse.ArgumentParser(description='Read-only public tennis availability')
    parser.add_argument('--output', default='reports')
    parser.add_argument('--validate', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    report = collect(datetime.now(timezone.utc))
    if args.validate:
        report['validation_passed'] = report['validation_passed'] and all(
            sum(d['offered_60_minute_sessions'] for d in s['dates']) > 0 for s in report['sources'])
    FileSink(args.output).deliver(report)
    return 0 if report['validation_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
