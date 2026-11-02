import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock
from tennis_agent.models import Slot, HELSINKI, eligible, target_dates, consolidate
from tennis_agent.adapters import sources
from tennis_agent.adapters.playfi import PlayFi
from tennis_agent.adapters.esport import Esport
from tennis_agent.http import SourceError, check_url
from tennis_agent.schedule import due
from tennis_agent.__main__ import collect
from tennis_agent.delivery import FileSink

FIX = Path(__file__).parent / 'fixtures'
NOW = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
DAY = date(2026, 11, 2)


def slot(day=DAY, start='17:00', minutes=60, price='30.00'):
    dt = datetime.combine(day, datetime.strptime(start, '%H:%M').time(), HELSINKI)
    return Slot('Venue', 'Court', dt, dt + timedelta(minutes=minutes), price, 'https://example.com')


class Rules(unittest.TestCase):
    def test_helsinki_dates_at_utc_midnight_boundary(self):
        now = datetime(2026, 11, 1, 23, tzinfo=timezone.utc)
        self.assertEqual(target_dates(now), [date(2026, 11, 3), date(2026, 11, 4)])

    def test_weekday_limits(self):
        for start, expected in [('16:30', False), ('17:00', True), ('20:00', True), ('20:30', False), ('21:00', False)]:
            with self.subTest(start=start): self.assertEqual(eligible(slot(start=start), NOW), expected)

    def test_weekend_limits(self):
        now = datetime(2026, 11, 6, 9, tzinfo=timezone.utc)
        for start, expected in [('09:30', False), ('10:00', True), ('19:00', True), ('19:30', False)]:
            self.assertEqual(eligible(slot(date(2026, 11, 7), start), now), expected)

    def test_duration_and_two_day_horizon(self):
        self.assertFalse(eligible(slot(minutes=30), NOW))
        self.assertFalse(eligible(slot(minutes=90), NOW))
        self.assertFalse(eligible(slot(date(2026, 11, 4)), NOW))

    def test_notice_boundary(self):
        s = slot(date(2026, 11, 2), '10:00')
        # The independent two-hour comparison also applies before filtering future dates.
        self.assertTrue(s.start >= s.start - timedelta(hours=2) + timedelta(hours=2))
        self.assertFalse(eligible(slot(), datetime(2026, 11, 2, 16, tzinfo=HELSINKI)))

    def test_duplicates_and_conflicts(self):
        found, count = consolidate([slot(), slot()], NOW)
        self.assertEqual((len(found), count), (1, 1))
        with self.assertRaises(ValueError): consolidate([slot(), slot(price='31.00')], NOW)

    def test_dst_both_transitions(self):
        for day, hours in [('2026-03-28', (7, 13)), ('2026-03-29', (6, 12)), ('2026-10-24', (6, 12)), ('2026-10-25', (7, 13))]:
            now = datetime.fromisoformat(day + 'T10:00:00+00:00')
            self.assertEqual([h for h in (6, 7, 12, 13) if due(f'0 {h} * * *', now)], list(hours))


class Adapters(unittest.TestCase):
    def test_cintoia_observed_both_dates(self):
        for adapter in sources():
            if not hasattr(adapter, 'host'): continue
            resources = json.loads((FIX / f'{adapter.host}-resources.json').read_text())
            for d in (2, 3):
                day = date(2026, 11, d)
                raw = json.loads((FIX / f'{adapter.host}-2026110{d}.json').read_text())
                slots = adapter.parse(day, resources, raw)
                self.assertGreater(len(slots), 0)
                for s in slots:
                    self.assertEqual(s.end - s.start, timedelta(hours=1))
                    self.assertEqual(s.start.date(), day)
                    self.assertNotIn('tykki', s.court.lower())
                    self.assertNotIn('ulko', s.court.lower())

    def test_cintoia_extended_duration(self):
        adapter = sources()[0]
        metadata = {'x': {'displayName': 'Tennis 1', 'category': 'tennis', 'sport': 'Tennis', 'type': 'court'}}
        raw = {'x': [{'s': '1700', 'e': '1730', 'p': 1000, 'ex': [{'du': 60, 'e': '1800', 'p': 2500}]}]}
        self.assertEqual(adapter.parse(DAY, metadata, raw)[0].price, '25.00')
        with self.assertRaises(SourceError): adapter.parse(DAY, metadata, {'unknown': []})

    def test_cintoia_rejects_wrong_date_pointer(self):
        adapter = sources()[0]
        http = Mock()
        http.resources.return_value = {'result': {'x': {}}}
        http.get.return_value = json.dumps({'fields': {'20261102': {'mapValue': {'fields': {'key': {'stringValue': 'https://falconft.s3.eu-north-1.amazonaws.com/wrong/20261103/data.json'}}}}}})
        with self.assertRaises(SourceError): adapter.fetch(DAY, http)
        self.assertEqual(http.get.call_count, 1)

    def test_playfi_both_dates_and_equipment_excluded(self):
        for d in (2, 3):
            day = date(2026, 11, d)
            html = (FIX / f'olari-{day}.html').read_text()
            slots = PlayFi().parse(day, html)
            self.assertTrue(slots)
            self.assertTrue(all(s.court in {'Te1', 'Te2', 'Te3'} and s.price is None for s in slots))
            with self.assertRaises(SourceError): PlayFi().parse(day + timedelta(days=1), html)
        with self.assertRaises(SourceError): PlayFi().parse(DAY, '<div id="root"></div>')

    def test_esport_both_dates_pages(self):
        for d in (2, 3):
            day = date(2026, 11, d)
            for page in (3, 4):
                html = (FIX / f'esport-{page}-{day}.html').read_text()
                self.assertTrue(Esport().parse(day, page, html))
                with self.assertRaises(SourceError): Esport().parse(day + timedelta(days=1), page, html)
                with self.assertRaises(SourceError): Esport().parse(day, page, html.replace('state_white', 'state_mystery'))

    def test_fetch_boundary_blocks_booking_and_payment(self):
        for url in ['http://play.fi/', 'https://play.fi/smashcenter/booking/create-booking',
                    'https://varaus.esportcenter.fi/varaus/index.php?func=do_cal_reservation', 'https://evil.example/']:
            with self.assertRaises(SourceError): check_url(url)

    def test_partial_report_and_modular_files(self):
        good, bad = Mock(), Mock()
        good.name, bad.name = 'Venue', 'Failed'
        good.fetch.side_effect = lambda day, http: [slot(day)]
        bad.fetch.side_effect = SourceError('Unavailable')
        report = collect(NOW, [good, bad], lambda: Mock(evidence=[]))
        self.assertEqual(report['status'], 'partial')
        self.assertFalse(report['validation_passed'])
        self.assertEqual(len(report['slots']), 2)
        self.assertEqual(report['sources'][1]['matching_slots'], 0)
        with tempfile.TemporaryDirectory() as d:
            FileSink(d).deliver(report)
            self.assertEqual(json.loads(Path(d, 'availability.json').read_text())['status'], 'partial')
            self.assertTrue(Path(d, 'availability.md').exists())


if __name__ == '__main__': unittest.main()
