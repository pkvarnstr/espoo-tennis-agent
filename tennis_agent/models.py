from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HELSINKI = ZoneInfo("Europe/Helsinki")


def target_dates(now):
    if now.tzinfo is None:
        raise ValueError("now must have a timezone")
    today = now.astimezone(HELSINKI).date()
    return [today + timedelta(days=i) for i in (1, 2)]


@dataclass(frozen=True)
class Slot:
    venue: str
    court: str
    start: datetime
    end: datetime
    price: str | None
    booking_url: str

    def to_dict(self):
        return dict(venue=self.venue, court=self.court, date=self.start.date().isoformat(),
                    start_time=self.start.strftime("%H:%M"), end_time=self.end.strftime("%H:%M"),
                    start=self.start.isoformat(), end=self.end.isoformat(), price=self.price,
                    currency="EUR", booking_url=self.booking_url)


def eligible(slot, now):
    start, end = slot.start.astimezone(HELSINKI), slot.end.astimezone(HELSINKI)
    low, high = (10, 20) if start.weekday() >= 5 else (17, 21)
    return (start.date() in target_dates(now) and start.date() == end.date()
            and end - start == timedelta(minutes=60)
            and start >= now + timedelta(hours=2)
            and start.hour >= low and (end.hour * 60 + end.minute) <= high * 60)


def consolidate(slots, now):
    unique, duplicates = {}, 0
    for slot in slots:
        if not eligible(slot, now):
            continue
        key = (slot.venue, slot.court, slot.start, slot.end)
        if key in unique:
            if unique[key].price != slot.price:
                raise ValueError("Conflicting prices for the same court/time")
            duplicates += 1
        else:
            unique[key] = slot
    return sorted(unique.values(), key=lambda s: (s.start, s.venue, s.court)), duplicates
