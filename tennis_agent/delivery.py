"""Modular report delivery; no assumed ChatGPT posting integration."""
import json
from pathlib import Path
from typing import Protocol


class ReportSink(Protocol):
    def deliver(self, report: dict) -> None: ...


class FileSink:
    def __init__(self, directory):
        self.directory = Path(directory)

    def deliver(self, report):
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / 'availability.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        lines = ['# Espoo indoor tennis availability', '', f"Checked: {report['checked_at']}",
                 f"Dates (Europe/Helsinki): {', '.join(report['dates'])}", f"Status: {report['status']}", '',
                 'Availability is a snapshot. Unknown prices must be checked in the booking calendar.', '',
                 '| Venue | Source status | Matching slots |', '|---|---|---:|']
        for s in report['sources']:
            lines.append(f"| {s['venue']} | {s['status']} | {s['matching_slots']} |")
        lines += ['', '| Venue | Court | Date | Start | End | EUR | Calendar |', '|---|---|---|---|---|---|---|']
        for s in report['slots']:
            lines.append(f"| {s['venue']} | {s['court']} | {s['date']} | {s['start_time']} | {s['end_time']} | {s['price'] or 'Unknown'} | [Open]({s['booking_url']}) |")
        lines += ['', 'Failed sources have unknown availability; a failure never means no courts are free.']
        (self.directory / 'availability.md').write_text('\n'.join(lines) + '\n')
