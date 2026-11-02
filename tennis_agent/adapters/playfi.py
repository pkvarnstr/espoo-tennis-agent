from datetime import datetime, timedelta
from urllib.parse import urlencode, urlsplit, parse_qs
from uuid import uuid4
from ..html import DOM
from ..models import Slot, HELSINKI
from ..http import SourceError

BASE = "https://play.fi/smashcenter/booking/booking-calendar"
COURTS = {"36": "Te1", "37": "Te2", "38": "Te3"}


class PlayFi:
    name = "Smash Olari"

    def fetch(self, day, http):
        url = BASE + "?" + urlencode({"BookingCalForm[p_laji]": 7,
            "BookingCalForm[p_pvm]": day.isoformat(), "BookingCalForm[p_calmode]": 2, "_": uuid4().hex})
        return self.parse(day, http.get(url))

    def parse(self, day, html):
        dom = DOM(html).root
        inputs = {n.attrs.get("name"): n.attrs.get("value") for n in dom.all("input")}
        if (inputs.get("BookingCalForm[p_pvm]") != day.isoformat()
                or inputs.get("BookingCalForm[p_laji]") != "7"
                or "Olarin tennishalli" not in dom.text()
                or not any("s-booked" in n.classes() or "s-avail" in n.classes() for n in dom.all("td"))):
            raise SourceError("Play.fi did not return the requested Olari calendar")
        slots = []
        for cell in dom.all("td"):
            if "s-avail" not in cell.classes():
                continue
            for link in cell.all("a"):
                p = urlsplit(link.attrs.get("href", ""))
                if p.path != "/smashcenter/booking/create-booking":
                    continue
                q = parse_qs(p.query)
                rid = q.get("resid", [None])[0]
                if rid not in COURTS or q.get("kesto") != ["60"]:
                    continue
                start = datetime.strptime(q["alkuaika"][0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=HELSINKI)
                if start.date() != day:
                    raise SourceError("Play.fi booking date differs from requested calendar date")
                if COURTS[rid] not in link.text().split():
                    raise SourceError("Play.fi court metadata changed")
                # Never follow create-booking links. Report a read-only calendar URL.
                booking_url = BASE + "?" + urlencode({"BookingCalForm[p_laji]": 7, "BookingCalForm[p_pvm]": day.isoformat()})
                slots.append(Slot(self.name, COURTS[rid], start, start + timedelta(hours=1), None, booking_url))
        return slots
